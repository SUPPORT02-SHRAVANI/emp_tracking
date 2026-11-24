// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// ---------------------------------------------------------------------------------------------
// Network Topology dashboard (Desk page /app/network-topology), created 2026-10-27.
//
// Two views:
//   All Nodes  - one card per GIS Node: sites, tree depth, open faults, the nodes it feeds and
//                its most critical site (the one whose failure cuts off the most others).
//   One node   - the node's feeder tree, drawn left to right (node -> first-level sites ->
//                the sites they feed ...), built from the Site ETIPL codes by
//                network_topology.py.
// Failure simulation (one node): click any box to mark it as stopped; every site fed through
// it turns orange ("affected"), and the Impact panel counts and lists them. "Node Down" stops
// the whole node, and the nodes fed from it ("Fed From Node" on GIS Node). "Show open
// complaints as down" (on by default) marks sites with an open complaint as stopped, so the
// live faults show without a click. Nothing is saved: it is a what-if view.
// Opening the page with frappe.route_options = {node: "D1J"} (GIS Node form) opens that node.
//
// Change log
//   2026-10-27  Created.
//   2026-10-27  Hand tool: press and drag to move the tree (scrollbars hidden); the tree keeps
//               its position when a click redraws it.
//   2026-10-27  Open complaints are shown as down by default ("Show open complaints as down",
//               ticked when a node opens and on Reset): the site's box is red and its branch
//               orange without any click.
//   2026-11-02  EVision design layer (public/css/evision.css): colours in the page's <style> are --ev-* tokens (Frappe
//               Espresso, light + dark mode) instead of hex; lighter type weights;
//               the loading box is a skeleton.
// ---------------------------------------------------------------------------------------------

const NT_METHOD = "emp_tracking.emp_tracking.page.network_topology.network_topology.";
// tree layout, in SVG units
const NT = { W: 210, H: 44, ROW: 54, GAP: 56, PAD: 16 };

frappe.pages["network-topology"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Network Topology"), single_column: true });
	wrapper.nt = new NetworkTopology(page);
};

frappe.pages["network-topology"].on_page_show = function (wrapper) {
	if (wrapper.nt && frappe.route_options && frappe.route_options.node) {
		wrapper.nt.open_node(frappe.route_options.node);
		frappe.route_options = null;
	}
};

function nt_esc(v) {
	return frappe.utils.escape_html(v == null ? "" : String(v));
}

function nt_cut(text, n) {
	text = String(text || "");
	return text.length > n ? text.slice(0, n - 1) + "…" : text;
}

