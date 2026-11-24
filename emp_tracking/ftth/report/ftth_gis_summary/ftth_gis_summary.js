// Copyright (c) 2026, Softworld and contributors
// For license information, please see license.txt

frappe.query_reports["FTTH GIS Summary"] = {
	filters: [
		{ fieldname: "from_date", label: __("WO Received From"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("WO Received To"), fieldtype: "Date" },
		{ fieldname: "gis", label: __("GIS"), fieldtype: "Link", options: "GIS Node" },
		{ fieldname: "ibd_team", label: __("IBD Team"), fieldtype: "Link", options: "IBD Team" },
		{ fieldname: "segment", label: __("Segment"), fieldtype: "Select", options: "\nB2C\nB2B" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "warnings" && data && data.warnings > 0) {
			value = `<span style="color:var(--red-600)">${value}</span>`;
		}
		return value;
	},
};
