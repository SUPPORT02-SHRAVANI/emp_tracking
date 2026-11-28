// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt

// ---------------------------------------------------------------------------------------------
// GIS Node (FTTH Tracker): Site Diagram, added from this app through doctype_js in hooks.py
//
// How this file works
//   One GIS Node (GIS code such as D1J) has many Sites. When a GIS Node is opened, this script
//   loads all its Sites and draws them in the "Site Diagram" section (Custom Field
//   custom_site_diagram, made by setup.py) as a top-down flow chart, like the team's Excel flow
//   charts. The tree is built from the ETIPL code: a site with code "D1J.2.4.1" hangs under the
//   site with code "D1J.2.4", which hangs under "D1J.2", which hangs under the node itself.
//   Boxes can be collapsed, and the chart can be zoomed.
//
// Change log
//   2026-10-07  Created on the Node form (node.js): site tree built from ETIPL codes, drawn as a
//               top-down flow chart (reference: Flow Chart D1J), with zoom buttons.
//   2026-10-24  Moved to GIS Node when Node was merged into it; the HTML field is now the
//               Custom Field custom_site_diagram.
//   2026-10-26  "KMZ Files" section: lists the KMZ files FTTH Tracker imported for this node
//               (custom_kmz_imported), with route / point counts and links to them.
//   2026-10-26  "KMZ Map" button: opens the KMZ Map page filtered to this node.
//   2026-10-27  "Topology" button: opens the Network Topology page on this node.
//   2026-11-28  Area dropdown (all Areas, with their team area) on the Area text field; a
//               locality in a team area fills the Team Area; Team Area offers Area 1-6 only.
// ---------------------------------------------------------------------------------------------

// Form events: when a saved GIS Node is opened or reloaded, draw its site diagram.
frappe.ui.form.on("GIS Node", {
	// 2026-11-28: Team Area is one of the six team areas (its Area Manager then fills on save)
	setup(frm) {
		frm.set_query("team_area", () => ({ filters: { is_team_area: 1 } }));
	},
	// 2026-11-28 (user: "in GIS node no dropdown for area"): Area stays free text (242 nodes have
	// spellings not in the Area list), with every Area offered as a dropdown while typing / on click
	onload_post_render(frm) {
		area_suggestions(frm);
	},
	// 2026-11-28: a locality that belongs to a team area fills the Team Area (Area Manager on save).
	// A name that is not an Area yet asks "create it?" (user: "if adding new, always ask")
	async area(frm) {
		const typed = (frm.doc.area || "").trim();
		if (!typed) return;
		const found = await frappe.db.get_list("Area", { filters: { name: ["like", typed] }, fields: ["name", "team_area", "is_team_area"], limit: 1 });
		if (!found.length) {
			ask_create_area(frm, typed);
			return;
		}
		const a = found[0];
		if (a.name !== frm.doc.area) {
			frm.set_value("area", a.name); // "hadapsar" -> "Hadapsar": the Area's own spelling
			return;
		}
		const team = a.is_team_area ? a.name : a.team_area;
		if (team && !frm.doc.team_area) frm.set_value("team_area", team);
	},
	// Date: 2026-10-07
	refresh(frm) {
		area_suggestions(frm);
		// The field is missing until setup.py has run after a migrate; do nothing then.
		if (!frm.is_new() && frm.get_field("custom_site_diagram")) render_site_diagram(frm);
		// 2026-10-26: same guard for the KMZ list (field made by setup.py)
		if (!frm.is_new() && frm.get_field("custom_kmz_imported")) render_kmz_files(frm);
		// 2026-10-26: this node's routes and pins on the KMZ Map page
		if (!frm.is_new()) {
			frm.add_custom_button(__("KMZ Map"), () => {
				frappe.route_options = { gis: frm.doc.name };
				frappe.set_route("kmz-map");
			});
			// 2026-10-27: feeder tree and failure impact of this node
			frm.add_custom_button(__("Topology"), () => {
				frappe.route_options = { node: frm.doc.name };
				frappe.set_route("network-topology");
			});
		}
	},
});

