// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// NOC Team Availability: filters (created 2026-11-26). All complaints count here (a vendor or a
// non-fibre call still uses the team's people), so "Own fibre faults only" starts unticked.

frappe.query_reports["NOC Team Availability"] = {
	filters: [
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "team", label: __("Team"), fieldtype: "Link", options: "Maintenance Team" },
	].concat(evision.noc_scope_filters().map((f) => (f.fieldname === "own_fiber_only" ? Object.assign({}, f, { default: 0 }) : f))),
	formatter: evision.noc_formatter,
	initial_depth: 0,
	onload: (report) => evision.noc_report_onload(report),
	after_datatable_render: (dt) => evision.noc_report_after_render(dt),
};
