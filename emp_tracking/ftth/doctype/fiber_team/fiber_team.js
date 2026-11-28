// Copyright (c) 2026, Softworld and contributors
// For license information, please see license.txt
//
// Fiber Team form. Created 2026-11-28 (user: "put this in fiber team"): the team's Team Area can
// only be one of the six team areas (Area 1-6), and the form shows that area's manager and its
// localities (shared evision.render_team_areas, as on the Maintenance Team form).

frappe.ui.form.on("Fiber Team", {
	setup(frm) {
		frm.set_query("team_area", () => ({ filters: { is_team_area: 1 } }));
	},
	refresh(frm) {
		evision.render_team_areas(frm, "team_area", "areas_html");
	},
	team_area(frm) {
		evision.render_team_areas(frm, "team_area", "areas_html");
	},
});
