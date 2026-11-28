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
//   2026-11-27  "Map contents" tab: the KMZ folders as a tree, like Google Earth (folders inside
//               folders, pins and lines inside them). A folder click zooms to it, a pin / line
//               click zooms to it and opens its popup, the eye hides / shows (draw_tree, bind_tree).
//               The old node list is the "GIS Nodes" tab. Zoom now goes to 22 (KM_MAX_ZOOM; tiles
//               enlarged past level 19), as the map used to stop at 18 (user's request).
//   2026-11-27  Search box on "Map contents" (like Google Earth's Places search): typing filters the
//               tree to matching folders / pins / lines and opens the folders on the way to them;
//               Enter zooms to everything found (set_search, search_tree).
//   2026-11-27  KMZ Polygons (the KMZ's shapes: area remarks, DSA / cluster and team boundaries)
//               drawn under the routes in their Google Earth colours, in the tree and the search,
//               and as a "Shapes" layer (user's report: not everything in the KMZ was on the map).
//   2026-11-28  Index from EVision Settings > Maps: corner or hidden, open / folded at start, rows
//               shown / hidden with their own labels; a changed colour is used on the map too.
//   2026-11-28  route_options {area}: opens on a team area (Maintenance Team "View team on map"),
//               with that area's boundary in the team's colour (kmz_map.py).
// ---------------------------------------------------------------------------------------------

const KM_METHOD = "emp_tracking.emp_tracking.page.kmz_map.kmz_map.";
// 2026-10-27: no purple / pink (looked like the fuchsia no-node colour) and no red (open complaints)
const KM_PALETTE = ["#2563eb", "#16a34a", "#ea580c", "#854d0e", "#0891b2", "#1e3a8a", "#ca8a04", "#4f46e5",
	"#334155", "#0d9488", "#4d7c0f", "#65a30d"];
// 2026-10-27: these three and KM_PIN_TYPES are replaced by KMZ Map Settings when the page loads
let KM_UNMATCHED = "#c026d3"; // fuchsia: rows with no GIS Node (2026-10-27: was grey, hard to see)
let KM_DOWN = "#dc2626"; // red: site with an open complaint
let KM_AFFECTED = "#f97316"; // orange: site fed through a down site
const KM_MAX_ZOOM = 22; // 2026-11-27: deepest zoom (tiles enlarged past level 19)
// 2026-11-27: icons of the "Map contents" tree (folder, pin, line, eye open / shut)
const KM_ICONS = {
	// 2026-11-27: a KMZ Polygon (shape) row in the tree
	shape: `<svg viewBox="0 0 24 24" fill="currentColor" fill-opacity=".2" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M4 8 11 3l9 5-2 11-11 2z"/></svg>`,
	folder: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>`,
	folder_open: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v1"/><path d="M3 19l3-8h16l-3 8z"/></svg>`,
	line: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="17" r="2"/><circle cx="19" cy="7" r="2"/><path d="M6.5 15.5 10 12l4 2 3.5-5.5"/></svg>`,
	eye: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>`,
	eye_off: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3l18 18"/><path d="M10.6 5.1A10.9 10.9 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.1M6.6 6.6A17.4 17.4 0 0 0 2 12s3.5 7 10 7a9.7 9.7 0 0 0 4.4-1"/></svg>`,
};
const KM_TREE_PAGE = 300; // rows shown per open folder before "Show more"

frappe.pages["kmz-map"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("KMZ Map"), single_column: true });
	wrapper.km = new KMZMap(page);
};

