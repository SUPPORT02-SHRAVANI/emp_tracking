// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt

// ---------------------------------------------------------------------------------------------
// Team Map (Desk page /app/team-map). Created 2026-11-28 (user: "make new map for team assignment view").
//
// How this file works
//   Which EVisions team covers what, on one map (data: team_map.get_team_map):
//     - each team area's boundary, filled in its Team Colour (Maintenance Team > Team Colour);
//     - Network Links as dots in the colour of the team they are assigned to; a link assigned to a
//       team of another area gets a red ring ("Links": all / only other-area ones / hidden);
//     - GIS Nodes (their own KMZ pin) in their area team's colour, labelled with the GIS code;
//     - open complaints as "!" pins in their team's colour.
//   On the right, one card per team (area, manager, leader, splicers / riders, localities, links,
//   links of another area, open complaints). Clicking a card zooms to its area and fades the
//   others; "All teams" shows everything again. "Open team" opens the Maintenance Team form.
//   route_options {team}: opens zoomed to that team (Maintenance Team "View team on map").
//   2026-11-28: cards show the Area Manager only (no Team Leader, user's decision).
// ---------------------------------------------------------------------------------------------

const TM_METHOD = "emp_tracking.emp_tracking.page.team_map.team_map.get_team_map";
const TM_OTHER = "#9ca3af"; // links / complaints of a vendor or no team

frappe.pages["team-map"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Team Map"), single_column: true });
	wrapper.tm = new TeamMap(page);
};

frappe.pages["team-map"].on_page_show = function (wrapper) {
	if (!wrapper.tm) return;
	// a Maintenance Team form's "View team on map" sends its team (used once the data is in)
	if (frappe.route_options && frappe.route_options.team) {
		wrapper.tm.want_team = frappe.route_options.team;
		frappe.route_options = null;
		wrapper.tm.apply_wanted();
	}
	if (wrapper.tm.map) setTimeout(() => wrapper.tm.map.invalidateSize(), 50);
};

const TM_STYLE = `<style>
	.tm-wrap { display:grid; grid-template-columns: 1fr 340px; gap:16px; }
	@media (max-width: 991px) { .tm-wrap { grid-template-columns: 1fr; } }
	.tm-map { height: calc(100vh - 230px); min-height: 460px; border:1px solid var(--border-color); border-radius:12px; }
	.tm-bar { display:flex; flex-wrap:wrap; gap:16px; align-items:center; margin-bottom:12px; font-size:var(--text-sm); }
	.tm-bar .seg { display:inline-flex; border:1px solid var(--border-color); border-radius:8px; overflow:hidden; }
	.tm-bar .seg button { border:0; background:var(--fg-color); padding:4px 10px; color:var(--text-muted); }
	.tm-bar .seg button.on { background:var(--text-color); color:var(--fg-color); }
	.tm-bar label { display:inline-flex; gap:6px; align-items:center; margin:0; color:var(--text-color); }
	.tm-side { display:flex; flex-direction:column; gap:10px; max-height: calc(100vh - 230px); overflow:auto; }
	.tm-card { border:1px solid var(--border-color); border-radius:12px; padding:12px 14px; cursor:pointer; background:var(--fg-color);
		border-left:5px solid var(--tc); }
	.tm-card.on { box-shadow:0 0 0 2px var(--tc); }
	.tm-card.faded { opacity:.45; }
	.tm-card .hd { display:flex; justify-content:space-between; align-items:center; gap:8px; }
	.tm-card .hd b { font-size:var(--text-md); }
	.tm-card .sub { color:var(--text-muted); font-size:var(--text-sm); margin:2px 0 8px; }
	.tm-card .nums { display:grid; grid-template-columns: repeat(3, 1fr); gap:6px; }
	.tm-card .nums div { font-size:var(--text-xs); color:var(--text-muted); }
	.tm-card .nums b { display:block; font-size:var(--text-md); color:var(--text-color); }
	.tm-card .warn b { color:var(--red-600, #dc2626); }
	.tm-all { align-self:flex-start; }
	.tm-pin { font-size:10px; font-weight:600; padding:1px 4px; border-radius:4px; background:#fff; border:1px solid #111827; color:#111827; white-space:nowrap; }
	.tm-bang { width:20px; height:20px; border-radius:50%; color:#fff; font-weight:700; font-size:12px; display:flex;
		align-items:center; justify-content:center; border:2px solid #fff; box-shadow:0 0 0 1px rgba(0,0,0,.35); }
	.tm-legend { background:var(--fg-color); padding:8px 10px; border-radius:8px; font-size:12px; line-height:1.7;
		box-shadow:0 1px 4px rgba(0,0,0,.2); }
	.tm-legend i { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; vertical-align:-1px; }
</style>`;