const NT_STYLE = `
<style>
.nt-bar { display:flex; flex-wrap:wrap; gap:10px; align-items:flex-end; margin-bottom:12px; }
.nt-bar .frappe-control { margin-bottom:0; min-width:170px; }
.nt-bar .btn { margin-bottom:2px; }
.nt-check { display:flex; align-items:center; gap:6px; margin-bottom:6px; font-size:13px; }
.nt-kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:12px; }
.nt-kpi { background:var(--card-bg); border:1px solid var(--border-color); border-radius:12px; padding:12px 14px;
	border-top:1px solid var(--ev-border); }
.nt-kpi .v { font-size:22px; font-weight:500; line-height:1.2; color:var(--text-color); }
.nt-kpi .l { font-size:12px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.03em; }
.nt-kpi.t-red { border-top-color:var(--ev-border); } .nt-kpi.t-orange { border-top-color:var(--ev-border); }
.nt-kpi.t-green { border-top-color:var(--ev-border); } .nt-kpi.t-purple { border-top-color:var(--ev-border); }
.nt-body { display:grid; grid-template-columns:1fr 320px; gap:12px; }
@media (max-width: 991px) { .nt-body { grid-template-columns:1fr; } }
.nt-card { background:var(--card-bg); border:1px solid var(--border-color); border-radius:12px; padding:12px; min-width:0; }
.nt-card h6 { margin:0 0 8px; font-weight:500; }
.nt-tree { overflow:auto; max-height:75vh; cursor:grab; user-select:none; scrollbar-width:none; }
.nt-tree::-webkit-scrollbar { display:none; }
.nt-tree.panning { cursor:grabbing; }
.nt-tree svg { display:block; }
.nt-legend { display:flex; flex-wrap:wrap; gap:12px; font-size:12px; color:var(--text-muted); margin-bottom:8px; }
.nt-legend span::before { content:""; display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:4px;
	vertical-align:-2px; background:var(--sw); border:1.5px solid var(--sb, var(--sw)); }
.nt-edge { fill:none; stroke:var(--gray-400); stroke-width:1.5; }
.nt-edge.cut { stroke:var(--orange-500); stroke-dasharray:5 4; }
.nt-box rect { fill:var(--fg-color); stroke:var(--gray-500); stroke-width:1.5; rx:8; cursor:pointer; }
.nt-box text { font-size:12px; fill:var(--text-color); pointer-events:none; }
.nt-box text.code { font-size:11px; font-weight:500; fill:var(--text-muted); }
.nt-box.root rect { fill:var(--blue-100); stroke:var(--blue-500); stroke-width:2.5; }
.nt-box.root text { font-weight:500; font-size:14px; }
.nt-box.down rect { fill:var(--red-100); stroke:var(--red-500); stroke-width:2.5; }
.nt-box.affected rect { fill:var(--orange-100); stroke:var(--orange-500); }
.nt-box.match rect { stroke:var(--purple-500); stroke-width:3; }
.nt-box .fault { fill:var(--red-500); }
.nt-box .fold { fill:var(--card-bg); stroke:var(--gray-500); cursor:pointer; }
.nt-box .fold-t { font-size:12px; font-weight:500; fill:var(--text-color); }
.nt-list { max-height:34vh; overflow:auto; font-size:13px; }
.nt-row { display:flex; gap:8px; align-items:baseline; padding:5px 6px; border-radius:6px; cursor:pointer; }
.nt-row:hover { background:var(--control-bg); }
.nt-row .c { font-weight:500; color:var(--text-muted); font-size:11px; min-width:74px; }
.nt-row .n { flex:1; }
.nt-row .k { font-weight:500; }
.nt-impact { border-left:4px solid var(--red-500); padding:6px 10px; margin-bottom:8px; background:var(--control-bg); border-radius:6px; }
.nt-impact .t { font-weight:500; }
.nt-impact .s { font-size:12px; color:var(--text-muted); }
.nt-cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:12px; }
.nt-ncard { background:var(--card-bg); border:1px solid var(--border-color); border-radius:12px; padding:12px 14px; cursor:pointer;
	border-left:5px solid var(--blue-500); }
.nt-ncard:hover { box-shadow:var(--shadow-md); }
.nt-ncard.has-fault { border-left-color:var(--red-500); }
.nt-ncard .h { display:flex; justify-content:space-between; align-items:baseline; }
.nt-ncard .h b { font-size:18px; }
.nt-ncard .m { font-size:12px; color:var(--text-muted); }
.nt-ncard .stats { display:flex; gap:14px; margin:6px 0; font-size:13px; }
.nt-ncard .crit { font-size:12px; border-top:1px dashed var(--border-color); padding-top:6px; }
.nt-pill { display:inline-block; padding:0 8px; border-radius:10px; font-size:11px; font-weight:500; background:var(--red-100); color:var(--red-700); }
.nt-help { font-size:12px; color:var(--text-muted); margin-bottom:10px; }
</style>`;

class NetworkTopology {
	constructor(page) {
		this.page = page;
		this.stopped = new Set(); // site names marked as stopped by clicking
		this.collapsed = new Set();
		this.node_down = false;
		this.zoom = 1;
		$(page.body).html(`${NT_STYLE}<div class="nt-bar"></div><div class="nt-main"></div>`);
		this.$bar = $(page.body).find(".nt-bar");
		this.$main = $(page.body).find(".nt-main");
		this.page.add_inner_button(__("All Nodes"), () => this.open_node(""));
		this.make_controls();
		this.load_overview().then(() => {
			const start = frappe.route_options && frappe.route_options.node;
			frappe.route_options = null;
			this.open_node(start || "");
		});
	}