// Date: 2026-11-28
// Dropdown of Areas on the free-text Area field: all localities (A-Z) appear on click and narrow
// down while typing; picking one fills the field. Loaded once per page.
let GN_AREAS = null;
async function area_suggestions(frm) {
	const field = frm.fields_dict.area;
	if (!field || !field.$input || field.$input.data("gn-areas")) return;
	field.$input.data("gn-areas", 1);
	if (!GN_AREAS) {
		GN_AREAS = (await frappe.db.get_list("Area", { fields: ["name", "team_area", "is_team_area"], order_by: "name asc", limit: 1000 }))
			.filter((a) => !a.is_team_area)
			.map((a) => ({ label: a.team_area ? `${a.name}  ·  ${a.team_area}` : a.name, value: a.name }));
	}
	const aw = new Awesomplete(field.$input.get(0), { list: GN_AREAS, minChars: 0, maxItems: 50, autoFirst: true,
		sort: false, filter: (text, input) => Awesomplete.FILTER_CONTAINS(text.label, input) });
	field.$input.on("focus click", () => { if (!field.$input.val()) { aw.evaluate(); aw.open(); } });
	field.$input.on("awesomplete-selectcomplete", (e) => {
		frm.set_value("area", e.originalEvent ? e.originalEvent.text.value : field.$input.val());
	});
}

// Date: 2026-11-28
// A typed area that is not in the Area list: ask before creating it (user: "if adding new, always
// ask should I create new"). Yes -> a new locality Area with its Team Area and a code; No -> the
// typed text stays as it is.
function ask_create_area(frm, name) {
	const code = "NOC-" + name.toUpperCase().replace(/[^A-Z0-9]+/g, "-").replace(/^-|-$/g, "");
	const d = new frappe.ui.Dialog({
		title: __("Create new area?"),
		fields: [
			{ fieldtype: "HTML", fieldname: "q", options: `<p>${__("\"{0}\" is not in the Area list. Create it as a new area?", [frappe.utils.escape_html(name)])}</p>` },
			{ fieldtype: "Data", fieldname: "area_name", label: __("Area Name"), default: name, reqd: 1 },
			{ fieldtype: "Link", fieldname: "team_area", label: __("Team Area"), options: "Area", default: frm.doc.team_area,
				get_query: () => ({ filters: { is_team_area: 1 } }), description: __("Area 1-6 this place belongs to") },
			{ fieldtype: "Data", fieldname: "area_code", label: __("Area Code"), default: code, reqd: 1 },
		],
		primary_action_label: __("Yes, create"),
		primary_action: async (v) => {
			const doc = await frappe.db.insert({ doctype: "Area", area_name: v.area_name.trim(), area_code: v.area_code,
				status: "Active", team_area: v.team_area || null });
			d.hide();
			GN_AREAS = null; // the dropdown reloads with the new area
			frappe.show_alert({ message: __("Area {0} created", [doc.name]), indicator: "green" });
			await frm.set_value("area", doc.name);
			if (v.team_area && !frm.doc.team_area) frm.set_value("team_area", v.team_area);
		},
		secondary_action_label: __("No, keep as typed"),
		secondary_action: () => d.hide(),
	});
	d.show();
}

