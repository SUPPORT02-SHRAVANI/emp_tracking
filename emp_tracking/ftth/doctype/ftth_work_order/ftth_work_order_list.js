// Copyright (c) 2026, Softworld and contributors
// For license information, please see license.txt

const FTTH_STATUS_COLOR = {
	New: "gray",
	Survey: "orange",
	"Fiber Laid": "yellow",
	"Splicing Done": "blue",
	"RFS Done": "green",
};

frappe.listview_settings["FTTH Work Order"] = {
	add_fields: ["status", "has_warnings", "gis"],
	get_indicator(doc) {
		const color = FTTH_STATUS_COLOR[doc.status] || "gray";
		return [__(doc.status), color, `status,=,${doc.status}`];
	},
	formatters: {
		end_location(value, df, doc) {
			const flag = doc.has_warnings
				? ` <span class="indicator-pill red" title="${__("Has warnings")}" style="padding:0 6px">!</span>`
				: "";
			return `${frappe.utils.escape_html(value || "")}${flag}`;
		},
	},
	onload(listview) {
		listview.page.add_inner_button(__("Only with warnings"), () => {
			listview.filter_area.add([["FTTH Work Order", "has_warnings", "=", 1]]);
		});
	},
};