	// Date: 2026-10-27
	make_controls() {
		this.f_node = frappe.ui.form.make_control({
			parent: $("<div>").appendTo(this.$bar),
			df: { fieldname: "node", label: __("GIS Node"), fieldtype: "Select", options: [""],
				change: () => { if (!this.syncing) this.open_node(this.f_node.get_value() || ""); } },
			render_input: true,
		});
		this.f_search = frappe.ui.form.make_control({
			parent: $("<div>").appendTo(this.$bar),
			df: { fieldname: "search", label: __("Find site"), fieldtype: "Data", placeholder: __("name or ETIPL code"),
				change: () => this.draw() },
			render_input: true,
		});
		this.$node_tools = $(`<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end">
			<button class="btn btn-sm btn-danger nt-down">${__("Node Down")}</button>
			<button class="btn btn-sm btn-default nt-reset">${__("Reset")}</button>
			<button class="btn btn-sm btn-default nt-zoom" data-z="0.8">−</button>
			<button class="btn btn-sm btn-default nt-zoom" data-z="1.25">+</button>
			<button class="btn btn-sm btn-default nt-fold">${__("Collapse / Expand")}</button>
			<label class="nt-check"><input type="checkbox" class="nt-live" checked> ${__("Show open complaints as down")}</label>
		</div>`).appendTo(this.$bar);
		this.$node_tools.find(".nt-down").on("click", () => { this.node_down = !this.node_down; this.draw(); });
		this.$node_tools.find(".nt-reset").on("click", () => {
			// back to the live picture: only open complaints shown as down (2026-10-27)
			this.stopped.clear(); this.node_down = false; this.$node_tools.find(".nt-live").prop("checked", true); this.draw();
		});
		this.$node_tools.find(".nt-zoom").on("click", (e) => {
			this.zoom = Math.min(2.5, Math.max(0.3, this.zoom * parseFloat($(e.currentTarget).attr("data-z"))));
			this.draw();
		});
		this.$node_tools.find(".nt-fold").on("click", () => {
			// collapse everything below the first level, or open all again
			if (this.collapsed.size) this.collapsed.clear();
			else this.data.sites.filter((s) => !s.parent && s.downstream).forEach((s) => this.collapsed.add(s.name));
			this.draw();
		});
		this.$node_tools.find(".nt-live").on("change", () => this.draw());
	}

	async load_overview() {
		this.overview = await frappe.xcall(NT_METHOD + "get_overview");
		this.f_node.df.options = [{ value: "", label: __("All Nodes") }].concat(
			this.overview.nodes.map((n) => ({ value: n.node, label: `${n.node} (${n.sites})` })));
		this.f_node.set_options();
	}

	// Date: 2026-10-27
	async open_node(node) {
		this.syncing = true;
		await this.f_node.set_value(node || "");
		this.syncing = false;
		this.stopped.clear();
		this.collapsed.clear();
		this.node_down = false;
		this.zoom = 1;
		// 2026-10-27: open complaints show as down (red box, orange branch) as soon as a node opens
		this.$node_tools.find(".nt-live").prop("checked", true);
		this.f_search.$wrapper.toggle(!!node);
		this.$node_tools.toggle(!!node);
		if (!node) {
			this.data = null;
			this.draw_overview();
			return;
		}
		this.$main.html(`<div class="text-muted ev-loading">${__("Loading...")}</div>`);
		this.data = await frappe.xcall(NT_METHOD + "get_topology", { node });
		this.prepare();
		this.draw();
	}

	// ------------------------------------------------------------------ overview

