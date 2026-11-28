// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// Complaint List Colours form (created 2026-11-28, user: the main site's table was empty):
// "Load default colours" adds every default row that is missing (Status, Operator, Link Status,
// Link Type, Area, EVisions SLA); rows already there keep their colour.

frappe.ui.form.on("Complaint List Colours", {
	refresh(frm) {
		frm.add_custom_button(__("Load default colours"), async () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__("Save or reload the page first."));
				return;
			}
			const added = await frappe.xcall(
				"emp_tracking.emp_tracking.doctype.complaint_list_colours.complaint_list_colours.load_defaults");
			frappe.show_alert({ message: added ? __("{0} default colours added", [added]) : __("All default colours are already there"),
				indicator: "green" });
			frm.reload_doc();
		});
	},
});
