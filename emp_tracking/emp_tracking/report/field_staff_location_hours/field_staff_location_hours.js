// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// Field Staff Location Hours: filters (created 2026-11-26). Blank employee = all field staff.
// 2026-11-27: Team and Role filters; opens on teams and people (days folded); "No location from
// app" in grey, low "In field" share in amber.

frappe.query_reports["Field Staff Location Hours"] = {
	filters: [
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "team", label: __("Team"), fieldtype: "Link", options: "Maintenance Team" },
		{ fieldname: "role", label: __("Role"), fieldtype: "Select", options: "\nSplicer\nRider\nTeam Leader\nHelper" },
		{ fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee" },
	],
	formatter(value, row, column, data, default_formatter) {
		let html = evision.noc_formatter(value, row, column, data, default_formatter);
		if (!data || !column) return html;
		// no hours: a quiet dash instead of a column of 0.0
		if (["field", "home", "office", "other", "total", "complaints"].includes(column.fieldname) && !value) {
			return `<div style="text-align:right;color:var(--text-light, #bbb)">–</div>`;
		}
		if (column.fieldname === "last_seen" && data.indent === 1 && !data.total) {
			return `<span style="color:var(--text-muted)">${frappe.utils.escape_html(value || "")}</span>`;
		}
		if (column.fieldname === "field_pct" && value != null && value < 50 && data.total) {
			return `<span style="color:var(--orange-600, #c2410c)">${html}</span>`;
		}
		return html;
	},
	initial_depth: 1,
	onload: (report) => evision.noc_report_onload(report),
	after_datatable_render: (dt) => evision.noc_report_after_render(dt),
};