	draw_overview() {
		const o = this.overview;
		const total_sites = o.nodes.reduce((a, n) => a + n.sites, 0);
		const with_tree = o.nodes.filter((n) => n.sites);
		this.$main.html(`
			<div class="nt-kpis">
				${this.kpi(o.nodes.length, __("GIS Nodes"))}
				${this.kpi(with_tree.length, __("Nodes with Sites"), "t-green")}
				${this.kpi(total_sites, __("Sites"), "t-purple")}
				${this.kpi(o.open_faults, __("Open Faults"), "t-red")}
			</div>
			<div class="nt-help">${__("Click a node to see its feeder tree and test what stops if a site or the node fails. \"Most critical\" is the site whose failure cuts off the most other sites.")}</div>
			<div class="nt-cards">${o.nodes.map((n) => `
				<div class="nt-ncard ${n.faults ? "has-fault" : ""}" data-node="${nt_esc(n.node)}">
					<div class="h"><b>${nt_esc(n.node)}</b>${n.faults ? `<span class="nt-pill">${__("{0} open", [n.faults])}</span>` : ""}</div>
					<div class="m">${nt_esc([n.area, n.team].filter(Boolean).join(" · ") || "-")}</div>
					<div class="stats"><span><b>${n.sites}</b> ${__("sites")}</span><span><b>${n.depth}</b> ${__("levels")}</span>
						${n.feeds ? `<span><b>${n.feeds}</b> ${__("nodes fed")}</span>` : ""}</div>
					${n.fed_from ? `<div class="m">${__("Fed from")} <b>${nt_esc(n.fed_from)}</b></div>` : ""}
					${n.critical_count ? `<div class="crit">${__("Most critical")}: <b>${nt_esc(n.critical_code || "")}</b> ${nt_esc(nt_cut(n.critical_site, 34))}
						<br>${__("If it stops, {0} more sites stop", [`<b>${n.critical_count}</b>`])}</div>` : ""}
				</div>`).join("")}</div>`);
		this.$main.find(".nt-ncard").on("click", (e) => this.open_node($(e.currentTarget).attr("data-node")));
	}

	kpi(value, label, cls = "") {
		return `<div class="nt-kpi ${cls}"><div class="v">${format_number(value || 0)}</div><div class="l">${label}</div></div>`;
	}

	// ------------------------------------------------------------------ one node

	// Date: 2026-10-27
	prepare() {
		const d = this.data;
		this.by_name = {};
		this.children = { "": [] };
		d.sites.forEach((s) => { this.by_name[s.name] = s; this.children[s.name] = []; });
		d.sites.forEach((s) => this.children[s.parent || ""].push(s.name));
		// sites side by side in ETIPL order ("D1J.2" before "D1J.10")
		const key = (s) => (s.etipl_code || "~" + s.site_name).split(".").map((p) => (isNaN(p) ? p : p.padStart(4, "0"))).join(".");
		Object.values(this.children).forEach((list) => list.sort((a, b) => key(this.by_name[a]).localeCompare(key(this.by_name[b]))));
		this.faulty = new Set(d.faults.filter((f) => f.site && this.by_name[f.site]).map((f) => f.site));
		this.node_faults = d.faults.filter((f) => !f.site || !this.by_name[f.site]).length;
	}

	descendants(name) {
		const out = [];
		const stack = [...(this.children[name] || [])];
		while (stack.length) {
			const s = stack.pop();
			out.push(s);
			stack.push(...(this.children[s] || []));
		}
		return out;
	}

	// Date: 2026-10-27
	// What the current what-if stops: the stopped points and everything fed through them.
	impact() {
		const live = this.$node_tools.find(".nt-live").prop("checked");
		const down = new Set(this.stopped);
		if (live) this.faulty.forEach((s) => down.add(s));
		const affected = new Set();
		if (this.node_down) {
			this.data.sites.forEach((s) => affected.add(s.name));
		} else {
			down.forEach((s) => this.descendants(s).forEach((c) => { if (!down.has(c)) affected.add(c); }));
		}
		return { down: this.node_down ? new Set() : down, affected };
	}

