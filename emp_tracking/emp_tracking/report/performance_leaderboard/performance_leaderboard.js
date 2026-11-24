// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// Performance Leaderboard: filters, medals, level colours and progress bars (created 2026-10-24).
// 2026-10-24: "Source" filter (New Project / FTTH Work Order / both); period now defaults to
//             1 January of this year, because the FTTH data has no RFS in the current month.
// 2026-10-24: "Maintenance Calls" source (Staff Monthly Performance) with a Designation filter.
//             Choosing it jumps the period to the earliest month on record and ranks people.
// 2026-10-31: New Project merged into FTTH Work Order: "New Project" source and the
//             "EVisions Team" rank (New Project only) removed.

frappe.query_reports["Performance Leaderboard"] = {
	filters: [
		{
			fieldname: "source",
			label: __("Source"),
			fieldtype: "Select",
			options: "\nFTTH Work Order\nMaintenance Calls",
			description: __("Blank = FTTH Work Orders"),
			on_change(report) {
				const calls = report.get_filter_value("source") === "Maintenance Calls";
				report.toggle_filter_display("designation", !calls);
				report.toggle_filter_display("rank_by", calls);
				report.toggle_filter_display("area", calls);
				if (!calls) return report.refresh();
				// Supervisor and Splicer scores use different weights: compare like with like
				if (!report.get_filter_value("designation")) report.set_filter_value("designation", "Splicer");
				// The sheet data is April 2025 - March 2026; start the period at the first month on record
				frappe.db
					.get_list("Staff Monthly Performance", { fields: ["month"], order_by: "month asc", limit: 1 })
					.then((rows) => {
						if (rows.length) report.set_filter_value("from_date", rows[0].month);
						else report.refresh();
					});
			},
		},
		{
			fieldname: "designation",
			label: __("Designation"),
			fieldtype: "Select",
			options: "\nSupervisor\nSplicer\nRider",
			hidden: 1,
		},
		{
			fieldname: "rank_by",
			label: __("Rank"),
			fieldtype: "Select",
			options: "Vendor\nEmployee\nFiber Pulling Team\nArea\nArea Manager\nGIS",
			// Vendor / IBD Team first: the FTTH data has almost no Splicer / Rider filled in yet
			default: "Vendor",
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("RFS From"),
			fieldtype: "Date",
			default: frappe.datetime.year_start(),
		},
		{ fieldname: "to_date", label: __("RFS To"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "area", label: __("Area"), fieldtype: "Data" },
		{ fieldname: "top", label: __("Show Top"), fieldtype: "Int" },
	],

	onload(report) {
		// Point values are editable by Project Heads / System Managers
		if (frappe.model.can_write("Leaderboard Settings")) {
			report.page.add_inner_button(__("Points Settings"), () => frappe.set_route("Form", "Leaderboard Settings"));
		}
	},

	formatter(value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);

		// Medal next to the rank for the podium
		if (column.fieldname === "rank") {
			return data.medal ? `<b>${data.medal} ${data.rank}</b>` : `${data.rank}`;
		}
		if (column.fieldname === "points") {
			return `<b>${default_formatter(value, row, column, data)}</b>`;
		}
		// Progress bar towards the next level; Frappe CSS variables keep light/dark themes working
		if (column.fieldname === "level_progress") {
			if (!data.next_level) return `<span style="color:var(--text-muted)">${__("Max level")}</span>`;
			const pct = Math.max(0, Math.min(100, data.level_progress || 0));
			const tip = __("{0} more points to {1}", [data.points_to_next, __(data.next_level)]);
			return `<div title="${frappe.utils.escape_html(tip)}" style="background:var(--gray-200);border-radius:6px;height:10px;margin-top:6px">
				<div style="width:${pct}%;background:var(--blue-500);height:10px;border-radius:6px"></div></div>`;
		}
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "level") {
			const color = { Diamond: "cyan", Platinum: "purple", Gold: "yellow", Silver: "gray", Bronze: "orange" }[data.level];
			if (color) value = `<span style="color:var(--${color}-600);font-weight:600">${value}</span>`;
		}
		if (["missing_proof", "rework"].includes(column.fieldname) && data[column.fieldname] > 0) {
			value = `<span style="color:var(--red-600)">${value}</span>`;
		}
		return value;
	},
};
