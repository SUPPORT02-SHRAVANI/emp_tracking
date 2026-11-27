// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// NOC Pending Summary: filters (created 2026-11-26). Defaults follow the NOC workbook's scope:
// own teams only, own fibre faults only. "Team wise" = the workbook's TEAM WISE PENDING SUMMARY tab,
// shown as a tree (day totals, teams under each day, collapsed at first).
// 2026-11-26: shared scope filters and cell colours from evision.js (noc_scope_filters / noc_formatter).

frappe.query_reports["NOC Pending Summary"] = {
	filters: [
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "team", label: __("Team"), fieldtype: "Link", options: "Maintenance Team" },
		{ fieldname: "team_wise", label: __("Team wise"), fieldtype: "Check", default: 0 },
	].concat(evision.noc_scope_filters()),
	formatter: evision.noc_formatter,
	initial_depth: 0,
	// 2026-11-26: full screen button, full-height table, light band behind every other month
	onload: (report) => evision.noc_report_onload(report),
	after_datatable_render: (dt) => evision.noc_report_after_render(dt),
};
