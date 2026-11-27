// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// NOC Unique Cut Master: filters (created 2026-11-26). Cuts first received in From..To.
// 2026-11-26: shared scope filters and cell colours (SLA as a green / red / amber chip) from evision.js.

frappe.query_reports["NOC Unique Cut Master"] = {
	filters: [
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "team", label: __("Team"), fieldtype: "Link", options: "Maintenance Team" },
		{ fieldname: "cut_sla", label: __("Cut SLA"), fieldtype: "Select", options: "\nIN\nOUT\nOpen" },
	].concat(evision.noc_scope_filters()),
	formatter: evision.noc_formatter,
	// 2026-11-26: full screen button and a full-height table
	onload: (report) => evision.noc_report_onload(report),
	after_datatable_render: (dt) => evision.noc_report_after_render(dt),
};
