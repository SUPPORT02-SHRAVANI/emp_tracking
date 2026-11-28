// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// Area list (created 2026-11-28, user: "clicking Areas opens the tree view"): the menu opens this
// list again (+ Add, filters); "Team view" opens the tree of Area 1-6 with their localities.

frappe.listview_settings["Area"] = {
	add_fields: ["is_team_area", "team_area"],
	onload(listview) {
		listview.page.add_inner_button(__("Team view"), () => frappe.set_route("Tree", "Area"));
	},
};