class TeamMap {
	constructor(page) {
		this.page = page;
		this.links_mode = "all";
		this.show_nodes = true;
		this.show_complaints = true;
		this.focus = null;
		$(TM_STYLE + `
			<div class="tm-bar">
				<span>${__("Links")}:</span>
				<span class="seg" data-seg="links">
					<button data-v="all" class="on">${__("All")}</button>
					<button data-v="other">${__("Other area only")}</button>
					<button data-v="none">${__("Hide")}</button>
				</span>
				<label><input type="checkbox" data-t="nodes" checked> ${__("GIS Nodes")}</label>
				<label><input type="checkbox" data-t="complaints" checked> ${__("Open complaints")}</label>
				<span class="text-muted tm-note"></span>
			</div>
			<div class="tm-wrap"><div class="tm-map"></div><div class="tm-side"></div></div>`).appendTo(page.main);
		this.$ = (s) => $(page.main).find(s);
		this.$(".seg button").on("click", (e) => {
			this.links_mode = $(e.currentTarget).attr("data-v");
			this.$(".seg button").removeClass("on").filter(`[data-v="${this.links_mode}"]`).addClass("on");
			this.draw();
		});
		this.$("input[data-t]").on("change", (e) => {
			this["show_" + $(e.currentTarget).attr("data-t")] = e.currentTarget.checked;
			this.draw();
		});
		page.set_primary_action(__("Refresh"), () => this.load(), "refresh");
		page.add_inner_button(__("Maintenance Teams"), () => frappe.set_route("List", "Maintenance Team"));
		page.add_inner_button(__("Areas"), () => frappe.set_route("Tree", "Area"));
		Promise.all([frappe.require("leaflet.bundle.js"), frappe.require("leaflet.bundle.css")]).then(() => {
			this.make_map();
			this.load();
		});
	}

	make_map() {
		const d = frappe.utils.map_defaults;
		L.Icon.Default.imagePath = d.image_path;
		this.map = L.map(this.$(".tm-map")[0], { preferCanvas: true, maxZoom: 22 }).setView(d.center, 11);
		const deep = (o) => Object.assign({}, o, { maxZoom: 22, maxNativeZoom: 19 });
		const street = L.tileLayer(d.tiles.default_tile.url, deep(d.tiles.default_tile.options)).addTo(this.map);
		const satellite = L.tileLayer(d.tiles.satellite_tile.url, deep(d.tiles.satellite_tile.options));
		L.control.layers({ [__("Street")]: street, [__("Satellite")]: satellite }).addTo(this.map);
		this.areas_layer = L.featureGroup().addTo(this.map);
		this.links_layer = L.featureGroup().addTo(this.map);
		this.nodes_layer = L.featureGroup().addTo(this.map);
		this.complaints_layer = L.featureGroup().addTo(this.map);
		const legend = L.control({ position: "bottomleft" });
		legend.onAdd = () => {
			const div = L.DomUtil.create("div", "tm-legend");
			div.innerHTML = `<div><i style="background:#2563eb"></i>${__("Link / node: dot in its team's colour")}</div>
				<div><i style="background:#fff;border:2px solid #dc2626"></i>${__("Link assigned to a team of another area")}</div>
				<div><i style="background:${TM_OTHER}"></i>${__("Vendor or no team")}</div>
				<div><span class="tm-bang" style="display:inline-flex;width:14px;height:14px;font-size:9px;background:#dc2626;margin-right:6px">!</span>${__("Open complaint")}</div>`;
			return div;
		};
		legend.addTo(this.map);
	}

	async load() {
		this.$(".tm-note").text(__("Loading..."));
		this.data = await frappe.xcall(TM_METHOD);
		this.colour = {};
		this.data.teams.forEach((t) => (this.colour[t.name] = t.colour));
		this.draw_cards();
		this.draw(true);
		this.apply_wanted();
	}

	// zoom to the team asked for by a Maintenance Team form, once the data has loaded
	apply_wanted() {
		if (!this.want_team || !this.data) return;
		const team = this.data.teams.find((t) => t.name === this.want_team);
		this.want_team = null;
		if (team) {
			this.focus = null;
			this.pick(team);
		}
	}

	team_colour(team) {
		return this.colour[team] || TM_OTHER;
	}

