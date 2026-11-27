# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Patch: office shift judged on hours worked, not on the shift's clock times
#
# How this file works
#   The office Shift Type "Office 09:30-18:30 (Mobile App)" was created on 2026-11-23 as "Present if
#   punched in", accepting punches 08:30-21:30 only. User's rule (2026-11-27): if office hours are
#   completed, mark Present irrespective of the shift, e.g. punch in 10:00, out 19:00.
#   app_attendance.ensure_shift_types() never overwrites an existing Shift Type, so this one-time
#   patch copies the new office settings (punch window 00:00-23:59, 8 h 45 min = Present (9 h with
#   15 min grace), 4.5 h = Half Day, less = Absent) from app_attendance.SHIFT_TYPES onto the
#   existing record.
#   Saved through the document API so HRMS's own Shift Type validation runs.
#   On a new site the Shift Type does not exist yet; after_migrate creates it with these settings.
#
# Change log
#   2026-11-27  Created.
#   2026-11-27  15 min grace (Present from 8 h 45 min); re-run on newsite.local with --force.
# ---------------------------------------------------------------------------------------------

import frappe

from emp_tracking.app_attendance import OFFICE_SHIFT, SHIFT_TYPES

FIELDS = (
	"begin_check_in_before_shift_start_time",
	"allow_check_out_after_shift_end_time",
	"working_hours_threshold_for_half_day",
	"working_hours_threshold_for_absent",
)


# Date: 2026-11-27
def execute():
	if not frappe.db.exists("Shift Type", OFFICE_SHIFT):
		return
	doc = frappe.get_doc("Shift Type", OFFICE_SHIFT)
	doc.update({f: SHIFT_TYPES[OFFICE_SHIFT][f] for f in FIELDS})
	doc.save(ignore_permissions=True)