// Top-down flow chart, like the team's Excel flow charts: node on top, each site under its feeder.
const SITE_DIAGRAM_CSS = `
.site-diagram-tools { margin-bottom: 8px; }
.site-diagram { overflow: auto; max-height: 80vh; padding: 12px 4px; }
.site-diagram ul { display: flex; justify-content: center; position: relative; list-style: none;
	margin: 0; padding: 22px 0 0; }
.site-diagram > ul { padding: 0; width: max-content; min-width: 100%; }
.site-diagram li { display: flex; flex-direction: column; align-items: center; position: relative;
	padding: 22px 5px 0; }
.site-diagram li::before, .site-diagram li::after { content: ""; position: absolute; top: 0; right: 50%;
	width: 50%; height: 22px; border-top: 1.5px solid var(--text-color); }
.site-diagram li::after { right: auto; left: 50%; border-left: 1.5px solid var(--text-color); }
.site-diagram li:first-child::before, .site-diagram li:last-child::after { border: 0 none; }
.site-diagram li:last-child::before { border-right: 1.5px solid var(--text-color); }
.site-diagram li:only-child::before { border-top: 0 none; }
.site-diagram ul ul::before { content: ""; position: absolute; top: 0; left: 50%; height: 22px;
	border-left: 1.5px solid var(--text-color); }
.site-diagram > ul > li { padding-top: 0; }
.site-diagram > ul > li::before, .site-diagram > ul > li::after { display: none; }
.site-diagram li.sd-closed > ul { display: none; }
.site-diagram .sd-box { flex: none; width: 160px; border: 1.5px solid var(--text-color); background: var(--fg-color);
	text-align: center; line-height: 1.3; }
.site-diagram .sd-head { position: relative; padding: 1px 4px; border-bottom: 1.5px solid var(--text-color);
	font-size: var(--text-xs); font-weight: 600; }
.site-diagram .sd-body { padding: 5px 6px; }
.site-diagram .sd-name { display: block; font-size: var(--text-sm); color: var(--text-color); }
.site-diagram .sd-meta { font-size: var(--text-xs); color: var(--text-muted); }
.site-diagram .sd-root { width: auto; min-width: 160px; padding: 8px 16px; font-size: var(--text-lg); font-weight: 700; }
.site-diagram .sd-toggle { position: absolute; right: 4px; top: 0; cursor: pointer; user-select: none; }
`;

// Date: 2026-10-07
// Returns the ETIPL code of the site one level above (null for a first-level site).
// "04N.2.1.3" -> "04N.2.1"; a first-level code ("04N.2") hangs off the node itself.
function parent_code(code) {
	const parts = code.split(".");
	return parts.length > 2 ? parts.slice(0, -1).join(".") : null;
}

// Date: 2026-10-07
// Returns the last number of an ETIPL code ("04N.2.10" -> 10), used to sort sites side by side.
function last_number(code) {
	return cint((code || "").split(".").pop());
}

// Date: 2026-10-07
// Turns the flat list of sites into a tree and returns the first-level sites.
// Sites of one node as a tree: each site sits under the site whose ETIPL code is one level shorter.
function build_site_tree(sites) {
	const by_code = {};
	sites.forEach((site) => {
		site.children = [];
		if (site.etipl_code) by_code[site.etipl_code] = site;
	});
	const by_name = {};
	sites.forEach((site) => (by_name[(site.site_name || "").toLowerCase()] = site));

	const roots = [];
	sites.forEach((site) => {
		// Without an ETIPL code, the B Location says which site feeds it.
		const parent = site.etipl_code
			? by_code[parent_code(site.etipl_code)]
			: by_name[(site.b_location || "").toLowerCase()];
		(parent && parent !== site ? parent.children : roots).push(site);
	});

	const sort = (list) => {
		list.sort((a, b) => last_number(a.etipl_code) - last_number(b.etipl_code));
		list.forEach((site) => sort(site.children));
	};
	sort(roots);
	return roots;
}

// Date: 2026-10-07
// Returns the ETIPL code without the node prefix.
// "D1J.2.4.1" -> "2.4.1", the position number written above each box in the flow charts.
function short_code(code) {
	return (code || "").split(".").slice(1).join(".");
}

// Date: 2026-10-07
// Builds the HTML of one site box (position number, site name, month and vendor) followed by
// the boxes of all the sites below it. Calls itself for each child site.
function site_html(site) {
	const esc = frappe.utils.escape_html;
	const meta = [site.month, site.vendor_name].filter(Boolean).join(" · ");
	const toggle = site.children.length ? `<span class="sd-toggle" title="${__("Collapse / expand")}">−</span>` : "";
	const children = site.children.length ? `<ul>${site.children.map(site_html).join("")}</ul>` : "";
	return `<li>
		<div class="sd-box" title="${esc(site.etipl_code || "")}">
			<div class="sd-head">${esc(short_code(site.etipl_code) || "-")}${toggle}</div>
			<div class="sd-body">
				<a class="sd-name" href="/app/site/${encodeURIComponent(site.name)}">${esc(site.site_name)}</a>
				<span class="sd-meta">${esc(meta)}</span>
			</div>
		</div>
		${children}
	</li>`;
}

