// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// NOC Performance: filters (created 2026-11-26). "Rows" = month-wise or day-wise, optionally per
// team or splicer (keys in emp_tracking/noc_reports.py PERF_ROWS). Day call = received 08:00-19:59.
// 2026-11-26: redesigned: day / night rows under each period, 7 columns stretched over the width.

frappe.query_reports["NOC Performance"] = {
	filters: [
		{
			fieldname: "from_date", label: __("From"), fieldtype: "Date", reqd: 1,
			// moment: frappe.datetime.month_start() ignores its argument
			default: moment().subtract(2, "month").startOf("month").format("YYYY-MM-DD"),
		},
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{
			fieldname: "rows_by", label: __("Rows"), fieldtype: "Select", default: "Month",
			options: "Month\nDay\nMonth, Team\nDay, Team\nTeam, Month\nMonth, Splicer",
		},
		{ fieldname: "team", label: __("Team"), fieldtype: "Link", options: "Maintenance Team" },
	].concat(evision.noc_scope_filters()),
	formatter: evision.noc_formatter,
	onload: (report) => evision.noc_report_onload(report),
	after_datatable_render: (dt) => evision.noc_report_after_render(dt),
};
