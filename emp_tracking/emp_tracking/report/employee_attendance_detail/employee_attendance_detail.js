// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// Employee Attendance Detail: filters and colours (created 2026-11-23).
// Colours follow the biometric report: P green, A red, ½P orange, WO / H yellow, L blue.

const EAD_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
	"September", "October", "November", "December"];

frappe.query_reports["Employee Attendance Detail"] = {
	filters: [
		{
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			options: EAD_MONTHS.join("\n"),
			// Last month by default: that is the month payroll is run for
			default: EAD_MONTHS[(new Date().getMonth() + 11) % 12],
			reqd: 1,
		},
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Int",
			default: new Date().getMonth() === 0 ? new Date().getFullYear() - 1 : new Date().getFullYear(),
			reqd: 1,
		},
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee" },
		{ fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department" },
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch" },
		{
			fieldname: "shift_start",
			label: __("Shift Start"),
			fieldtype: "Time",
			default: "09:30:00",
			description: __("Used for Late By when the employee has no shift"),
		},
		{
			fieldname: "shift_end",
			label: __("Shift End"),
			fieldtype: "Time",
			// The biometric machine's FS shift ends 18:29 (its Early By figures are counted from there)
			default: "18:29:00",
			description: __("Used for Early By when the employee has no shift"),
		},
		{ fieldname: "late_grace", label: __("Late Grace (min)"), fieldtype: "Int", default: 15 },
		{ fieldname: "early_grace", label: __("Early Grace (min)"), fieldtype: "Int", default: 10 },
	],

	// 2026-11-23: Frappe's Export gives plain cells; this button downloads the same data as a
	// coloured Excel built on the server (download_xlsx in the report's .py file).
	onload(report) {
		report.page.add_inner_button(__("Download Excel (Coloured)"), () => {
			const filters = report.get_values();
			if (!filters) return;
			const url = "/api/method/emp_tracking.emp_tracking.report.employee_attendance_detail."
				+ "employee_attendance_detail.download_xlsx?filters="
				+ encodeURIComponent(JSON.stringify(filters));
			window.open(frappe.urllib.get_full_url(url));
		});
	},

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "employee" && data.row_type === "Status") {
			return `<b>${value}</b>`;
		}
		if (column.fieldname === "detail") {
			return `<span style="color: var(--text-muted);">${value}</span>`;
		}
		// Day columns on the Status row get the biometric colours
		if (data.row_type === "Status" && /^d\d\d$/.test(column.fieldname)) {
			const s = data[column.fieldname] || "";
			const colour = {
				P: "var(--green-600)", "½P": "var(--orange-600)", A: "var(--red-600)",
				L: "var(--blue-600)", WFH: "var(--green-600)",
			}[s];
			if (s.startsWith("WO") || s === "H") {
				return `<span style="background: var(--yellow-100); color: var(--yellow-800); padding: 1px 4px; border-radius: 3px; font-weight: 600;">${value}</span>`;
			}
			if (colour) return `<span style="color: ${colour}; font-weight: 600;">${value}</span>`;
		}
		if ((data.row_type === "Late By" || data.row_type === "Early By") && /^d\d\d$/.test(column.fieldname) && value) {
			return `<span style="color: var(--red-500);">${value}</span>`;
		}
		return value;
	},
};
