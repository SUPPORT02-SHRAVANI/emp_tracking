// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// Team Cable Summary: filters (created 2026-10-27). Blank Project / Maintenance = both.

frappe.query_reports["Team Cable Summary"] = {
	filters: [
		{
			fieldname: "work_type",
			label: __("Project / Maintenance"),
			fieldtype: "Select",
			options: "\nMaintenance\nProject",
			default: "Maintenance",
		},
		{ fieldname: "team", label: __("Maintenance Team"), fieldtype: "Link", options: "Maintenance Team" },
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date" },
	],
};
