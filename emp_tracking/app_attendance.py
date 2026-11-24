# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""Attendance from mobile-app punches, using HRMS's own Auto Attendance.

Created: 2026-11-23

How it works:
- The mobile app saves every punch in / punch out as an Employee Checkin (log type IN / OUT).
- HRMS turns checkins into Attendance only for employees with a shift: its hourly scheduler job
  (Shift Type.process_auto_attendance_for_all_shifts) groups each employee's checkins by shift and
  creates the Attendance that payroll uses (Payroll Settings: Payroll Based On = Attendance).
  It also marks Absent on working days without a punch, from the Shift Type's
  "Process Attendance After" date.
- Who: only employees with Mode of Attendance (custom_mode_of_attendance) = "Mobile App" (user's
  decision, 2026-11-23). Unolo / Biometric / blank employees are never given these shifts, so HRMS
  does not mark them Absent.
- Two Shift Types (user's decision, 2026-11-23), both "Present if punched in" (no half-day / absent
  hour thresholds) and "Last Sync of Checkin" kept current by HRMS (auto_update_last_sync):
    * OFFICE_SHIFT 09:30-18:30.
    * FIELD_SHIFT for riders, splicers and the maintenance team: a 12-hour day counted from their own
      punch-in time. HRMS shifts have fixed clock times, so this shift accepts a punch-in at any time
      of the day (06:00-18:00 with 6 h before / 6 h after allowed = 00:00-23:59); any punch-in that
      day counts as Present.
- The shift reaches the employee through the standard Employee "Default Shift" field, which HR can
  still change by hand. employee_before_save() fills it when Mode of Attendance becomes "Mobile App"
  and clears it (only if it is one of these two shifts) when the mode changes to something else.

Upgrade safety: no HRMS code is changed. Shift Types are ordinary records created once (never
overwritten, so HR's later edits stay); the Mode of Attendance option comes from fixtures.

Checked against HRMS 16.53.0 (Shift Type fields, get_assigned_employees(consider_default_shift=True),
update_last_sync_of_checkin). After an HRMS upgrade, re-check those names in
hrms/hr/doctype/shift_type/shift_type.py.

Change log:
	2026-11-23  Created.
"""

import re

import frappe
from frappe.utils import today

MODE_FIELD = "custom_mode_of_attendance"
MOBILE_APP = "Mobile App"

OFFICE_SHIFT = "Office 09:30-18:30 (Mobile App)"
FIELD_SHIFT = "Field 12 Hours (Mobile App)"
OUR_SHIFTS = (OFFICE_SHIFT, FIELD_SHIFT)

# Settings shared by both shifts. Thresholds 0 = not used, so any punch IN marks the day Present.
COMMON_SHIFT_SETTINGS = {
	"enable_auto_attendance": 1,
	# HRMS processes only checkins before "Last Sync of Checkin"; let HRMS move it forward itself.
	"auto_update_last_sync": 1,
	# The app always sends the log type, so IN / OUT never have to be guessed from the order.
	"determine_check_in_and_check_out": "Strictly based on Log Type in Employee Checkin",
	"working_hours_calculation_based_on": "First Check-in and Last Check-out",
	"working_hours_threshold_for_half_day": 0,
	"working_hours_threshold_for_absent": 0,
	"enable_late_entry_marking": 0,
	"enable_early_exit_marking": 0,
	"mark_auto_attendance_on_holidays": 0,
}

SHIFT_TYPES = {
	OFFICE_SHIFT: {
		"start_time": "09:30:00",
		"end_time": "18:30:00",
		"begin_check_in_before_shift_start_time": 60,  # punches from 08:30 count
		"allow_check_out_after_shift_end_time": 180,  # punch-outs until 21:30 count
		"color": "Blue",
	},
	FIELD_SHIFT: {
		"start_time": "06:00:00",
		"end_time": "18:00:00",
		# 6 h before start and just under 6 h after end: the whole day 00:00-23:59, so a 12-hour day
		# can start whenever the rider / splicer punches in.
		"begin_check_in_before_shift_start_time": 360,
		"allow_check_out_after_shift_end_time": 359,
		"color": "Orange",
	},
}

# Riders, splicers and the maintenance team work the 12-hour field shift (user, 2026-11-23).
FIELD_DESIGNATION = re.compile(r"rider|splicer|maintenance", re.IGNORECASE)


# Date: 2026-11-23
def after_migrate():
	"""hooks.py after_migrate: create the shifts, then give existing "Mobile App" employees one."""
	try:
		ensure_shift_types()
		assign_default_shifts()
	except Exception:
		# Never fail a deploy over this; the error is listed in the Error Log.
		frappe.log_error(title="emp_tracking: mobile-app attendance setup failed")


def ensure_shift_types():
	"""Creates the two Shift Types if they are missing. Existing ones are left as HR set them."""
	if not frappe.db.exists("DocType", "Shift Type"):
		return
	for name, settings in SHIFT_TYPES.items():
		if frappe.db.exists("Shift Type", name):
			continue
		doc = frappe.new_doc("Shift Type")
		doc.name = name
		doc.update({**COMMON_SHIFT_SETTINGS, **settings})
		# Absent marking starts on the day the shift is created, never for past dates.
		doc.process_attendance_after = today()
		doc.insert(ignore_permissions=True, set_name=name)


def assign_default_shifts():
	"""Fills Default Shift for active "Mobile App" employees that have none (HR's choice is kept)."""
	if not frappe.get_meta("Employee").has_field(MODE_FIELD):
		return
	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active", MODE_FIELD: MOBILE_APP, "default_shift": ("is", "not set")},
		fields=["name", "designation"],
	)
	leaders = _maintenance_team_leaders()
	for emp in employees:
		shift = _shift_for(emp.name, emp.designation, leaders)
		if shift:
			frappe.db.set_value("Employee", emp.name, "default_shift", shift)


# Date: 2026-11-23
def employee_before_save(doc, method=None):
	"""doc_events Employee.before_save: keep Default Shift in step with Mode of Attendance."""
	if not doc.meta.has_field(MODE_FIELD):
		return
	if doc.get(MODE_FIELD) == MOBILE_APP:
		if not doc.default_shift:
			shift = _shift_for(doc.name, doc.designation, _maintenance_team_leaders())
			if shift:
				doc.default_shift = shift
	elif doc.default_shift in OUR_SHIFTS:
		# Mode changed away from the app: stop HRMS from marking this employee Absent via our shift.
		doc.default_shift = None


def _shift_for(employee, designation, maintenance_leaders):
	"""Field 12-hour shift for riders / splicers / maintenance staff, office shift for the rest.
	Returns None while the Shift Type does not exist yet (before the first migrate), so saving an
	Employee never fails on a missing link."""
	is_field = bool(FIELD_DESIGNATION.search(designation or "")) or employee in maintenance_leaders
	shift = FIELD_SHIFT if is_field else OFFICE_SHIFT
	return shift if frappe.db.exists("Shift Type", shift) else None


def _maintenance_team_leaders():
	if not frappe.db.exists("DocType", "Maintenance Team"):
		return set()
	return set(
		frappe.get_all("Maintenance Team", filters={"status": "Active"}, pluck="team_leader")
	) - {None, ""}
