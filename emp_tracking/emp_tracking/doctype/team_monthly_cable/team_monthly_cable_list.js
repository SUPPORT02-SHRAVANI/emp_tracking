// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// Team Monthly Cable list: "Add for All Teams" (one date, every team's metres in one grid) and
// a link to the Team Cable Summary report (created 2026-10-27).

frappe.listview_settings["Team Monthly Cable"] = {
	// Date: 2026-10-27
	onload(listview) {
		if (frappe.model.can_create("Team Monthly Cable")) {
			listview.page.add_inner_button(__("Add for All Teams"), () => add_for_all_teams(listview));
		}
		listview.page.add_inner_button(__("Summary by Month"), () =>
			frappe.set_route("query-report", "Team Cable Summary")
		);
	},
};

// Date: 2026-10-27
// One row per active Maintenance Team; rows left at 0 are skipped on the server.
function add_for_all_teams(listview) {
	frappe.db
		.get_list("Maintenance Team", { filters: { status: "Active" }, fields: ["name"], order_by: "name asc", limit: 0 })
		.then((teams) => {
			const dialog = new frappe.ui.Dialog({
				title: __("Add Cable for All Teams"),
				size: "large",
				fields: [
					{ fieldname: "date", label: __("Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
					{ fieldtype: "Column Break" },
					{
						fieldname: "work_type",
						label: __("Project / Maintenance"),
						fieldtype: "Select",
						options: "Maintenance\nProject",
						default: "Maintenance",
						reqd: 1,
					},
					{ fieldtype: "Section Break" },
					{
						fieldname: "rows",
						label: __("Cable per Team (m)"),
						fieldtype: "Table",
						cannot_add_rows: false,
						in_place_edit: true,
						data: teams.map((t) => ({ team: t.name, total_cable: 0 })),
						fields: [
							{
								fieldname: "team",
								label: __("Maintenance Team"),
								fieldtype: "Link",
								options: "Maintenance Team",
								in_list_view: 1,
								reqd: 1,
							},
							{ fieldname: "total_cable", label: __("Total Cable (m)"), fieldtype: "Float", in_list_view: 1 },
						],
						description: __("Leave 0 for teams with no cable on this date."),
					},
					{ fieldtype: "Section Break" },
					{ fieldname: "location", label: __("Site / Link / Location"), fieldtype: "Data" },
					{ fieldname: "remarks", label: __("Remarks"), fieldtype: "Small Text" },
				],
				primary_action_label: __("Save Entries"),
				primary_action(values) {
					frappe.call({
						method: "emp_tracking.emp_tracking.doctype.team_monthly_cable.team_monthly_cable.add_entries",
						args: { ...values, rows: values.rows || [] },
						freeze: true,
						callback(r) {
							if (r.exc) return;
							dialog.hide();
							frappe.show_alert({ message: __("{0} entries saved", [r.message.length]), indicator: "green" });
							listview.refresh();
						},
					});
				},
			});
			dialog.show();
		});
}
