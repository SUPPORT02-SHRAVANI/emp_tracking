// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// ---------------------------------------------------------------------------------------------
// KMZ Map dashboard (Desk page /app/kmz-map), created 2026-10-26.
//
// Shows every KMZ Route (line) and KMZ Point (pin) on one map, coloured by GIS Node, with
// filters: GIS Node, Area, KMZ File, KMZ Path (folder chain inside the KMZ), Matched By, Site
// and what to show. KPI tiles give the totals, and the node list on the right zooms to a
// node when clicked. Clicking a line or pin shows its node, KMZ file and full KMZ path.
// The map is Frappe's own Leaflet (loaded on demand, see 2026-11-17) with its street / satellite tiles
// (frappe.utils.map_defaults). Data comes from kmz_map.py.
// Opening the page with frappe.route_options = {gis: "B1V"} (GIS Node form button) pre-filters it.
//
// Change log
//   2026-10-26  Created.
//   2026-10-27  Rows arrive as short arrays; a popup loads its row's details when opened.
//   2026-10-27  Open complaints shown on the map ("Show open complaints", on by default), with
//               the same rules as the Network Topology page: the lines / pins of a site with an
//               open complaint turn red, those of the sites fed through it orange, the node pin
//               gets a red ring and a warning marker sits at each complaint.
//   2026-10-27  GIS Node and Area filters narrow each other (link_node_area).
//   2026-10-27  Pins coloured by type (ODF, Encloser / JC, Pole, Tree, Chamber, code point, building)
//               instead of the node colour; legend entries hide / show a type when clicked.
//   2026-10-27  Legend moved onto the map as a collapsible "Index" box (bottom right) explaining
//               every pin, line, node and complaint symbol.
//   2026-10-27  Pin types, their colours / default visibility and the down / affected / no-node
//               colours come from KMZ Map Settings ("Map Settings" button); built-in defaults
//               when nothing is saved.
//   2026-10-27  "Add Route" button: draw one route by clicking points (a click on a pin snaps to it)
//               and save it as a KMZ Route (start_draw / finish_draw, kmz_map.add_route).
//   2026-10-27  Routes with no GIS Node drawn dashed; purple / pink / red taken out of the node colours
//               (they looked like the no-node fuchsia or the complaint red).
//   2026-10-27  "Assign Nodes" button: node-less rows get the nearest matched node within a chosen
//               distance, after a preview; Undo All takes them back (assign_nodes).
//   2026-10-28  Hovering a pin shows its name (building / ODF / pole name) instead of its type.
//   2026-11-02  EVision design layer (public/css/evision.css): colours in the page's <style> are --ev-* tokens (Frappe
//               Espresso, light + dark mode) instead of hex; lighter type weights.
//   2026-11-17  Leaflet loaded with frappe.require("leaflet.bundle.js" / ".css") before the map is
//               made: Frappe 16.54 stopped loading it with the desk, so the map was blank.
//               Map pin / route colours are unchanged.
// ---------------------------------------------------------------------------------------------

const KM_METHOD = "emp_tracking.emp_tracking.page.kmz_map.kmz_map.";
// 2026-10-27: no purple / pink (looked like the fuchsia no-node colour) and no red (open complaints)
const KM_PALETTE = ["#2563eb", "#16a34a", "#ea580c", "#854d0e", "#0891b2", "#1e3a8a", "#ca8a04", "#4f46e5",
	"#334155", "#0d9488", "#4d7c0f", "#65a30d"];
// 2026-10-27: these three and KM_PIN_TYPES are replaced by KMZ Map Settings when the page loads
let KM_UNMATCHED = "#c026d3"; // fuchsia: rows with no GIS Node (2026-10-27: was grey, hard to see)
let KM_DOWN = "#dc2626"; // red: site with an open complaint
let KM_AFFECTED = "#f97316"; // orange: site fed through a down site

frappe.pages["kmz-map"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("KMZ Map"), single_column: true });
	wrapper.km = new KMZMap(page);
};

frappe.pages["kmz-map"].on_page_show = function (wrapper) {
	if (!wrapper.km) return;
	// a GIS Node form sends its node through route_options
	if (frappe.route_options && frappe.route_options.gis) {
		wrapper.km.set_node(frappe.route_options.gis);
		frappe.route_options = null;
	}
	if (wrapper.km.map) setTimeout(() => wrapper.km.map.invalidateSize(), 50);
};

function km_esc(v) {
	return frappe.utils.escape_html(v == null ? "" : String(v));
}

// Date: 2026-10-27
// Pin types, read from the KMZ pin name (the KMZ has no type field). Order matters: first match
// wins. Red / orange stay reserved for open complaints. These are the built-in defaults; the
// rows of KMZ Map Settings replace them (km_apply_settings).
let KM_PIN_TYPES = [
	{ key: "odf", label: __("ODF"), colour: "#0f766e", test: /\bodf\b/i },
	{ key: "enc", label: __("Encloser / JC"), colour: "#eab308", test: /\bencl\w*|\bjc\b|\btapping\b/i },
	{ key: "pole", label: __("Pole / Light"), colour: "#64748b", test: /\b(pole|light)\b/i },
	{ key: "tree", label: __("Tree"), colour: "#22c55e", test: /\btree\b/i },
	{ key: "chamber", label: __("Chamber / HH"), colour: "#0ea5e9", test: /\b(hh|chamber|manhole|mh)\b/i },
	// short codes with a digit, e.g. "1PZ21", "G7M03", "C2"
	{ key: "code", label: __("Code point"), colour: "#ec4899", test: /^(?=.*\d)[a-z0-9:-]{2,8}$/i },
	{ key: "building", label: __("Building"), colour: "#7c3aed", test: /^/ }, // everything else
];

