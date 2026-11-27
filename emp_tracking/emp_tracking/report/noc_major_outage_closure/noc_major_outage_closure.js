// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// NOC Major Outage Closure: filters (created 2026-11-26). Opens on the last 3 months, as the
// workbook tab lists several months. Rows are grouped per month (tree, see the .py).
// 2026-11-26: shared scope filters and cell colours from evision.js.

frappe.query_reports["NOC Major Outage Closure"] = {
	filters: [
		{
			fieldname: "from_date", label: __("From"), fieldtype: "Date", reqd: 1,
			// moment: frappe.datetime.month_start() ignores its argument
			default: moment().subtract(2, "month").startOf("month").format("YYYY-MM-DD"),
		},
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "team", label: __("Team"), fieldtype: "Link", options: "Maintenance Team" },
	].concat(evision.noc_scope_filters()),
	formatter: evision.noc_formatter,
	// 2026-11-26: full screen button and a full-height table
	onload: (report) => evision.noc_report_onload(report),
	after_datatable_render: (dt) => evision.noc_report_after_render(dt),
};
