"""Salary Structure Assignment: default "Leave Encashment Amount Per Day" = monthly Gross / 30.

Created: 2026-11-21

Business rule (RKBG, confirmed by HR on 2026-11-21):
- Every employee gets 15 leaves a year (Jan–Dec).
- Field employees: unused leaves are encashed. One leave day is paid at Gross (the assignment's
  "base") / 30, the same calendar-day rate used for salary.
- Office employees: unused leaves are carried forward (their leave type is not encashable, so this
  amount is never used for them).

HRMS reads the per-day amount from the employee's Salary Structure Assignment
(leave_encashment_amount_per_day, a standard field) when a Leave Encashment is made. Our salary
structures are shared by employees with different Gross, so the amount must be per assignment;
this hook fills it from "base" only when it is empty, so HR can still type another value.

Change log:
	2026-11-21  Created.
"""

import frappe
from frappe.utils import flt


def before_validate(doc, method=None):
	# only fill a blank value: an amount entered by HR is never overwritten
	if flt(doc.get("leave_encashment_amount_per_day")) > 0 or flt(doc.get("base")) <= 0:
		return
	doc.leave_encashment_amount_per_day = flt(flt(doc.base) / 30, 2)