	// Date: 2026-10-27
	draw() {
		if (!this.data) return;
		const d = this.data;
		const { down, affected } = this.impact();
		const total = d.sites.length;
		const stopped_sites = new Set([...down, ...affected]);
		const working = total - stopped_sites.size;
		// 2026-10-27: keep the tree where the user dragged it; every click redraws it
		const $old = this.$main.find(".nt-tree");
		const scroll = $old.length && this.data_node === d.node.name ? { left: $old[0].scrollLeft, top: $old[0].scrollTop } : null;
		this.data_node = d.node.name;
		this.$main.html(`
			<div class="nt-kpis">
				${this.kpi(total, __("Sites in {0}", [d.node.name]))}
				${this.kpi(d.depth, __("Levels"), "t-purple")}
				${this.kpi(this.node_down ? 1 : down.size, this.node_down ? __("Node Down") : __("Stopped Points"), "t-red")}
				${this.kpi(stopped_sites.size, __("Sites Without Service"), "t-orange")}
				${this.kpi(working, __("Still Working"), "t-green")}
			</div>
			<div class="nt-body">
				<div class="nt-card">
					<div class="nt-legend">
						<span style="--sw:var(--blue-100);--sb:var(--blue-500)">${__("Node")}</span>
						<span style="--sw:var(--fg-color);--sb:var(--gray-500)">${__("Working")}</span>
						<span style="--sw:var(--red-100);--sb:var(--red-500)">${__("Stopped (click a box)")}</span>
						<span style="--sw:var(--orange-100);--sb:var(--orange-500)">${__("Affected: fed through a stopped point")}</span>
						<span style="--sw:var(--red-500)">${__("Open fault")}</span>
						<em>${__("Hold and drag to move the tree")}</em>
					</div>
					<div class="nt-tree">${total ? this.svg(down, affected) : `<div class="text-muted">${__("No Sites for this node yet.")}</div>`}</div>
				</div>
				<div>${this.side_panel(down, affected)}</div>
			</div>`);
		if (scroll) Object.assign(this.$main.find(".nt-tree")[0] || {}, { scrollLeft: scroll.left, scrollTop: scroll.top });
		this.bind_tree();
	}

	// Date: 2026-10-27
	// Hand tool: press and drag the tree to move it left / right / up / down (no scrollbars).
	// Touch screens already move it with a finger swipe. A drag is not taken as a click on a box.
	bind_pan($tree) {
		const el = $tree[0];
		$(document).off(".ntpan");
		if (!el) return;
		$tree.on("mousedown", (e) => {
			if (e.button !== 0) return;
			this._drag = { x: e.clientX, y: e.clientY, left: el.scrollLeft, top: el.scrollTop };
			this._dragged = false;
			$tree.addClass("panning");
			e.preventDefault(); // no text selection while dragging
		});
		$(document).on("mousemove.ntpan", (e) => {
			if (!this._drag) return;
			const dx = e.clientX - this._drag.x, dy = e.clientY - this._drag.y;
			if (Math.abs(dx) + Math.abs(dy) > 4) this._dragged = true;
			el.scrollLeft = this._drag.left - dx;
			el.scrollTop = this._drag.top - dy;
		});
		$(document).on("mouseup.ntpan", () => {
			this._drag = null;
			$tree.removeClass("panning");
		});
	}