frappe.pages["kmz-map"].on_page_show = function (wrapper) {
	// 2026-11-28: on the first open the filters' choices are still loading (a value set now is lost);
	// the page's own load step reads route_options once they are in
	if (!wrapper.km || !wrapper.km.loaded) return;
	// a GIS Node form sends its node through route_options
	if (frappe.route_options && frappe.route_options.gis) {
		wrapper.km.set_node(frappe.route_options.gis);
		frappe.route_options = null;
	} else if (frappe.route_options && frappe.route_options.area) {
		// 2026-11-28: a Maintenance Team form sends its area
		wrapper.km.set_area(frappe.route_options.area);
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
.km-body { display:grid; grid-template-columns:1fr 320px; gap:12px; }
/* 2026-11-27: right panel tabs and the Google Earth style "Map contents" folder tree */
.km-tabs { display:flex; gap:4px; padding:0 2px 8px; border-bottom:1px solid var(--border-color); margin-bottom:6px; }
.km-tab { border:0; background:none; padding:4px 10px; border-radius:8px; font-size:13px; color:var(--text-muted); cursor:pointer; }
.km-tab.active { background:var(--control-bg); color:var(--text-color); font-weight:600; }
.km-search { display:flex; align-items:center; gap:6px; margin:0 2px 6px; }
.km-search input { flex:1; min-width:0; }
.km-search .km-found { font-size:11px; color:var(--text-muted); white-space:nowrap; }
.km-tree { max-height:72vh; overflow:auto; font-size:12.5px; }
.km-tr { display:flex; align-items:center; gap:6px; padding:3px 6px 3px 0; border-radius:6px; cursor:pointer; min-height:26px; }
.km-tr:hover { background:var(--control-bg); }
.km-tr .cr { width:16px; flex:none; text-align:center; color:var(--text-muted); font-size:10px; }
.km-tr .ic { width:16px; height:16px; flex:none; display:flex; align-items:center; justify-content:center; color:var(--text-muted); }
.km-tr .ic svg { width:15px; height:15px; }
.km-tr .lb { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--text-color); }
.km-tr .ct { font-size:11px; color:var(--text-muted); flex:none; }
.km-tr .eye { flex:none; width:22px; height:22px; display:flex; align-items:center; justify-content:center; border-radius:6px;
	color:var(--text-muted); }
.km-tr .eye:hover { background:var(--border-color); }
.km-tr .eye svg { width:14px; height:14px; }
.km-tr.off .lb, .km-tr.off .ic { opacity:.4; }
.km-tr .pin-dot { width:10px; height:10px; border-radius:50%; border:1.5px solid #fff; box-shadow:0 0 0 1px rgba(0,0,0,.25); }
.km-tr .more { color:var(--text-muted); font-style:italic; }
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
				<div class="km-card">
					<div class="km-tabs">
						<button class="km-tab active" data-tab="tree">${__("Map contents")}</button>
						<button class="km-tab" data-tab="nodes">${__("GIS Nodes")}</button>
					</div>
					<div class="km-pane" data-pane="tree">
						<div class="km-search">
							<input type="search" class="form-control input-xs" placeholder="${__("Search places (folder, building, ODF...)")}">
							<span class="km-found"></span>
						</div>
						<div class="km-tree"></div></div>
					<div class="km-pane" data-pane="nodes" style="display:none">
						<div class="text-muted small" style="padding:2px 8px 6px">${__("GIS Nodes (click to filter)")}</div>
						<div class="km-nodes"></div></div>
				</div>
			</div>`);
		this.$ = (sel) => $(page.body).find(sel);
		// 2026-11-27: folder tree state, kept across reloads of the map: open folders, hidden rows
		this.tree_open = new Set();
		this.hidden_rows = new Set();
		this.shown_rows = new Set(); // pins opened from the tree although their type is off in the Index
		this.$(".km-tab").on("click", (e) => {
			const tab = $(e.currentTarget).attr("data-tab");
			this.$(".km-tab").removeClass("active").filter(`[data-tab="${tab}"]`).addClass("active");
			this.$(".km-pane").hide().filter(`[data-pane="${tab}"]`).show();
		});
		this.bind_tree();
		// 2026-11-27: places search; waits 250 ms after typing so big trees are not re-searched per key
		this.search = null;
		let typing;
		this.$(".km-search input")
			.on("input", (e) => {
				clearTimeout(typing);
				typing = setTimeout(() => this.set_search(e.target.value), 250);
			})
			.on("keydown", (e) => {
				if (e.key !== "Enter") return;
				clearTimeout(typing);
				this.set_search(e.target.value);
				if (this.search) this.zoom_to(this.search.found);
			});
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
			} else if (frappe.route_options && frappe.route_options.area) {
				this.set_area(frappe.route_options.area);
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
		// 2026-11-28: Index settings (EVision Settings > Maps): position, open / folded, rows; a row
		// colour changed there also replaces the map's colour for that thing
		this.km_index = await frappe.xcall("emp_tracking.emp_tracking.doctype.evision_settings.evision_settings.get_map_index",
			{ map_name: "KMZ Map" }).catch(() => null) || { position: "Bottom right", start: "Open", rows: {} };
		const own = (key) => (this.km_index.rows[key] || {}).colour;
		KM_UNMATCHED = own("route_none") || KM_UNMATCHED;
		KM_DOWN = own("down") || KM_DOWN;
		KM_AFFECTED = own("affected") || KM_AFFECTED;
		this.index_closed = this.km_index.start === "Folded";
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

	// 2026-11-28: a Maintenance Team's "View team on map": every filter cleared, Area = the team's area
	set_area(area) {
		this.syncing = true;
		Promise.all(Object.entries(this.f).map(([k, c]) => c.set_value(k === "show" ? "Routes and Pins" : k === "area" ? area : "")))
			.then(async () => { this.syncing = false; await this.link_node_area(); this.refresh(); });
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
		// 2026-11-27: zoom to 22 (user: "zoom jyaada nahi ho raha"). Frappe's tiles set no maxZoom, so
		// Leaflet stopped at 18; past the tiles' last real level (19) the level-19 images are enlarged.
		this.map = L.map(this.$(".km-map")[0], { preferCanvas: true, maxZoom: KM_MAX_ZOOM }).setView(d.center, 11);
		const deep = (o) => ({ ...o, maxZoom: KM_MAX_ZOOM, maxNativeZoom: 19 });
		const street = L.tileLayer(d.tiles.default_tile.url, deep(d.tiles.default_tile.options)).addTo(this.map);
		const satellite = L.tileLayer(d.tiles.satellite_tile.url, deep(d.tiles.satellite_tile.options));
		// 2026-11-27: KMZ Polygons (area / DSA / cluster boundaries), made first so they lie under the routes
		this.polygons_layer = L.featureGroup().addTo(this.map);
		this.routes_layer = L.featureGroup().addTo(this.map);
		this.points_layer = L.featureGroup().addTo(this.map);
		// 2026-10-27: down / affected lines and pins and complaint markers, kept above the rest
		this.faults_layer = L.featureGroup().addTo(this.map);
		L.control.layers({ [__("Street")]: street, [__("Satellite")]: satellite },
			{ [__("Shapes")]: this.polygons_layer, [__("Routes")]: this.routes_layer, [__("Pins")]: this.points_layer,
				[__("Open Complaints")]: this.faults_layer }).addTo(this.map);
		// 2026-10-27: Index (map legend) in the bottom-right corner, filled by draw_index; clicks and
		// scrolling inside it must not move or zoom the map
		// 2026-11-28: corner from EVision Settings; "Hidden" keeps the box off the map
		const corner = { "Bottom right": "bottomright", "Bottom left": "bottomleft", "Top right": "topright",
			"Top left": "topleft" }[(this.km_index || {}).position];
		const index = L.control({ position: corner || "bottomright" });
		index.onAdd = () => {
			const div = L.DomUtil.create("div", "km-index");
			L.DomEvent.disableClickPropagation(div);
			L.DomEvent.disableScrollPropagation(div);
			return div;
		};
		if (corner || !this.km_index) index.addTo(this.map);
		this.$index = corner || !this.km_index ? $(index.getContainer()) : $("<div>");

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
		for (const layer of [this.polygons_layer, this.routes_layer, this.points_layer, this.faults_layer]) layer.on("click", on_click);
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
		// 2026-11-28: rows, labels and shown / hidden from EVision Settings > Maps (km_index)
		const rows = (this.km_index || {}).rows || {};
		const show = (key) => !rows[key] || rows[key].show;
		const lab = (key, fallback) => frappe.utils.escape_html((rows[key] && rows[key].label) || fallback);
		const it = (key, sym, fallback, extra = "") => show(key) ? `<div class="it ${extra}">${sym}<span>${lab(key, fallback)}</span></div>` : "";
		const types = show("pins") ? KM_PIN_TYPES.filter((t) => counts[t.key]).map((t) =>
			`<div class="it pt ${this.hidden_types.has(t.key) ? "off" : ""}" data-type="${t.key}" title="${__("Click to hide / show")}">
				<span class="dot" style="--sw:${t.colour}"></span><span>${t.label}</span><span class="c">${counts[t.key]}</span></div>`).join("") : "";
		const lines = it("route_node", `<span class="ln" style="--sw:linear-gradient(90deg,${KM_PALETTE.slice(0, 4).join(",")})"></span>`, __("Route, coloured by GIS Node"))
			+ it("route_none", `<span class="ln" style="--sw:repeating-linear-gradient(90deg,${KM_UNMATCHED} 0 6px,transparent 6px 9px)"></span>`, __("Route with no GIS Node (dashed)"))
			+ ((data.polygons || []).length ? it("shapes", `<span class="dot" style="--sw:rgba(124,58,237,.25);border:2px solid #7c3aed;border-radius:3px"></span>`, __("Shape (area / DSA / cluster boundary)")) : "");
		const node = it("node_pin", `<span class="dot" style="--sw:${KM_PALETTE[0]};border-color:var(--ev-text);width:14px;height:14px"></span>`, __("Node pin (labelled with GIS code)"));
		const faults = live ? it("open_complaint", `<span class="bang">!</span>`, __("Open complaint"))
			+ it("node_faults", `<span class="dot" style="--sw:${KM_PALETTE[0]};border:3px solid ${KM_DOWN};width:15px;height:15px"></span>`, __("Node with open complaints"))
			+ it("down", `<span class="ln thick" style="--sw:${KM_DOWN}"></span>`, __("Down: site with an open complaint"))
			+ it("affected", `<span class="ln thick" style="--sw:${KM_AFFECTED}"></span>`, __("Affected: fed through a down site")) : "";
		this.$index.toggleClass("closed", !!this.index_closed).html(`
			<div class="hd"><span>${__("Index")}</span><span>${this.index_closed ? "▸" : "▾"}</span></div>
			<div class="bd">
				${types ? `<div class="sec">${lab("pins", __("Pins (click to hide)"))}</div>${types}` : ""}
				${lines ? `<div class="sec">${__("Lines")}</div>${lines}` : ""}
				${node ? `<div class="sec">${__("Node")}</div>${node}` : ""}
				${faults ? `<div class="sec">${__("Open complaints")}</div>${faults}` : ""}
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
		const drawn = __("{0} routes and {1} pins on the map.", [data.routes.length, data.points.length]) +
			((data.polygons || []).length ? " " + __("{0} shapes.", [data.polygons.length]) : "");
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
		const is_shape = doctype === "KMZ Polygon"; // 2026-11-27
		const extra = is_shape
			? `<div>${__("Area")}: ${r.area_sq_m >= 100000 ? format_number(r.area_sq_m / 1e6, null, 2) + " km²" : format_number(r.area_sq_m, null, 0) + " m²"}</div>`
			: is_route
			? `<div>${__("Length")}: ${format_number(r.length_m, null, 1)} m</div>`
			: `<div>${format_number(r.latitude, null, 6)}, ${format_number(r.longitude, null, 6)}</div>`;
		return `<div class="km-pop">
			<b>${km_esc(is_shape ? r.polygon_name : is_route ? r.route_name : r.point_name)}</b> · ${link(doctype, r.name, __("open"))}
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
		this.polygons_layer.clearLayers();
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
		this.items = []; // 2026-11-27: every line / pin with its KMZ folder, for the "Map contents" tree
		// 2026-11-27: shapes in their Google Earth colours; the fill is kept see-through (at most 0.35)
		// so the streets and routes under it still show. [name, gis, title, ring, line, fill, opacity, pi]
		for (const [name, gis, title, ring, line, fill, opacity, pi] of data.polygons || []) {
			const colour = line || fill || km_colour(gis);
			const shape = L.polygon(ring, {
				color: colour, weight: 2, opacity: 0.9,
				fillColor: fill || colour, fillOpacity: Math.min(opacity == null ? 0.15 : opacity, 0.35),
			});
			shape.bindTooltip(km_esc(title || __("(no name)")), { sticky: true });
			this.register(shape, this.polygons_layer, "KMZ Polygon", name, title, pi, colour);
			// 2026-11-28: a team area's boundary (Area filter) is not a KMZ Polygon row: tooltip only
			if (!String(name).startsWith("area-boundary-")) this.bind_popup(shape, "KMZ Polygon", name, title);
		}
		// rows are short arrays (kmz_map.py): route [name, gis, title, coords, site, path index],
		// pin [name, gis, title, lat, lon, site, path index] (path index: 2026-11-27)
		for (const [name, gis, title, coords, site, pi] of data.routes) {
			const st = state(site);
			const colour = st ? (st === "down" ? KM_DOWN : KM_AFFECTED) : km_colour(gis);
			const line = L.polyline(coords, st
				? { color: colour, weight: 6, opacity: 0.95 }
				// 2026-10-27: a route with no GIS Node is dashed, so it never looks like a node's colour
				: { color: colour, weight: 3, opacity: 0.85, dashArray: gis ? null : "7 5" });
			this.register(line, st ? this.faults_layer : this.routes_layer, "KMZ Route", name, title, pi, colour);
			if (st) line.bindTooltip(tip[st], { sticky: true });
			this.bind_popup(line, "KMZ Route", name, title);
		}
		for (const [name, gis, title, lat, lon, site, pi] of data.points) {
			// the node's own pin (named with its GIS code, e.g. "C1U Node") is drawn larger
			const is_node = gis && (title || "").trim().toUpperCase().replace(/\s+NODE$/, "") === gis;
			const st = state(site);
			// a node with open complaints gets a thick red ring and a "⚠ V0N · 2 open" label
			const node_faults = is_node && live ? f.nodes[gis] || 0 : 0;
			// 2026-10-27: colour by pin type; the node pin keeps its node colour; a type hidden in the legend is skipped
			const type = is_node ? null : km_pin_type(title);
			// 2026-11-27: still made and listed in the tree (eye shut), so a folder shows all its pins as
			// in Google Earth; it only reaches the map when its eye is opened there
			const type_off = !!(type && !st && this.hidden_types.has(type.key));
			const fill = st === "down" ? KM_DOWN : st === "affected" ? KM_AFFECTED : type ? type.colour : km_colour(gis);
			const pin = L.circleMarker([lat, lon], {
				radius: is_node ? (node_faults ? 11 : 8) : st ? 6 : 5,
				color: node_faults ? KM_DOWN : is_node ? "#111827" : "#ffffff", weight: node_faults ? 4 : is_node ? 2 : 1.5,
				fillColor: fill, fillOpacity: 0.95,
			});
			this.register(pin, st || node_faults ? this.faults_layer : this.points_layer, "KMZ Point", name, title, pi, fill, type_off);
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
		this.draw_tree(data);
		if (fit) {
			// shapes count only when nothing else is drawn: an area boundary would zoom the map far out
			const drawn = [this.routes_layer, this.points_layer, this.faults_layer].filter((l) => l.getLayers().length);
			const bounds = L.featureGroup(drawn.length ? drawn : [this.polygons_layer]).getBounds();
			if (bounds.isValid()) this.map.fitBounds(bounds, { padding: [20, 20], maxZoom: 17 });
		}
		setTimeout(() => this.map.invalidateSize(), 50);
	}

	// Date: 2026-11-27
	// Puts a line / pin on its layer (unless hidden in the tree) and remembers it for the tree.
	// type_off: a pin type switched off in the Index; listed hidden unless shown from the tree.
	register(layer, group, doctype, name, title, pi, colour, type_off = false) {
		const id = ({ "KMZ Route": "R:", "KMZ Polygon": "G:" }[doctype] || "P:") + name;
		const item = { id, layer, group, doctype, name, title: (title || "").trim(), pi: pi == null ? -1 : pi, colour,
			index: this.items.length, type_off };
		this.items.push(item);
		if (!this.is_off(item)) layer.addTo(group);
	}

	// off the map: hidden with its eye in the tree, or its pin type is off and the tree did not open it
	is_off(item) {
		return this.hidden_rows.has(item.id) || (item.type_off && !this.shown_rows.has(item.id));
	}

	// Date: 2026-11-27
	// "Map contents": the KMZ folder chains ("Completed node KMZ / H6Q / Vasundhara ... to ODF")
	// as a tree like Google Earth's, with each folder's pins and lines inside it. Folders open on
	// click; only open folders are drawn, at most KM_TREE_PAGE rows each until "Show more".
	draw_tree(data) {
		const root = { key: "", name: "", folders: new Map(), items: [], count: 0, parent: null };
		const folders = new Map([["", root]]);
		const by_pi = new Map();
		const folder_for = (pi) => {
			if (by_pi.has(pi)) return by_pi.get(pi);
			let node = root;
			for (const part of (data.paths[pi] || "").split(" / ").map((s) => s.trim()).filter(Boolean)) {
				const key = node.key ? `${node.key} / ${part}` : part;
				if (!node.folders.has(part)) {
					const f = { key, name: part, folders: new Map(), items: [], count: 0, parent: node };
					node.folders.set(part, f);
					folders.set(key, f);
				}
				node = node.folders.get(part);
			}
			by_pi.set(pi, node);
			return node;
		};
		for (const item of this.items) {
			const f = folder_for(item.pi);
			f.items.push(item);
			for (let n = f; n; n = n.parent) n.count++;
		}
		this.tree = root;
		this.tree_folders = folders;
		this.tree_limits = new Map();
		// map reloaded (filters / refresh): run the typed search again on the new tree
		if (this.search) this.search_tree(this.search.words);
		this.paint_tree();
	}

	// Date: 2026-11-27
	// Places search. Every typed word must appear (any case) in a folder name or a pin / line name.
	// A folder whose own name matches is shown with all its contents; otherwise a folder stays
	// only if something inside it matches, and it opens by itself so the match can be seen.
	set_search(text) {
		const words = (text || "").toLowerCase().split(/\s+/).filter(Boolean);
		this.search = null;
		if (words.length && this.tree) this.search_tree(words);
		this.tree_limits = new Map();
		this.paint_tree();
		this.$(".km-found").text(this.search ? __("{0} found", [this.search.found.length]) : "");
	}

	search_tree(words) {
		const hit = (s) => {
			const low = (s || "").toLowerCase();
			return words.every((w) => low.includes(w));
		};
		// visible: folders kept, whole: folders shown unfiltered, items: matching pins / lines
		const s = { words, visible: new Set(), whole: new Set(), items: new Set(), found: [], closed: new Set() };
		const visit = (folder) => {
			if (hit(folder.name)) {
				s.visible.add(folder.key);
				s.whole.add(folder.key);
				s.found.push(...this.subtree_items(folder));
				return true;
			}
			let any = false;
			for (const i of folder.items) {
				if (hit(i.title)) {
					s.items.add(i.index);
					s.found.push(i);
					any = true;
				}
			}
			for (const f of folder.folders.values()) if (visit(f)) any = true;
			if (any) s.visible.add(folder.key);
			return any;
		};
		for (const f of this.tree.folders.values()) visit(f);
		for (const i of this.tree.items) {
			if (hit(i.title)) {
				s.items.add(i.index);
				s.found.push(i);
			}
		}
		this.search = s;
	}

	// open folders: the ones the user opened, plus (while searching) the ones leading to a match
	// that the user has not shut again
	is_open(key) {
		if (this.tree_open.has(key)) return true;
		const s = this.search;
		return !!(s && s.visible.has(key) && !s.whole.has(key) && !s.closed.has(key));
	}

	paint_tree() {
		const $t = this.$(".km-tree");
		const top = $t.scrollTop();
		const html = this.tree_rows(this.tree, 0, !!this.search);
		const empty = this.search ? __("No place matches the search.") : __("Nothing on the map for these filters.");
		$t.html(html || `<div class="text-muted small" style="padding:8px">${empty}</div>`);
		$t.scrollTop(top);
	}

	// rows of one open folder: its sub-folders (A-Z), then its lines and pins;
	// filtered = only the search's matches (off inside a folder whose own name matched)
	tree_rows(folder, depth, filtered) {
		const pad = (d) => `padding-left:${d * 14}px`;
		let subs = [...folder.folders.values()].sort((a, b) => a.name.localeCompare(b.name));
		let items = folder.items;
		if (filtered) {
			subs = subs.filter((f) => this.search.visible.has(f.key));
			items = items.filter((i) => this.search.items.has(i.index));
		}
		const entries = [...subs, ...items];
		const limit = this.tree_limits.get(folder.key) || KM_TREE_PAGE;
		let html = "";
		for (const e of entries.slice(0, limit)) {
			if (e.folders) {
				const open = this.is_open(e.key);
				const off = this.subtree_items(e).every((i) => this.is_off(i));
				html += `<div class="km-tr ${off ? "off" : ""}" data-key="${km_esc(e.key)}" style="${pad(depth)}" title="${km_esc(e.name)}">
					<span class="cr">${open ? "▼" : "▶"}</span><span class="ic">${open ? KM_ICONS.folder_open : KM_ICONS.folder}</span>
					<span class="lb">${km_esc(e.name)}</span><span class="ct">${e.count}</span>
					<span class="eye" title="${__("Hide / show")}">${off ? KM_ICONS.eye_off : KM_ICONS.eye}</span></div>`;
				if (open) html += this.tree_rows(e, depth + 1, filtered && !this.search.whole.has(e.key));
			} else {
				const off = this.is_off(e);
				const icon = e.doctype === "KMZ Route"
					? `<span style="color:${e.colour}">${KM_ICONS.line}</span>`
					: e.doctype === "KMZ Polygon"
					? `<span style="color:${e.colour}">${KM_ICONS.shape}</span>`
					: `<span class="pin-dot" style="background:${e.colour}"></span>`;
				html += `<div class="km-tr ${off ? "off" : ""}" data-item="${e.index}" style="${pad(depth)}" title="${km_esc(e.title)}">
					<span class="cr"></span><span class="ic">${icon}</span>
					<span class="lb">${km_esc(e.title || __("(no name)"))}</span>
					<span class="eye" title="${__("Hide / show")}">${off ? KM_ICONS.eye_off : KM_ICONS.eye}</span></div>`;
			}
		}
		if (entries.length > limit) {
			html += `<div class="km-tr" data-more="${km_esc(folder.key)}" style="${pad(depth)}"><span class="cr"></span>
				<span class="lb more">${__("Show {0} more", [Math.min(KM_TREE_PAGE, entries.length - limit)])}</span></div>`;
		}
		return html;
	}

	subtree_items(folder) {
		const out = [...folder.items];
		for (const f of folder.folders.values()) out.push(...this.subtree_items(f));
		return out;
	}

	// hides / shows lines and pins on the map, and remembers it for the next reload
	set_hidden(items, hide) {
		for (const i of items) {
			if (hide) {
				this.hidden_rows.add(i.id);
				this.shown_rows.delete(i.id);
				i.group.removeLayer(i.layer);
			} else {
				this.hidden_rows.delete(i.id);
				this.shown_rows.add(i.id);
				if (!i.group.hasLayer(i.layer)) i.layer.addTo(i.group);
			}
		}
		this.paint_tree();
	}

	zoom_to(items) {
		const bounds = L.latLngBounds([]);
		for (const i of items) bounds.extend(i.layer.getBounds ? i.layer.getBounds() : i.layer.getLatLng());
		if (bounds.isValid()) this.map.fitBounds(bounds, { padding: [30, 30], maxZoom: 20 });
	}

	// clicks in the tree: arrow opens / shuts a folder, a folder name also zooms to it, a pin / line
	// zooms to it and opens its popup, the eye hides / shows, "Show more" lists the next rows
	bind_tree() {
		this.$(".km-tree").on("click", ".km-tr", (e) => {
			const $row = $(e.currentTarget);
			const key = $row.attr("data-key");
			const more = $row.attr("data-more");
			const at = $row.attr("data-item");
			if (more != null) {
				this.tree_limits.set(more, (this.tree_limits.get(more) || KM_TREE_PAGE) + KM_TREE_PAGE);
				return this.paint_tree();
			}
			const on_eye = $(e.target).closest(".eye").length > 0;
			if (key != null) {
				const folder = this.tree_folders.get(key);
				if (!folder) return;
				const items = this.subtree_items(folder);
				if (on_eye) return this.set_hidden(items, !items.every((i) => this.is_off(i)));
				const on_arrow = $(e.target).closest(".cr").length > 0;
				if (this.is_open(key) && on_arrow) {
					this.tree_open.delete(key);
					if (this.search) this.search.closed.add(key); // shut a folder the search opened
				} else {
					this.tree_open.add(key);
					if (this.search) this.search.closed.delete(key);
				}
				this.paint_tree();
				if (!on_arrow) this.zoom_to(items);
				return;
			}
			const item = this.items[cint(at)];
			if (!item) return;
			if (on_eye) return this.set_hidden([item], !this.is_off(item));
			if (this.is_off(item)) this.set_hidden([item], false);
			if (item.layer.getBounds) this.map.fitBounds(item.layer.getBounds(), { padding: [40, 40], maxZoom: 20 });
			else this.map.setView(item.layer.getLatLng(), Math.max(this.map.getZoom(), 19));
			item.layer.openPopup();
		});
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
