// ---------------------------------------------------------------------------------------------
// Shift Assignment list: "Weekly Roster" button. Created 2026-11-25.
//
// How this file works
//   Added through doctype_list_js in hooks.py. Frappe runs it after HRMS's own
//   shift_assignment_list.js, so it keeps HRMS's onload (the "Shift Tools" button) and adds a
//   "Weekly Roster" button next to it.
//   The dialog takes employees, a shift rotation (in order), a start date and a number of weeks.
//   "Preview" shows the plan (server dry run); "Create" makes one submitted Shift Assignment per
//   employee per week via emp_tracking.shift_roster.create_weekly_roster. Weeks that already
//   have an active assignment are skipped, never changed.
//   Checked against HRMS 16.53.0 (listview_settings["Shift Assignment"].onload).
//
// Change log
//   2026-11-25  Created.
// ---------------------------------------------------------------------------------------------

(function () {
	const DT = "Shift Assignment";
	const METHOD = "emp_tracking.shift_roster.create_weekly_roster";
	const esc = frappe.utils.escape_html;

	const settings = (frappe.listview_settings[DT] = frappe.listview_settings[DT] || {});
	const hrms_onload = settings.onload;

	settings.onload = function (list_view) {
		if (hrms_onload) hrms_onload(list_view);
		// Only users who can create Shift Assignments get the button (server checks again).
		if (frappe.model.can_create(DT)) {
			list_view.page.add_inner_button(__("Weekly Roster"), () => open_roster_dialog(list_view));
		}
	};

	// Next Monday (or today if today is Monday): rosters normally run Monday to Sunday.
	function next_monday() {
		const d = moment();
		const add = (8 - d.isoWeekday()) % 7;
		return d.add(add, "days").format("YYYY-MM-DD");
	}

	function open_roster_dialog(list_view) {
		const d = new frappe.ui.Dialog({
			title: __("Weekly Shift Roster"),
			size: "large",
			fields: [
				{
					fieldname: "employees",
					label: __("Employees"),
					fieldtype: "MultiSelectList",
					reqd: 1,
					get_data: (txt) =>
						frappe.db.get_link_options("Employee", txt, { status: "Active" }),
				},
				{ fieldtype: "Column Break" },
				{
					fieldname: "start_date",
					label: __("Start Date"),
					fieldtype: "Date",
					reqd: 1,
					default: next_monday(),
					description: __("Each week runs 7 days from this date."),
				},
				{
					fieldname: "weeks",
					label: __("Number of Weeks"),
					fieldtype: "Int",
					reqd: 1,
					default: 4,
				},
				{ fieldtype: "Section Break", label: __("Shift Rotation") },
				{
					fieldname: "rotation",
					fieldtype: "Table",
					cannot_add_rows: false,
					in_place_edit: true,
					description: __(
						"Week 1 gets row 1, week 2 row 2, and so on, then it starts again. One row = same shift every week."
					),
					fields: [
						{
							fieldname: "shift_type",
							label: __("Shift Type"),
							fieldtype: "Link",
							options: "Shift Type",
							in_list_view: 1,
							reqd: 1,
						},
					],
					data: [],
				},
				{ fieldtype: "Section Break" },
				{ fieldname: "preview", fieldtype: "HTML" },
			],
			primary_action_label: __("Create"),
			primary_action: () => run(false),
			secondary_action_label: __("Preview"),
			secondary_action: () => run(true),
		});

		function get_args() {
			const v = d.get_values();
			if (!v) return null;
			const shifts = (v.rotation || []).map((r) => r.shift_type).filter(Boolean);
			if (!shifts.length) {
				frappe.msgprint(__("Add at least one shift to the rotation."));
				return null;
			}
			return {
				employees: v.employees,
				shift_types: shifts,
				start_date: v.start_date,
				weeks: v.weeks,
			};
		}

		function run(dry_run) {
			const args = get_args();
			if (!args) return;
			frappe.call({
				method: METHOD,
				args: { ...args, dry_run: dry_run ? 1 : 0 },
				freeze: true,
				freeze_message: dry_run ? __("Preparing preview...") : __("Creating shift assignments..."),
				callback: (r) => {
					if (!r.message) return;
					render(r.message, dry_run);
					if (!dry_run) {
						list_view.refresh();
						frappe.show_alert({
							message: __("{0} created, {1} skipped, {2} failed", [
								r.message.created,
								r.message.skipped,
								r.message.failed,
							]),
							indicator: r.message.failed ? "orange" : "green",
						});
					}
				},
			});
		}

		// Result / preview table. Status colours use Frappe indicator classes (theme-safe).
		function render(res, dry_run) {
			const colour = { "To Create": "blue", Created: "green", Skipped: "gray", Failed: "red" };
			const rows = res.rows
				.map((r) => {
					const link = r.assignment
						? `<a href="/app/shift-assignment/${encodeURIComponent(r.assignment)}" target="_blank">${esc(r.assignment)}</a>`
						: "";
					return `<tr>
						<td>${esc(r.employee)}<div class="text-muted small">${esc(r.employee_name || "")}</div></td>
						<td>${r.week}</td>
						<td>${frappe.datetime.str_to_user(r.start_date)} – ${frappe.datetime.str_to_user(r.end_date)}</td>
						<td>${esc(r.shift_type)}</td>
						<td><span class="indicator-pill ${colour[r.status] || "gray"}">${esc(__(r.status))}</span>
							<div class="small">${link} ${esc(r.message || "")}</div></td>
					</tr>`;
				})
				.join("");
			const summary = dry_run
				? __("Preview only, nothing created yet. Click Create to make these assignments.")
				: __("{0} created, {1} skipped, {2} failed.", [res.created, res.skipped, res.failed]);
			d.fields_dict.preview.$wrapper.html(`
				<p class="text-muted">${esc(summary)}</p>
				<div style="max-height: 360px; overflow: auto;">
					<table class="table table-bordered table-sm">
						<thead><tr>
							<th>${__("Employee")}</th><th>${__("Week")}</th><th>${__("Dates")}</th>
							<th>${__("Shift")}</th><th>${__("Status")}</th>
						</tr></thead>
						<tbody>${rows}</tbody>
					</table>
				</div>`);
		}

		d.show();
	}
})();