	// Date: 2026-10-27
	// Left-to-right tidy tree: each leaf gets its own row, a parent sits in the middle of its children.
	svg(down, affected) {
		const pos = {};
		let row = 0, max_depth = 0;
		const place = (name, depth) => {
			max_depth = Math.max(max_depth, depth);
			const kids = this.collapsed.has(name) ? [] : this.children[name] || [];
			if (!kids.length) {
				pos[name] = { x: depth, y: row++ };
			} else {
				kids.forEach((k) => place(k, depth + 1));
				pos[name] = { x: depth, y: (pos[kids[0]].y + pos[kids[kids.length - 1]].y) / 2 };
			}
		};
		place("", 0);
		const X = (p) => NT.PAD + p.x * (NT.W + NT.GAP);
		const Y = (p) => NT.PAD + p.y * NT.ROW;
		const width = X({ x: max_depth }) + NT.W + NT.PAD;
		const height = NT.PAD * 2 + Math.max(row, 1) * NT.ROW;
		const search = (this.f_search.get_value() || "").trim().toLowerCase();

		let edges = "", boxes = "";
		const stopped_any = (n) => n === "" ? this.node_down : down.has(n) || affected.has(n);
		Object.keys(pos).forEach((name) => {
			if (name === "") return;
			const s = this.by_name[name];
			const parent = s.parent || "";
			if (!pos[parent]) return;
			const a = pos[parent], b = pos[name];
			const x1 = X(a) + NT.W, y1 = Y(a) + NT.H / 2, x2 = X(b), y2 = Y(b) + NT.H / 2, mx = (x1 + x2) / 2;
			edges += `<path class="nt-edge ${stopped_any(parent) || stopped_any(name) ? "cut" : ""}"
				d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}"/>`;
		});
		Object.entries(pos).forEach(([name, p]) => {
			const x = X(p), y = Y(p);
			if (name === "") {
				boxes += `<g class="nt-box root ${this.node_down ? "down" : ""}" data-name="" transform="translate(${x},${y})">
					<rect width="${NT.W}" height="${NT.H}"></rect>
					<text x="12" y="19">${nt_esc(this.data.node.name)} ${__("Node")}</text>
					<text class="code" x="12" y="35">${nt_esc(nt_cut(this.data.node.area || "", 30))}</text>
					${this.node_faults ? `<circle class="fault" cx="${NT.W - 10}" cy="10" r="6"></circle>` : ""}
					<title>${nt_esc(this.data.node.name)}: ${__("click to set the whole node down")}</title></g>`;
				return;
			}
			const s = this.by_name[name];
			const cls = down.has(name) ? "down" : affected.has(name) ? "affected" : "";
			const match = search && ((s.site_name || "").toLowerCase().includes(search) || (s.etipl_code || "").toLowerCase().includes(search));
			const kids = (this.children[name] || []).length;
			boxes += `<g class="nt-box ${cls} ${match ? "match" : ""}" data-name="${nt_esc(name)}" transform="translate(${x},${y})">
				<rect width="${NT.W}" height="${NT.H}"></rect>
				<text class="code" x="10" y="16">${nt_esc(s.etipl_code || __("no code"))}${s.downstream ? ` · ${__("feeds {0}", [s.downstream])}` : ""}</text>
				<text x="10" y="33">${nt_esc(nt_cut(s.site_name, 29))}</text>
				${this.faulty.has(name) ? `<circle class="fault" cx="${NT.W - 10}" cy="10" r="6"></circle>` : ""}
				${kids ? `<g class="nt-foldbtn" data-fold="${nt_esc(name)}"><circle class="fold" cx="${NT.W}" cy="${NT.H / 2}" r="9"></circle>
					<text class="fold-t" x="${NT.W - 4}" y="${NT.H / 2 + 4}">${this.collapsed.has(name) ? "+" : "−"}</text></g>` : ""}
				<title>${nt_esc(s.etipl_code || "")} ${nt_esc(s.site_name)}${s.b_location ? `\n${__("B Location")}: ${nt_esc(s.b_location)}` : ""}
${__("Fed through it")}: ${s.downstream}\n${__("Click to stop / restart this site")}</title></g>`;
		});
		return `<svg width="${width * this.zoom}" height="${height * this.zoom}" viewBox="0 0 ${width} ${height}">${edges}${boxes}</svg>`;
	}

	bind_tree() {
		const $tree = this.$main.find(".nt-tree");
		this.bind_pan($tree);
		$tree.find(".nt-foldbtn").on("click", (e) => {
			e.stopPropagation();
			if (this._dragged) return; // the mouse was dragging the tree, not clicking
			const name = $(e.currentTarget).attr("data-fold");
			this.collapsed.has(name) ? this.collapsed.delete(name) : this.collapsed.add(name);
			this.draw();
		});
		$tree.find(".nt-box").on("click", (e) => {
			if (this._dragged) return;
			const name = $(e.currentTarget).attr("data-name");
			if (name === "") this.node_down = !this.node_down;
			else this.stopped.has(name) ? this.stopped.delete(name) : this.stopped.add(name);
			this.draw();
		});
		this.$main.find("[data-sim]").on("click", (e) => {
			const name = $(e.currentTarget).attr("data-sim");
			this.stopped.has(name) ? this.stopped.delete(name) : this.stopped.add(name);
			this.draw();
		});
		this.$main.find("[data-site]").on("click", (e) => frappe.set_route("Form", "Site", $(e.currentTarget).attr("data-site")));
		this.$main.find("[data-node]").on("click", (e) => this.open_node($(e.currentTarget).attr("data-node")));
		this.$main.find("[data-fault]").on("click", (e) => frappe.set_route("Form", "Complaint Information", $(e.currentTarget).attr("data-fault")));
	}

