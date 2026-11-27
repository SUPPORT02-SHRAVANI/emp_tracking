# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""Weekly Shift Roster: give employees a different shift each week.

Created: 2026-11-25

Why: HRMS 16.53.0 has no "Shift Assignment Schedule" doctype, so a weekly rotation (e.g. Office one
week, Field 12 Hours the next) had to be entered as one Shift Assignment per week by hand.

How it works:
- The "Weekly Roster" button on the Shift Assignment list (public/js/shift_assignment_list.js) sends
  the employees, the shift rotation (1 or more Shift Types, in order), a start date and the number of
  weeks to create_weekly_roster().
- Week i runs start_date + 7*i .. start_date + 7*i + 6 and gets rotation[i % len(rotation)].
- Each week becomes an ordinary submitted Shift Assignment, which overrides the employee's Default
  Shift on those dates. Auto Attendance, checkin shift matching and reports use it as usual.
- A week is skipped (not an error) when the employee already has an active submitted Shift Assignment
  overlapping it, so the tool can be run again safely and never touches existing assignments.
- dry_run=1 returns the same plan without creating anything (the dialog's preview).

Upgrade safety: no HRMS code is changed; records are created through the normal doc API, so HRMS's
own validation and the user's Shift Assignment permissions apply. Checked against HRMS 16.53.0
(Shift Assignment fields: employee, company, shift_type, start_date, end_date, status).

Change log:
	2026-11-25  Created.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, getdate

# Safety limits so a mistaken entry cannot create thousands of documents in one request.
MAX_WEEKS = 26
MAX_EMPLOYEES = 200


def _as_list(value):
	"""Accept a list or a JSON string (frappe.call sends lists as JSON)."""
	if isinstance(value, str):
		value = json.loads(value) if value.strip().startswith("[") else [value]
	return [v for v in (value or []) if v]


@frappe.whitelist()
def create_weekly_roster(employees, shift_types, start_date, weeks, dry_run=0):
	"""Create (or preview with dry_run) one Shift Assignment per employee per week.

	Returns {"rows": [{employee, employee_name, week, start_date, end_date, shift_type, status,
	assignment, message}], "created": n, "skipped": n, "failed": n}.
	status is "To Create" (dry run), "Created", "Skipped" (overlap) or "Failed".
	"""
	employees = list(dict.fromkeys(_as_list(employees)))
	shift_types = _as_list(shift_types)
	weeks = int(weeks or 0)
	dry_run = int(dry_run or 0)
	start = getdate(start_date)

	# Input validation: clear messages instead of HRMS errors halfway through the run.
	if not employees:
		frappe.throw(_("Select at least one employee."))
	if not shift_types:
		frappe.throw(_("Add at least one shift to the rotation."))
	if not 1 <= weeks <= MAX_WEEKS:
		frappe.throw(_("Number of weeks must be between 1 and {0}.").format(MAX_WEEKS))
	if len(employees) > MAX_EMPLOYEES:
		frappe.throw(_("Select at most {0} employees at a time.").format(MAX_EMPLOYEES))
	for st in set(shift_types):
		if not frappe.db.exists("Shift Type", st):
			frappe.throw(_("Shift Type {0} not found.").format(st))

	# Permission check up front (insert/submit below check again per document).
	if not dry_run:
		frappe.has_permission("Shift Assignment", "create", throw=True)
		frappe.has_permission("Shift Assignment", "submit", throw=True)

	emp_info = {
		e.name: e
		for e in frappe.get_all(
			"Employee",
			filters={"name": ["in", employees]},
			fields=["name", "employee_name", "company", "status"],
		)
	}
	missing = [e for e in employees if e not in emp_info]
	if missing:
		frappe.throw(_("Employee not found: {0}").format(", ".join(missing)))

	rows, counts = [], {"Created": 0, "Skipped": 0, "Failed": 0}
	for emp in employees:
		info = emp_info[emp]
		for i in range(weeks):
			week_start, week_end = add_days(start, 7 * i), add_days(start, 7 * i + 6)
			row = {
				"employee": emp,
				"employee_name": info.employee_name,
				"week": i + 1,
				"start_date": week_start,
				"end_date": week_end,
				"shift_type": shift_types[i % len(shift_types)],
				"assignment": None,
				"message": "",
			}

			# Overlap check: any active submitted assignment whose dates touch this week
			# (an open-ended one has end_date empty). Skipping keeps existing rosters intact
			# and makes a second run with the same input create nothing new.
			existing = _overlapping_assignment(emp, week_start, week_end)
			if existing:
				row.update(status="Skipped", assignment=existing.name,
					message=_("Already has {0}").format(existing.shift_type))
				counts["Skipped"] += 1
			elif info.status != "Active":
				row.update(status="Skipped", message=_("Employee is {0}").format(info.status))
				counts["Skipped"] += 1
			elif dry_run:
				row["status"] = "To Create"
			else:
				_create_assignment(row, info.company, counts)
			rows.append(row)

	return {
		"rows": rows,
		"created": counts["Created"],
		"skipped": counts["Skipped"],
		"failed": counts["Failed"],
	}


def _overlapping_assignment(employee, start, end):
	"""First active submitted Shift Assignment of the employee that overlaps start..end, or None."""
	sa = frappe.qb.DocType("Shift Assignment")
	result = (
		frappe.qb.from_(sa)
		.select(sa.name, sa.shift_type)
		.where(
			(sa.employee == employee)
			& (sa.docstatus == 1)
			& (sa.status == "Active")
			& (sa.start_date <= end)
			& ((sa.end_date >= start) | sa.end_date.isnull())
		)
		.limit(1)
		.run(as_dict=True)
	)
	return result[0] if result else None


def _create_assignment(row, company, counts):
	"""Insert and submit one assignment. A failure rolls back only this week (savepoint),
	so one bad row (e.g. an HRMS validation error) does not undo the weeks already created."""
	savepoint = "weekly_roster_row"
	frappe.db.savepoint(savepoint)
	try:
		doc = frappe.get_doc({
			"doctype": "Shift Assignment",
			"employee": row["employee"],
			"company": company,
			"shift_type": row["shift_type"],
			"start_date": row["start_date"],
			"end_date": row["end_date"],
			"status": "Active",
		})
		doc.insert()
		doc.submit()
		row.update(status="Created", assignment=doc.name)
		counts["Created"] += 1
	except Exception as e:
		frappe.db.rollback(save_point=savepoint)
		frappe.clear_messages()  # the error is shown in the result table instead of a popup
		row.update(status="Failed", message=str(e)[:200])
		counts["Failed"] += 1
