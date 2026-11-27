// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// NOC SLA TAT Summary: filters (created 2026-11-26). "Rows" picks one of the NOC workbook's
// ALL TEAM SUMMARY pivot layouts (keys in emp_tracking/noc_reports.py GROUP_BY).
// 2026-11-26: shared scope filters and cell colours (In green, Out red, zeros faded) from evision.js.

frappe.query_reports["NOC SLA TAT Summary"] = {
	filters: [
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{
			fieldname: "group_by", label: __("Rows"), fieldtype: "Select", default: "Month, Team",
			options: "Month, Team\nMonth, Team, Splicer\nSplicer, Team, Month\nTeam, Month, Date\nMonth, Date, Team, Splicer",
		},
		{ fieldname: "team", label: __("Team"), fieldtype: "Link", options: "Maintenance Team" },
	].concat(evision.noc_scope_filters()),
	formatter: evision.noc_formatter,
	// 2026-11-26: full screen button and a full-height table
	onload: (report) => evision.noc_report_onload(report),
	after_datatable_render: (dt) => evision.noc_report_after_render(dt),
};