	site_row(name, right, attr = "data-site") {
		const s = this.by_name[name];
		return `<div class="nt-row" ${attr}="${nt_esc(name)}"><span class="c">${nt_esc(s.etipl_code || "-")}</span>
			<span class="n">${nt_esc(nt_cut(s.site_name, 40))}</span><span class="k">${right == null ? "" : right}</span></div>`;
	}

	// Date: 2026-10-27
	side_panel(down, affected) {
		const d = this.data;
		let impact = "";
		if (this.node_down) {
			const fed = d.feeds.reduce((a, f) => a + f.sites, 0);
			impact = `<div class="nt-impact"><div class="t">${__("{0} node down", [nt_esc(d.node.name)])}</div>
				<div class="s">${__("All {0} sites of this node stop.", [d.sites.length])}
				${d.feeds.length ? __("Fed from it, these nodes stop too: {0} ({1} more sites).", [d.feeds.map((f) => nt_esc(f.node)).join(", "), fed]) : ""}</div></div>`
				+ (d.feeds.length ? `<div class="nt-list">${d.feeds.map((f) => `<div class="nt-row" data-node="${nt_esc(f.node)}">
					<span class="c">${nt_esc(f.node)}</span><span class="n">${__("fed from {0}", [nt_esc(f.fed_from)])}</span>
					<span class="k">${__("{0} sites", [f.sites])}</span></div>`).join("")}</div>` : "");
		} else if (down.size) {
			impact = [...down].map((name) => {
				const cut = this.descendants(name).filter((c) => !down.has(c));
				const s = this.by_name[name];
				return `<div class="nt-impact"><div class="t">${nt_esc(s.etipl_code || "")} ${nt_esc(nt_cut(s.site_name, 36))} ${__("stops")}</div>
					<div class="s">${cut.length ? __("{0} more sites lose service:", [cut.length]) : __("No other site is fed through it.")}</div></div>
					${cut.length ? `<div class="nt-list" style="max-height:22vh">${cut.slice(0, 80).map((c) => this.site_row(c)).join("")}
						${cut.length > 80 ? `<div class="text-muted small">${__("and {0} more", [cut.length - 80])}</div>` : ""}</div>` : ""}`;
			}).join("");
		} else {
			impact = `<div class="text-muted small">${__("Click a site box to see what stops if it fails, or use Node Down.")}</div>`;
		}

		// the points whose failure cuts off the most sites
		const critical = d.sites.filter((s) => s.downstream).sort((a, b) => b.downstream - a.downstream).slice(0, 10);
		const faults = d.faults.length ? `<div class="nt-card" style="margin-top:12px"><h6>${__("Open Faults")} (${d.faults.length})</h6>
			<div class="nt-list">${d.faults.map((f) => `<div class="nt-row" data-fault="${nt_esc(f.name)}">
				<span class="c">${nt_esc(f.name)}</span><span class="n">${nt_esc(f.site ? (this.by_name[f.site] || {}).site_name || f.site : f.society_name || __("node"))}</span>
				<span class="k">${nt_esc(f.workflow_state || "")}</span></div>`).join("")}</div></div>` : "";
		return `
			<div class="nt-card"><h6>${__("Impact")}</h6>${impact}</div>
			<div class="nt-card" style="margin-top:12px"><h6>${__("Most Critical Points")}</h6>
				<div class="nt-help" style="margin-bottom:4px">${__("Sites that feed the most others. Click one to simulate its failure.")}</div>
				<div class="nt-list">${critical.length ? critical.map((s) => this.site_row(s.name, __("{0} sites", [s.downstream]), "data-sim")).join("")
					: `<div class="text-muted small">${__("Every site is fed straight from the node.")}</div>`}</div></div>
			${faults}
			<div class="nt-card" style="margin-top:12px"><h6>${__("Upstream")}</h6>
				<div class="small">${d.node.fed_from ? __("Fed from node {0}: if it stops, {1} stops too.", [`<a data-node="${nt_esc(d.node.fed_from)}">${nt_esc(d.node.fed_from)}</a>`, nt_esc(d.node.name)])
					: __("No \"Fed From Node\" set on this GIS Node.")}
				${d.feeds.length ? `<br>${__("Feeds: {0}", [d.feeds.map((f) => nt_esc(f.node)).join(", ")])}` : ""}</div></div>`;
	}
}
