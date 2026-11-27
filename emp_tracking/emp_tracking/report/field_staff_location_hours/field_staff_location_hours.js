// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// Field Staff Location Hours: filters (created 2026-11-26). Blank employee = all field staff.

frappe.query_reports["Field Staff Location Hours"] = {
	filters: [
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee" },
	],
	formatter: evision.noc_formatter,
	initial_depth: 0,
	onload: (report) => evision.noc_report_onload(report),
	after_datatable_render: (dt) => evision.noc_report_after_render(dt),
};
