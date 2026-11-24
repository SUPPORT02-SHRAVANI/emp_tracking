# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""Salary advance on the salary slip, like the "Advance" column of the attendance Excel.

Created: 2026-11-23

How it works (all standard HRMS, nothing in core is changed):
- The deduction Salary Component "Advance" (abbr ADV) is not in any Salary Structure. HR enters the
  amount per employee per month as an Additional Salary (component Advance, Payroll Date inside the
  month). HRMS adds it to that month's salary slip as a deduction and lowers Net Pay.
- An already-created draft slip picks it up only when it is saved again (or the Payroll Entry
  recreates the slips); HRMS does not refresh draft slips when the Additional Salary is submitted
  (checked on HRMS 16.53.0).
- "Advance" is posted to each company's "Employee Advances - <abbr>" account (set as data on the
  component, 2026-11-23, not from this file, so accounts stay editable by the accountant).
- Excel had a note next to the amount ("3000 fooding"); Additional Salary has no such field, so this
  module adds a Remarks custom field to it.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Additional Salary": [
		{
			"fieldname": "custom_remarks",
			"label": "Remarks",
			"fieldtype": "Small Text",
			"insert_after": "payroll_date",
			"description": "Why this amount is added / deducted, e.g. advance for fooding.",
			"translatable": 0,
		},
	],
}


def after_migrate():
	"""hooks.py after_migrate: (re)create the Remarks field. Safe to run on every migrate."""
	try:
		if frappe.db.exists("DocType", "Additional Salary"):
			create_custom_fields(CUSTOM_FIELDS, update=True)
	except Exception:
		# Never fail a deploy over this; the error is listed in the Error Log.
		frappe.log_error(title="emp_tracking: Additional Salary remarks field setup failed")