	// boundaries, links, nodes and complaints; with a team picked, only that team's are strong
	draw(fit = false) {
		const d = this.data;
		if (!d) return;
		[this.areas_layer, this.links_layer, this.nodes_layer, this.complaints_layer].forEach((l) => l.clearLayers());
		const focus = this.focus;
		const dim = (team) => focus && team !== focus.name;
		const esc = frappe.utils.escape_html;

		d.teams.forEach((t) => {
			const ring = d.boundaries[t.area];
			if (!ring) return;
			const on = !focus || focus.name === t.name;
			L.polygon(ring, { color: t.colour, weight: on ? 3 : 1.5, opacity: on ? 0.95 : 0.35, fillColor: t.colour,
				fillOpacity: on ? 0.12 : 0.03 })
				.bindTooltip(`<b>${esc(t.area)} · ${esc(t.name)}</b><br>${__("Area Manager")}: ${esc(t.manager || "-")}`, { sticky: true })
				.on("click", () => this.pick(t))
				.addTo(this.areas_layer);
		});

		let shown = 0, other = 0;
		if (this.links_mode !== "none") {
			for (const [lat, lon, team, area_team, linkid] of d.links) {
				const mismatch = team && area_team && team !== area_team && this.colour[team];
				if (mismatch) other++;
				if (this.links_mode === "other" && !mismatch) continue;
				if (focus && team !== focus.name && area_team !== focus.name) continue;
				shown++;
				L.circleMarker([lat, lon], {
					radius: mismatch ? 5 : 3.5, weight: mismatch ? 2 : 0.5,
					color: mismatch ? "#dc2626" : "#ffffff", fillColor: this.team_colour(team),
					fillOpacity: dim(team) ? 0.25 : 0.9,
				}).bindTooltip(`${esc(linkid)} · ${esc(team || __("no team"))}` +
					(mismatch ? `<br><b style="color:#dc2626">${__("Area is {0}'s", [esc(area_team)])}</b>` : ""))
					.on("click", () => frappe.set_route("Form", "Network Link", linkid))
					.addTo(this.links_layer);
			}
		}
		if (this.show_nodes) {
			for (const [lat, lon, code, team] of d.nodes) {
				if (focus && team !== focus.name) continue;
				L.circleMarker([lat, lon], { radius: 7, weight: 2, color: "#111827", fillColor: this.team_colour(team), fillOpacity: 1 })
					.bindTooltip(`<b>${esc(code)}</b> · ${esc(team || __("no team area"))}`)
					.on("click", () => frappe.set_route("Form", "GIS Node", code))
					.addTo(this.nodes_layer);
			}
		}
		if (this.show_complaints) {
			for (const [lat, lon, team, area_team, name, title, state] of d.complaints) {
				if (focus && team !== focus.name && area_team !== focus.name) continue;
				L.marker([lat, lon], {
					icon: L.divIcon({ className: "", iconSize: [20, 20], iconAnchor: [10, 10],
						html: `<div class="tm-bang" style="background:${this.team_colour(team)}">!</div>` }),
					zIndexOffset: 1000,
				}).bindTooltip(`<b>${esc(title || name)}</b><br>${esc(name)} · ${esc(state)}<br>${__("Team")}: ${esc(team || "-")}`)
					.on("click", () => frappe.set_route("Form", "Complaint Information", name))
					.addTo(this.complaints_layer);
			}
		}
		this.$(".tm-note").text(__("{0} links shown · {1} assigned to a team of another area", [shown, other]));
		if (fit || focus) {
			const target = focus && d.boundaries[focus.area] ? L.polygon(d.boundaries[focus.area]).getBounds() : this.areas_layer.getBounds();
			if (target.isValid()) this.map.fitBounds(target, { padding: [20, 20] });
		}
		setTimeout(() => this.map.invalidateSize(), 50);
	}

	draw_cards() {
		const esc = frappe.utils.escape_html;
		const $side = this.$(".tm-side").empty();
		$(`<button class="btn btn-xs btn-default tm-all">${__("All teams")}</button>`).on("click", () => this.pick(null)).appendTo($side);
		this.data.teams.forEach((t) => {
			const $c = $(`<div class="tm-card" style="--tc:${t.colour}">
				<div class="hd"><b>${esc(t.name)}</b><span class="text-muted">${esc(t.area)}</span></div>
				<div class="sub">${__("Area Manager")}: ${esc(t.manager || "-")}${t.manager_no ? " · " + esc(t.manager_no) : ""}</div>
				<div class="nums">
					<div><b>${t.splicers}</b>${__("Splicers")}</div>
					<div><b>${t.riders}</b>${__("Riders")}</div>
					<div><b>${t.places}</b>${__("Areas")}</div>
					<div><b>${t.links}</b>${__("Links")}</div>
					<div class="${t.links_other_area ? "warn" : ""}"><b>${t.links_other_area}</b>${__("Links of other area")}</div>
					<div class="${t.open ? "warn" : ""}"><b>${t.open}</b>${__("Open complaints")}</div>
				</div>
				<div style="margin-top:8px"><a class="tm-open small" href="/app/maintenance-team/${encodeURIComponent(t.name)}">${__("Open team")} →</a></div>
			</div>`);
			$c.on("click", (e) => { if (!$(e.target).closest(".tm-open").length) this.pick(t); });
			$c.attr("data-team", t.name).appendTo($side);
		});
	}

	// one team in focus (zoom, others faded), or all
	pick(team) {
		this.focus = team && (!this.focus || this.focus.name !== team.name) ? team : null;
		this.$(".tm-card").each((i, el) => {
			const name = $(el).attr("data-team");
			$(el).toggleClass("on", !!this.focus && name === this.focus.name).toggleClass("faded", !!this.focus && name !== this.focus.name);
		});
		// the picked team's card into view (TEAM 6 is below the fold)
		const $on = this.$(".tm-card.on");
		if ($on.length) $on[0].scrollIntoView({ behavior: "smooth", block: "nearest" });
		this.draw(!this.focus);
	}
}
