// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// Area tree view (created 2026-11-28, user: "only show Team 1 .. 6 and under teams the area names"):
// only the six EVision team areas (with their manager and number of areas), each with its
// localities under it (area.get_tree_children). A locality is moved by setting its Team Area on
// the Area form, so Add Child / drag-and-drop are not used. Localities with no team area yet are
// one click away ("Localities without a team area").

frappe.treeview_settings["Area"] = {
	breadcrumb: "Areas",
	title: __("Areas"),
	root_label: __("All Areas"),
	get_tree_nodes: "emp_tracking.emp_tracking.doctype.area.area.get_tree_children",
	disable_add_node: true,
	menu_items: [],
	onload(treeview) {
		frappe.db.count("Area", { filters: { is_team_area: 0, team_area: ["is", "not set"] } }).then((n) => {
			if (!n) return;
			treeview.page.add_inner_button(__("Localities without a team area ({0})", [n]),
				() => frappe.set_route("List", "Area", { is_team_area: 0, team_area: ["is", "not set"] }));
		});
		treeview.page.add_inner_button(__("List view"), () => frappe.set_route("List", "Area"));
	},
};
