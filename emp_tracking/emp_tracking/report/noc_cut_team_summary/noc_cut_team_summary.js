// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// NOC Cut Team Summary: filters (created 2026-11-26). Every SR counted, per day and team, with who
// closed them. Shared look from evision.js (scope filters, colours, full screen, month bands).

frappe.query_reports["NOC Cut Team Summary"] = {
	filters: [
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "team", label: __("Team"), fieldtype: "Link", options: "Maintenance Team" },
	].concat(evision.noc_scope_filters()),
	formatter: evision.noc_formatter,
	initial_depth: 0,
	onload: (report) => evision.noc_report_onload(report),
	after_datatable_render: (dt) => evision.noc_report_after_render(dt),
};
