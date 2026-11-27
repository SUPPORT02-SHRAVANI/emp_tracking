// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// NOC Unique Cut Summary: filters (created 2026-11-26). Same scope defaults as NOC Pending Summary;
// Team wise on, like the workbook's UNIQUE CUT TEAM SUMMARY tab (tree: day totals, teams under it).
// 2026-11-26: shared scope filters and cell colours from evision.js.

frappe.query_reports["NOC Unique Cut Summary"] = {
	filters: [
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "team", label: __("Team"), fieldtype: "Link", options: "Maintenance Team" },
		{ fieldname: "team_wise", label: __("Team wise"), fieldtype: "Check", default: 1 },
	].concat(evision.noc_scope_filters()),
	formatter: evision.noc_formatter,
	initial_depth: 0,
	// 2026-11-26: full screen button, full-height table, light band behind every other month
	onload: (report) => evision.noc_report_onload(report),
	after_datatable_render: (dt) => evision.noc_report_after_render(dt),
};
