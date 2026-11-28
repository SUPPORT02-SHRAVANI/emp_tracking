// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
//
// Maintenance Team form.
// Change log
//   2026-11-28  "Areas" section (user: "here show areas too"): the localities of the team's Area
//               (Areas tree: localities with that Team Area), as chips that open the Area, with the
//               area manager and a link to the tree. Localities are moved on the Area form.
//               Drawn by the shared evision.render_team_areas (public/js/evision.js).
//   2026-11-28  "View team on map" button: the KMZ Map on the team's area (nodes, routes, pins,
//               open complaints) with the area's boundary in the Team Colour.
//   2026-11-28  The button opens the separate Team Map page zoomed to this team (was the KMZ Map).

frappe.ui.form.on("Maintenance Team", {
	refresh(frm) {
		evision.render_team_areas(frm, "area", "areas_html");
		if (!frm.is_new() && frm.doc.area) {
			// 2026-11-28 (user: "separate map for it"): the Team Map page, zoomed to this team
			frm.add_custom_button(__("View team on map"), () => {
				frappe.route_options = { team: frm.doc.name };
				frappe.set_route("team-map");
			});
		}
	},
	area(frm) {
		evision.render_team_areas(frm, "area", "areas_html");
	},
});