function km_pin_type(title) {
	const t = (title || "").trim();
	return KM_PIN_TYPES.find((p) => p.test.test(t));
}

// Date: 2026-10-27
// Turns KMZ Map Settings into the page's colours and pin types. A "Name has word" row matches
// whole words in the pin name; a word ending in * matches any ending ("encl*" = encloser,
// enclosure, enclouser). Returns the types switched off by default (Show unticked).
function km_apply_settings(s) {
	if (!s) return [];
	KM_DOWN = s.down_colour || KM_DOWN;
	KM_AFFECTED = s.affected_colour || KM_AFFECTED;
	KM_UNMATCHED = s.no_node_colour || KM_UNMATCHED;
	const esc = (w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
	const types = (s.pin_types || []).map((r, i) => {
		let test = /^/; // Everything else
		if (r.match_type === "Short code (e.g. 1PZ21)") {
			test = /^(?=.*\d)[a-z0-9:-]{2,8}$/i;
		} else if (r.match_type !== "Everything else") {
			const words = (r.keywords || "").split(",").map((w) => w.trim().toLowerCase()).filter(Boolean)
				.map((w) => (w.endsWith("*") ? `\\b${esc(w.slice(0, -1))}\\w*` : `\\b${esc(w)}\\b`));
			test = words.length ? new RegExp(words.join("|"), "i") : /(?!)/; // no words: matches nothing
		}
		return { key: `t${i}`, label: r.label, colour: r.colour, test, show: r.show };
	});
	if (types.length) KM_PIN_TYPES = types;
	return types.filter((t) => !t.show).map((t) => t.key);
}

// one fixed colour per GIS code, so a node keeps its colour across filters
function km_colour(gis) {
	if (!gis) return KM_UNMATCHED;
	let hash = 0;
	for (const ch of gis) hash = (hash * 31 + ch.charCodeAt(0)) % 9973;
	return KM_PALETTE[hash % KM_PALETTE.length];
}

const KM_STYLE = `
<style>
.km-filters { display:flex; flex-wrap:wrap; gap:12px; align-items:flex-end; margin-bottom:12px; }
.km-filters .frappe-control { margin-bottom:0; min-width:160px; }
.km-kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:12px; }
.km-kpi { background:var(--card-bg); border:1px solid var(--border-color); border-radius:12px; padding:12px 14px;
	border-top:1px solid var(--ev-border); }
.km-kpi .v { font-size:22px; font-weight:500; color:var(--text-color); line-height:1.2; }
.km-kpi .l { font-size:12px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.03em; }
.km-kpi.t-green { border-top-color:var(--ev-border); } .km-kpi.t-orange { border-top-color:var(--ev-border); }
.km-kpi.t-purple { border-top-color:var(--ev-border); } .km-kpi.t-gray { border-top-color:var(--ev-border); }
.km-kpi.t-red { border-top-color:var(--ev-border); } .km-kpi.t-red .v { color:var(--red-600); }
.km-node .pill { font-size:11px; font-weight:600; color:#fff; background:var(--km-down); border-radius:10px; padding:0 6px; }
.km-index { background:var(--card-bg); color:var(--text-color); border:1px solid var(--border-color); border-radius:8px;
	box-shadow:0 1px 4px rgba(0,0,0,.2); font-size:12px; min-width:190px; max-height:55vh; overflow:auto; }
.km-index .hd { display:flex; justify-content:space-between; padding:6px 10px; font-weight:500; cursor:pointer; user-select:none; }
.km-index .bd { padding:0 10px 8px; } .km-index.closed .bd { display:none; }
.km-index .sec { margin-top:6px; font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; }
.km-index .it { display:flex; align-items:center; gap:7px; padding:2px 0; }
.km-index .it .c { margin-left:auto; color:var(--text-muted); }
.km-index .dot { width:11px; height:11px; border-radius:50%; flex:none; background:var(--sw); border:1.5px solid var(--ev-card);
	box-shadow:0 0 0 1px rgba(0,0,0,.25); }
.km-index .ln { width:18px; height:4px; border-radius:2px; flex:none; background:var(--sw); }
.km-index .ln.thick { height:6px; }
.km-index .pt { cursor:pointer; } .km-index .pt.off { opacity:.4; text-decoration:line-through; }
.km-index .bang { width:16px; height:16px; border-radius:50%; flex:none; background:var(--km-down); color:#fff; font-weight:500;
	font-size:10px; display:flex; align-items:center; justify-content:center; }
.km-fault-icon { display:flex; align-items:center; justify-content:center; width:26px; height:26px; border-radius:50%;
	background:var(--km-down); color:#fff; font-weight:500; border:2px solid var(--ev-card); box-shadow:0 0 0 0 rgba(220,38,38,.7);
	animation:km-pulse 1.6s infinite; }
@keyframes km-pulse { 0% { box-shadow:0 0 0 0 rgba(220,38,38,.7); } 70% { box-shadow:0 0 0 14px rgba(220,38,38,0); }
	100% { box-shadow:0 0 0 0 rgba(220,38,38,0); } }
.km-body { display:grid; grid-template-columns:1fr 260px; gap:12px; }
@media (max-width: 991px) { .km-body { grid-template-columns:1fr; } }
.km-card { background:var(--card-bg); border:1px solid var(--border-color); border-radius:12px; padding:10px; min-width:0; }
.km-map { height:72vh; min-height:420px; border-radius:8px; z-index:0; }
.km-note { font-size:12px; color:var(--text-muted); margin-top:6px; }
.km-nodes { max-height:72vh; overflow:auto; }
.km-node { display:flex; align-items:center; gap:8px; padding:6px 8px; border-radius:8px; cursor:pointer; }
.km-node:hover, .km-node.active { background:var(--control-bg); }
.km-node .dot { width:10px; height:10px; border-radius:50%; flex:none; }
.km-node .n { font-weight:600; flex:1; }
.km-node .c { font-size:12px; color:var(--text-muted); }
.km-draw { background:var(--card-bg); color:var(--text-color); border:1px solid var(--border-color); border-radius:8px;
	box-shadow:0 1px 4px rgba(0,0,0,.2); padding:6px 8px; display:flex; flex-wrap:wrap; gap:6px; align-items:center;
	font-size:12px; max-width:calc(100vw - 80px); }
.km-draw .msg { font-weight:600; margin-right:4px; }
.km-pop b { color:var(--text-color); } .km-pop div { margin-top:2px; }
.km-pop .path { font-size:11px; color:var(--text-muted); word-break:break-word; }
</style>`;

class KMZMap {
	constructor(page) {
		this.page = page;
		this.loaded = false;
		this.hidden_types = new Set(); // pin types switched off in the legend (2026-10-27)
		$(page.body).html(`${KM_STYLE}
			<div class="km-filters"></div>
			<div class="km-kpis"></div>
			<div class="km-body">
				<div class="km-card"><div class="km-map" id="km-map-${frappe.utils.get_random(6)}"></div>
					<div class="km-note"></div></div>
				<div class="km-card"><div class="text-muted small" style="padding:2px 8px 6px">${__("GIS Nodes (click to filter)")}</div>
					<div class="km-nodes"></div></div>
			</div>`);
		this.$ = (sel) => $(page.body).find(sel);
		this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");
		this.page.add_inner_button(__("Upload KMZ"), () => frappe.new_doc("KMZ Upload"));
		this.page.add_inner_button(__("Clear Filters"), () => this.clear_filters());
		// 2026-10-27: pin types and colours
		this.page.add_inner_button(__("Map Settings"), () => frappe.set_route("Form", "KMZ Map Settings"));
		// 2026-10-27: draw one route on the map (start_draw), for users who may create KMZ Routes
		if (frappe.model.can_create("KMZ Route")) this.page.add_inner_button(__("Add Route"), () => this.start_draw());
		// 2026-10-27: give node-less routes / pins the nearest node (assign_nodes), for users who may edit them
		if ((frappe.boot.user.can_write || []).includes("KMZ Route")) {
			this.page.add_inner_button(__("Assign Nodes"), () => this.assign_nodes());
		}
		this.make_filters();
		// 2026-11-17: Frappe 16.54 no longer loads Leaflet with the desk; its own Geolocation field
		// loads it on demand, so this page does the same before drawing the map (L was undefined
		// and the map stayed blank). The filter options load at the same time.
		Promise.all([
			frappe.require("leaflet.bundle.js"),
			frappe.require("leaflet.bundle.css"),
			this.load_options(),
		]).then(() => {
			this.make_map();
			this.loaded = true;
			if (frappe.route_options && frappe.route_options.gis) {
				this.set_node(frappe.route_options.gis);
				frappe.route_options = null;
			} else {
				this.refresh();
			}
		});
	}

	// Date: 2026-10-26
	control(df) {
		const c = frappe.ui.form.make_control({
			parent: $("<div>").appendTo(this.$(".km-filters")),
			df: { ...df, change: async () => {
				if (!this.loaded || this.syncing) return;
				// 2026-10-27: node and area narrow each other's choices before the map reloads
				if (df.fieldname === "gis" || df.fieldname === "area") await this.link_node_area();
				this.refresh();
			} },
			render_input: true,
		});
		return c;
	}

	make_filters() {
		this.f = {
			gis: this.control({ fieldname: "gis", label: __("GIS Node"), fieldtype: "Select", options: [""] }),
			area: this.control({ fieldname: "area", label: __("Area"), fieldtype: "Select", options: [""] }),
			source_file: this.control({ fieldname: "source_file", label: __("KMZ File"), fieldtype: "Select", options: [""] }),
			path: this.control({ fieldname: "path", label: __("KMZ Path contains"), fieldtype: "Data",
				placeholder: __("e.g. C1U or Icon Residency") }),
			matched_by: this.control({ fieldname: "matched_by", label: __("Matched By"), fieldtype: "Select",
				options: ["", "Node Name", "Building Name", "Same Folder", "Drawn on Map", "Nearest Node", "Not Matched"] }),
			site: this.control({ fieldname: "site", label: __("Site"), fieldtype: "Link", options: "Site" }),
			show: this.control({ fieldname: "show", label: __("Show"), fieldtype: "Select",
				options: ["Routes and Pins", "Routes Only", "Pins Only"], default: "Routes and Pins" }),
		};
		this.f.show.set_value("Routes and Pins");
		// 2026-10-27: kept out of this.f so values() does not send it; it only redraws the map
		this.show_faults = frappe.ui.form.make_control({
			parent: $("<div>").appendTo(this.$(".km-filters")),
			df: { fieldname: "show_faults", label: __("Show open complaints"), fieldtype: "Check",
				change: () => { if (this.data) this.draw_map(this.data, false); } },
			render_input: true,
		});
		this.show_faults.set_value(1);
	}

	// Date: 2026-10-26
	async load_options() {
		const o = await frappe.xcall(KM_METHOD + "get_filter_options");
		const set = (c, values) => { c.df.options = [""].concat(values); c.set_options(); };
		this.options = o;
		// 2026-10-27: colours and pin types from KMZ Map Settings; types with Show unticked start hidden
		this.hidden_types = new Set(km_apply_settings(o.settings));
		$(this.page.body).css("--km-down", KM_DOWN);
		set(this.f.gis, o.nodes);
		set(this.f.area, o.areas);
		set(this.f.source_file, o.files);
	}

	// Date: 2026-10-27
	// With a GIS Node chosen, Area offers only that node's area; with an Area chosen, GIS Node
	// offers only the nodes in it. A value the other filter no longer allows is cleared, without
	// starting a second map reload (syncing).
	async link_node_area() {
		const o = this.options;
		if (!o) return;
		const gis = this.f.gis.get_value(), area = this.f.area.get_value();
		const areas = gis ? (o.node_area[gis] ? [o.node_area[gis]] : []) : o.areas;
		const nodes = area ? o.nodes.filter((n) => o.node_area[n] === area) : o.nodes;
		const set = (c, values) => { c.df.options = [""].concat(values); c.set_options(); };
		set(this.f.area, areas);
		set(this.f.gis, nodes);
		this.syncing = true;
		if (area && !areas.includes(area)) await this.f.area.set_value("");
		if (gis && !nodes.includes(gis)) await this.f.gis.set_value("");
		this.syncing = false;
	}

	values() {
		const v = {};
		for (const [k, c] of Object.entries(this.f)) v[k] = c.get_value() || null;
		return v;
	}

	set_node(gis) {
		this.syncing = true;
		this.f.gis.set_value(gis).then(async () => { this.syncing = false; await this.link_node_area(); this.refresh(); });
	}

	clear_filters() {
		this.syncing = true;
		Promise.all(Object.entries(this.f).map(([k, c]) => c.set_value(k === "show" ? "Routes and Pins" : "")))
			.then(async () => { this.syncing = false; await this.link_node_area(); this.refresh(); });
	}

	// Date: 2026-10-26
	make_map() {
		const d = frappe.utils.map_defaults;
		L.Icon.Default.imagePath = d.image_path;
		// canvas renderer: thousands of pins stay smooth
		this.map = L.map(this.$(".km-map")[0], { preferCanvas: true }).setView(d.center, 11);
		const street = L.tileLayer(d.tiles.default_tile.url, d.tiles.default_tile.options).addTo(this.map);
		const satellite = L.tileLayer(d.tiles.satellite_tile.url, d.tiles.satellite_tile.options);
		this.routes_layer = L.featureGroup().addTo(this.map);
		this.points_layer = L.featureGroup().addTo(this.map);
		// 2026-10-27: down / affected lines and pins and complaint markers, kept above the rest
		this.faults_layer = L.featureGroup().addTo(this.map);
		L.control.layers({ [__("Street")]: street, [__("Satellite")]: satellite },
			{ [__("Routes")]: this.routes_layer, [__("Pins")]: this.points_layer,
				[__("Open Complaints")]: this.faults_layer }).addTo(this.map);
		// 2026-10-27: Index (map legend) in the bottom-right corner, filled by draw_index; clicks and
		// scrolling inside it must not move or zoom the map
		const index = L.control({ position: "bottomright" });
		index.onAdd = () => {
			const div = L.DomUtil.create("div", "km-index");
			L.DomEvent.disableClickPropagation(div);
			L.DomEvent.disableScrollPropagation(div);
			return div;
		};
		index.addTo(this.map);
		this.$index = $(index.getContainer());

		// 2026-10-27: Add Route drawing (start_draw): the route being drawn, its toolbar, and
		// clicks on the map or on any line / pin adding a point; popups stay shut while drawing
		this.draft_layer = L.featureGroup().addTo(this.map);
		const bar = L.control({ position: "topleft" });
		bar.onAdd = () => {
			const div = L.DomUtil.create("div", "km-draw");
			L.DomEvent.disableClickPropagation(div);
			div.innerHTML = `<span class="msg"></span>
				<button class="btn btn-xs btn-default undo">${__("Undo")}</button>
				<button class="btn btn-xs btn-primary finish">${__("Finish")}</button>
				<button class="btn btn-xs btn-default cancel">${__("Cancel")}</button>`;
			return div;
		};
		bar.addTo(this.map);
		this.$draw = $(bar.getContainer()).hide();
		this.$draw.find(".undo").on("click", () => this.draw_undo());
		this.$draw.find(".finish").on("click", () => this.finish_draw());
		this.$draw.find(".cancel").on("click", () => this.cancel_draw());
		const on_click = (e) => this.draw_click(e);
		this.map.on("click", on_click);
		for (const layer of [this.routes_layer, this.points_layer, this.faults_layer]) layer.on("click", on_click);
		this.map.on("popupopen", (e) => { if (this.drawing) this.map.closePopup(e.popup); });
	}

	// Date: 2026-10-27
	// Add Route: draw one route by clicking points on the map, then save it as a KMZ Route
	// (kmz_map.add_route), so a single new route needs no KMZ file. Clicking a pin puts the point
	// exactly on it, and the first / last pin clicked fill the name ("A to B") and GIS Node.
	start_draw() {
		if (this.drawing) return;
		this.drawing = { pts: [], pins: [] };
		this.map.closePopup();
		this.map.doubleClickZoom.disable(); // a quick second click adds a point instead of zooming
		$(this.map.getContainer()).css("cursor", "crosshair");
		this.$draw.show();
		this.draw_draft();
	}

	// e: a click on the map or on a line / pin (the same click can arrive through both)
	draw_click(e) {
		if (!this.drawing || e.originalEvent === this.drawing.last) return;
		this.drawing.last = e.originalEvent;
		const pin = e.propagatedFrom && e.propagatedFrom._km_title != null ? e.propagatedFrom : null;
		this.drawing.pts.push(pin ? pin.getLatLng() : e.latlng);
		this.drawing.pins.push(pin ? { title: pin._km_title, gis: pin._km_gis } : null);
		this.draw_draft();
	}

	draw_undo() {
		if (!this.drawing) return;
		this.drawing.pts.pop();
		this.drawing.pins.pop();
		this.draw_draft();
	}

	draw_length() {
		const p = this.drawing.pts;
		let m = 0;
		for (let i = 1; i < p.length; i++) m += this.map.distance(p[i - 1], p[i]);
		return m;
	}

	draw_draft() {
		this.draft_layer.clearLayers();
		const p = this.drawing.pts;
		if (p.length > 1) L.polyline(p, { color: "#111827", weight: 4, dashArray: "8 6", interactive: false }).addTo(this.draft_layer);
		p.forEach((ll, i) => L.circleMarker(ll, { radius: 5, color: "#111827", weight: 2, fillColor: i ? "#ffffff" : "#16a34a",
			fillOpacity: 1, interactive: false }).addTo(this.draft_layer));
		this.$draw.find(".msg").text(p.length
			? __("{0} points · {1} m", [p.length, format_number(this.draw_length(), null, 0)])
			: __("Click on the map to add points (click a pin to start / end on it)"));
		this.$draw.find(".undo").prop("disabled", !p.length);
		this.$draw.find(".finish").prop("disabled", p.length < 2);
	}

	cancel_draw() {
		this.drawing = null;
		this.draft_layer.clearLayers();
		this.map.doubleClickZoom.enable();
		$(this.map.getContainer()).css("cursor", "");
		this.$draw.hide();
	}

	finish_draw() {
		const dr = this.drawing;
		if (!dr || dr.pts.length < 2) return;
		const first = dr.pins[0], last = dr.pins[dr.pins.length - 1];
		const name = first && last && dr.pins.length > 1 ? `${first.title} to ${last.title}` : "";
		const d = new frappe.ui.Dialog({
			title: __("Save Route"),
			fields: [
				{ fieldname: "route_name", label: __("Route Name"), fieldtype: "Data", reqd: 1, default: name,
					description: __("e.g. Building A to Building B") },
				{ fieldname: "gis", label: __("GIS Node"), fieldtype: "Link", options: "GIS Node",
					default: this.f.gis.get_value() || (first && first.gis) || (last && last.gis) || "" },
				{ fieldname: "site", label: __("Site"), fieldtype: "Link", options: "Site" },
				{ fieldname: "info", fieldtype: "HTML", options: `<div class="text-muted small">${
					__("{0} points · {1} m", [dr.pts.length, format_number(this.draw_length(), null, 1)])}</div>` },
			],
			primary_action_label: __("Save"),
			primary_action: async (v) => {
				const r = await frappe.xcall(KM_METHOD + "add_route", {
					route_name: v.route_name, gis: v.gis || null, site: v.site || null,
					coords: JSON.stringify(dr.pts.map((ll) => [ll.lat, ll.lng])),
				});
				d.hide();
				this.cancel_draw();
				frappe.show_alert({ message: __("Route saved ({0} m)", [format_number(r.length_m, null, 1)]), indicator: "green" });
				this.refresh(false); // keep the current view
			},
		});
		d.show();
	}

	// Date: 2026-10-27
	// Assign Nodes: routes / pins with no GIS Node get the node of the closest matched row within
	// the chosen distance (kmz_map.preview_nearest / apply_nearest). Preview first, then Assign;
	// "unsure" rows (another node about as close) are only assigned when ticked. Every assigned
	// row is Matched By "Nearest Node", so Undo takes them all back.
	assign_nodes() {
		let d; // the dialog (made below); a field's change can fire while it is being built
		const args = () => {
			const v = d.get_values(true);
			return { max_m: v.max_m || 200, include_pins: v.include_pins ? 1 : 0, include_unsure: v.include_unsure ? 1 : 0 };
		};
		let previewed = null; // the args of the preview on screen; a change of input needs a new preview
		const reset = () => { previewed = null; if (d) d.set_primary_action(__("Preview"), preview); };
		const preview = async () => {
			const a = args();
			d.fields_dict.result.$wrapper.html(`<div class="text-muted">${__("Working it out... (up to 30 s)")}</div>`);
			const p = await frappe.xcall(KM_METHOD + "preview_nearest", a);
			previewed = a;
			const n = a.include_unsure ? p.found : p.sure;
			const rows = p.rows.map((r) => `<tr class="${r.unsure ? "text-warning" : ""}">
				<td>${r.doctype === "KMZ Route" ? __("Route") : __("Pin")}</td>
				<td><a href="/app/${frappe.router.slug(r.doctype)}/${encodeURIComponent(r.name)}" target="_blank">${km_esc(r.title)}</a></td>
				<td><b>${km_esc(r.gis)}</b> · ${r.m} m</td>
				<td>${r.other ? `${km_esc(r.other)} · ${r.other_m} m` : "-"}</td>
				<td>${r.unsure ? __("Unsure") : __("Sure")}</td></tr>`).join("");
			d.fields_dict.result.$wrapper.html(`
				<div>${__("{0} rows have no GIS Node; {1} have a matched row within {2} m: {3} sure, {4} unsure ({5} routes).",
					[p.without_node, p.found, a.max_m, p.sure, p.unsure, p.routes])}</div>
				<div class="text-muted small" style="margin:4px 0">${__("Most per node")}: ${p.by_node.slice(0, 12)
					.map(([g, c]) => `${km_esc(g)} ${c}`).join(" · ")}</div>
				${p.already ? `<div class="text-muted small">${__("{0} rows already have a Nearest Node from before.", [p.already])}</div>` : ""}
				<div class="text-muted small" style="margin-top:6px">${__("First {0} rows, unsure first (Unsure: the next node is almost as close):",
					[p.rows.length])}</div>
				<div style="max-height:320px;overflow:auto"><table class="table table-sm small" style="margin:0">
					<thead><tr><th>${__("Type")}</th><th>${__("Name")}</th><th>${__("Nearest node")}</th>
					<th>${__("Next node")}</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`);
			d.set_primary_action(__("Assign {0}", [format_number(n)]), assign);
		};
		const assign = () => {
			if (!previewed) return preview();
			frappe.confirm(__("Give these rows their nearest GIS Node? It can be undone with Undo."), async () => {
				const r = await frappe.xcall(KM_METHOD + "apply_nearest", previewed);
				d.hide();
				frappe.show_alert({ message: __("{0} routes / pins got a GIS Node", [format_number(r.assigned)]), indicator: "green" });
				this.refresh(false);
			});
		};
		d = new frappe.ui.Dialog({
			title: __("Assign Nodes by Distance"),
			size: "large",
			fields: [
				{ fieldname: "max_m", label: __("Within (metres)"), fieldtype: "Int", default: 200, change: reset,
					description: __("Up to 1000. A route / pin with no GIS Node gets the node of the closest route or pin that was matched by Node Name or Building Name.") },
				{ fieldname: "cb", fieldtype: "Column Break" },
				{ fieldname: "include_pins", label: __("Pins too (not only routes)"), fieldtype: "Check", default: 1, change: reset },
				{ fieldname: "include_unsure", label: __("Also assign unsure rows"), fieldtype: "Check", default: 0, change: reset },
				{ fieldname: "sb", fieldtype: "Section Break" },
				{ fieldname: "result", fieldtype: "HTML" },
			],
			secondary_action_label: __("Undo All"),
			secondary_action: () => frappe.confirm(__("Take the GIS Node off every row that got it from Assign Nodes?"), async () => {
				const r = await frappe.xcall(KM_METHOD + "undo_nearest");
				d.hide();
				frappe.show_alert({ message: __("Undone: {0} routes, {1} pins", [r["KMZ Route"], r["KMZ Point"]]), indicator: "orange" });
				this.refresh(false);
			}),
		});
		reset();
		d.show();
	}

	// Date: 2026-10-27
	// What every colour / symbol on the map means. Pin types show their count and hide / show
	// when clicked; the complaint part only shows while "Show open complaints" is ticked.
	draw_index(data, live) {
		const counts = {};
		for (const p of data.points) {
			const t = km_pin_type(p[2]);
			if (t) counts[t.key] = (counts[t.key] || 0) + 1;
		}
		const it = (sym, label, extra = "") => `<div class="it ${extra}">${sym}<span>${label}</span></div>`;
		const types = KM_PIN_TYPES.filter((t) => counts[t.key]).map((t) =>
			`<div class="it pt ${this.hidden_types.has(t.key) ? "off" : ""}" data-type="${t.key}" title="${__("Click to hide / show")}">
				<span class="dot" style="--sw:${t.colour}"></span><span>${t.label}</span><span class="c">${counts[t.key]}</span></div>`).join("");
		this.$index.toggleClass("closed", !!this.index_closed).html(`
			<div class="hd"><span>${__("Index")}</span><span>${this.index_closed ? "▸" : "▾"}</span></div>
			<div class="bd">
				${types ? `<div class="sec">${__("Pins (click to hide)")}</div>${types}` : ""}
				<div class="sec">${__("Lines")}</div>
				${it(`<span class="ln" style="--sw:linear-gradient(90deg,${KM_PALETTE.slice(0, 4).join(",")})"></span>`, __("Route, coloured by GIS Node"))}
				${it(`<span class="ln" style="--sw:repeating-linear-gradient(90deg,${KM_UNMATCHED} 0 6px,transparent 6px 9px)"></span>`, __("Route with no GIS Node (dashed)"))}
				<div class="sec">${__("Node")}</div>
				${it(`<span class="dot" style="--sw:${KM_PALETTE[0]};border-color:var(--ev-text);width:14px;height:14px"></span>`, __("Node pin (labelled with GIS code)"))}
				${live ? `<div class="sec">${__("Open complaints")}</div>
				${it(`<span class="bang">!</span>`, __("Open complaint"))}
				${it(`<span class="dot" style="--sw:${KM_PALETTE[0]};border:3px solid ${KM_DOWN};width:15px;height:15px"></span>`, __("Node with open complaints"))}
				${it(`<span class="ln thick" style="--sw:${KM_DOWN}"></span>`, __("Down: site with an open complaint"))}
				${it(`<span class="ln thick" style="--sw:${KM_AFFECTED}"></span>`, __("Affected: fed through a down site"))}` : ""}
			</div>`);
		this.$index.find(".hd").on("click", () => { this.index_closed = !this.index_closed; this.draw_index(data, live); });
		this.$index.find(".pt").on("click", (e) => {
			const key = $(e.currentTarget).attr("data-type");
			this.hidden_types.has(key) ? this.hidden_types.delete(key) : this.hidden_types.add(key);
			this.draw_map(this.data, false);
		});
	}

	// Date: 2026-10-26
	async refresh(fit = true) {
		const v = this.values();
		this.$(".km-note").text(__("Loading..."));
		const data = await frappe.xcall(KM_METHOD + "get_map_data", v);
		this.data = data;
		this.draw_kpis(data.summary, data.faults, v.gis);
		this.draw_map(data, fit);
		this.draw_nodes(data.by_node, v.gis, data.faults);
		const drawn = __("{0} routes and {1} pins on the map.", [data.routes.length, data.points.length]);
		this.$(".km-note").text(data.limit_hit
			? drawn + " " + __("Only the first ones are drawn: pick a GIS Node, KMZ File or KMZ Path to see the rest.")
			: drawn);
	}

	draw_kpis(s, faults, gis) {
		const tile = (value, label, cls = "") => `<div class="km-kpi ${cls}"><div class="v">${value}</div><div class="l">${label}</div></div>`;
		this.$(".km-kpis").html(
			tile(format_number(s.routes), __("Routes")) +
			tile(format_number(s.length_km, null, 2), __("Route km"), "t-green") +
			tile(format_number(s.points), __("Pins"), "t-orange") +
			tile(format_number(s.nodes), __("GIS Nodes"), "t-purple") +
			tile(format_number(s.not_matched), __("No Node"), "t-gray") +
			// with a node chosen, only that node's complaints
			tile(format_number(gis ? faults.nodes[gis] || 0 : faults.markers.length), __("Open Complaints"), "t-red"));
	}

	// Date: 2026-10-26 (2026-10-27: details fetched when the popup opens)
	popup_html(doctype, r) {
		const link = (dt, name, label) => name
			? `<a href="/app/${frappe.router.slug(dt)}/${encodeURIComponent(name)}">${km_esc(label || name)}</a>` : "-";
		const is_route = doctype === "KMZ Route";
		const extra = is_route
			? `<div>${__("Length")}: ${format_number(r.length_m, null, 1)} m</div>`
			: `<div>${format_number(r.latitude, null, 6)}, ${format_number(r.longitude, null, 6)}</div>`;
		return `<div class="km-pop">
			<b>${km_esc(is_route ? r.route_name : r.point_name)}</b> · ${link(doctype, r.name, __("open"))}
			<div>${__("GIS Node")}: ${r.gis ? link("GIS Node", r.gis) : __("not matched")}</div>
			${extra}
			${r.custom_site ? `<div>${__("Site")}: ${link("Site", r.custom_site)}</div>` : ""}
			<div>${__("KMZ File")}: ${km_esc(r.source_file || "-")}</div>
			<div class="path">${__("KMZ Path")}: ${km_esc(r.custom_kmz_path || r.node_folder || "-")}</div>
			${r.custom_kmz_matched_by ? `<div class="path">${__("Matched by")}: ${km_esc(r.custom_kmz_matched_by)}</div>` : ""}
		</div>`;
	}

	bind_popup(layer, doctype, name, title) {
		layer.bindPopup(`<div class="km-pop"><b>${km_esc(title)}</b><div class="path">${__("Loading...")}</div></div>`);
		layer.on("popupopen", async () => {
			if (layer._km_loaded) return;
			const r = await frappe.xcall(KM_METHOD + "get_item", { doctype, name });
			layer._km_loaded = true;
			layer.setPopupContent(this.popup_html(doctype, r));
		});
	}

	// Date: 2026-10-26 (2026-10-27: open complaints drawn on top, see fault_overlay in kmz_map.py)
	draw_map(data, fit = true) {
		this.routes_layer.clearLayers();
		this.points_layer.clearLayers();
		this.faults_layer.clearLayers();
		const f = data.faults;
		const live = !!this.show_faults.get_value();
		const down = new Set(live ? f.down_sites : []);
		const affected = new Set(live ? f.affected_sites : []);
		// red / orange for a site that is down / fed through a down site, else the node's colour
		const state = (site) => (site && down.has(site) ? "down" : site && affected.has(site) ? "affected" : null);
		const tip = { down: __("Down: open complaint on this site"), affected: __("Affected: fed through a site that is down") };
		const node_pins = {};
		// rows are short arrays (kmz_map.py): route [name, gis, title, coords, site], pin [name, gis, title, lat, lon, site]
		for (const [name, gis, title, coords, site] of data.routes) {
			const st = state(site);
			const line = L.polyline(coords, st
				? { color: st === "down" ? KM_DOWN : KM_AFFECTED, weight: 6, opacity: 0.95 }
				// 2026-10-27: a route with no GIS Node is dashed, so it never looks like a node's colour
				: { color: km_colour(gis), weight: 3, opacity: 0.85, dashArray: gis ? null : "7 5" }).addTo(st ? this.faults_layer : this.routes_layer);
			if (st) line.bindTooltip(tip[st], { sticky: true });
			this.bind_popup(line, "KMZ Route", name, title);
		}
		for (const [name, gis, title, lat, lon, site] of data.points) {
			// the node's own pin (named with its GIS code, e.g. "C1U Node") is drawn larger
			const is_node = gis && (title || "").trim().toUpperCase().replace(/\s+NODE$/, "") === gis;
			const st = state(site);
			// a node with open complaints gets a thick red ring and a "⚠ V0N · 2 open" label
			const node_faults = is_node && live ? f.nodes[gis] || 0 : 0;
			// 2026-10-27: colour by pin type; the node pin keeps its node colour; a type hidden in the legend is skipped
			const type = is_node ? null : km_pin_type(title);
			if (type && !st && this.hidden_types.has(type.key)) continue;
			const fill = st === "down" ? KM_DOWN : st === "affected" ? KM_AFFECTED : type ? type.colour : km_colour(gis);
			const pin = L.circleMarker([lat, lon], {
				radius: is_node ? (node_faults ? 11 : 8) : st ? 6 : 5,
				color: node_faults ? KM_DOWN : is_node ? "#111827" : "#ffffff", weight: node_faults ? 4 : is_node ? 2 : 1.5,
				fillColor: fill, fillOpacity: 0.95,
			}).addTo(st || node_faults ? this.faults_layer : this.points_layer);
			pin._km_title = title || ""; // Add Route: a point clicked on this pin snaps to it and names the route
			pin._km_gis = gis;
			if (is_node) {
				node_pins[gis] = [lat, lon];
				pin.bindTooltip(node_faults ? `⚠ ${km_esc(gis)} · ${__("{0} open", [node_faults])}` : km_esc(gis),
					{ permanent: true, direction: "top", offset: [0, -6] });
			} else {
				// 2026-10-28: hover shows the pin's own name (e.g. the building), not its type; type if unnamed
				const label = km_esc((title || "").trim() || type.label);
				pin.bindTooltip(st ? `${label}: ${tip[st]}` : label);
			}
			this.bind_popup(pin, "KMZ Point", name, title);
		}
		// one pulsing marker per open complaint: its own position, else its site's pin, else its node's pin
		if (live) {
			for (const [name, lat, lon, label, wf_state, node, site] of f.markers) {
				const at = lat && lon ? [lat, lon] : node_pins[node];
				if (!at) continue;
				L.marker(at, {
					icon: L.divIcon({ className: "", html: `<div class="km-fault-icon">!</div>`, iconSize: [26, 26], iconAnchor: [13, 13] }),
					zIndexOffset: 1000,
				}).bindPopup(`<div class="km-pop"><b>${km_esc(label || name)}</b>
					<div><a href="/app/complaint-information/${encodeURIComponent(name)}">${km_esc(name)}</a> · ${km_esc(wf_state)}</div>
					${node ? `<div>${__("GIS Node")}: ${km_esc(node)}</div>` : ""}
					${site ? `<div>${__("Site")}: <a href="/app/site/${encodeURIComponent(site)}">${km_esc(site)}</a></div>` : ""}
				</div>`).addTo(this.faults_layer);
			}
		}
		this.faults_layer.bringToFront();
		this.draw_index(data, live);
		if (fit) {
			const bounds = L.featureGroup([this.routes_layer, this.points_layer, this.faults_layer]).getBounds();
			if (bounds.isValid()) this.map.fitBounds(bounds, { padding: [20, 20], maxZoom: 17 });
		}
		setTimeout(() => this.map.invalidateSize(), 50);
	}

	draw_nodes(rows, active, faults) {
		const $list = this.$(".km-nodes");
		if (!rows.length) {
			$list.html(`<div class="text-muted small" style="padding:8px">${__("No KMZ data for these filters. Use Upload KMZ to add a file.")}</div>`);
			return;
		}
		$list.html(rows.map((r) => `<div class="km-node ${r.gis && r.gis === active ? "active" : ""}" data-gis="${km_esc(r.gis)}">
			<span class="dot" style="background:${km_colour(r.gis)}"></span>
			<span class="n">${km_esc(r.gis || __("No Node"))}</span>
			${r.gis && faults.nodes[r.gis] ? `<span class="pill" title="${__("Open complaints")}">${faults.nodes[r.gis]}</span>` : ""}
			<span class="c">${__("{0} routes · {1} pins", [r.routes, r.points])}</span></div>`).join(""));
		$list.find(".km-node").on("click", (e) => {
			const gis = $(e.currentTarget).attr("data-gis");
			if (gis) {
				this.set_node(gis === active ? "" : gis);
			} else {
				// "No Node": the rows the KMZ Upload could not match
				this.syncing = true;
				this.f.matched_by.set_value("Not Matched").then(() => { this.syncing = false; this.refresh(); });
			}
		});
	}
}