// Date: 2026-10-07
// Loads the node's sites, draws the flow chart into the Site Diagram field, and wires up the
// collapse (- / + in a box) and zoom (- / + above the chart) buttons.
async function render_site_diagram(frm) {
	const wrapper = frm.get_field("custom_site_diagram").$wrapper;
	const sites = await frappe.db.get_list("Site", {
		filters: { node: frm.doc.name },
		fields: ["name", "site_name", "etipl_code", "b_location", "vendor_name", "month"],
		limit: 5000,
	});
	if (!sites.length) {
		wrapper.html(`<div class="text-muted">${__("No sites on this node yet.")}</div>`);
		return;
	}

	const roots = build_site_tree(sites);
	wrapper.html(`<style>${SITE_DIAGRAM_CSS}</style>
		<div class="site-diagram-tools">
			<button class="btn btn-xs btn-default sd-zoom" data-step="-0.1">−</button>
			<button class="btn btn-xs btn-default sd-zoom" data-step="0.1">+</button>
			<span class="text-muted small">${__("{0} sites. Zoom with − / +, scroll to move.", [sites.length])}</span>
		</div>
		<div class="site-diagram"><ul><li>
			<div class="sd-box sd-root">${frappe.utils.escape_html(frm.doc.name)}</div>
			<ul>${roots.map(site_html).join("")}</ul>
		</li></ul></div>`);

	wrapper.find(".sd-toggle").on("click", function () {
		const li = $(this).closest("li").toggleClass("sd-closed");
		$(this).text(li.hasClass("sd-closed") ? "+" : "−");
	});

	// Big nodes are far wider than the screen, so start zoomed out to fit and let the user zoom.
	const diagram = wrapper.find(".site-diagram");
	const chart = diagram.children("ul");
	let zoom = Math.min(1, Math.max(0.3, diagram.width() / chart.outerWidth()));
	const apply_zoom = () => chart.css("zoom", zoom);
	apply_zoom();
	wrapper.find(".sd-zoom").on("click", function () {
		zoom = Math.min(1.5, Math.max(0.2, zoom + flt($(this).data("step"))));
		apply_zoom();
	});
}

// Date: 2026-10-26
// "Imported KMZ Files": one row per KMZ source file FTTH Tracker imported for this node, with
// links to the node's KMZ Routes / KMZ Points from that file. The node's own uploaded file and
// folder path are the plain fields custom_kmz_file / custom_kmz_path above it.
async function render_kmz_files(frm) {
	const wrapper = frm.get_field("custom_kmz_imported").$wrapper;
	wrapper.html(`<div class="text-muted small">${__("Loading KMZ files...")}</div>`);
	const rows = await frappe.xcall("emp_tracking.overrides.gis_node.get_kmz_files", { gis: frm.doc.name });
	if (!rows.length) {
		wrapper.html(`<div class="text-muted small">${__("No KMZ routes or points imported for this node yet.")}</div>`);
		return;
	}
	const link = (doctype, count, r) => {
		if (!count) return "0";
		// route options open the list filtered to this node and file
		const q = new URLSearchParams({ gis: frm.doc.name, source_file: r.source_file });
		return `<a href="/app/${frappe.router.slug(doctype)}?${q}">${count}</a>`;
	};
	wrapper.html(`
		<div class="text-muted small" style="margin-bottom:4px">${__("Imported KMZ Files")}</div>
		<table class="table table-bordered table-sm" style="margin:0">
			<thead><tr><th>${__("KMZ File")}</th><th>${__("Folder in KMZ")}</th>
				<th class="text-right">${__("Routes")}</th><th class="text-right">${__("Points")}</th></tr></thead>
			<tbody>${rows.map((r) => `<tr>
				<td>${frappe.utils.escape_html(r.source_file || __("(no file name)"))}</td>
				<td>${frappe.utils.escape_html(r.node_folder)}</td>
				<td class="text-right">${link("KMZ Route", r.routes, r)}</td>
				<td class="text-right">${link("KMZ Point", r.points, r)}</td></tr>`).join("")}</tbody>
		</table>`);
}
