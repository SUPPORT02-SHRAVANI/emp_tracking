# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""Company fields used by the "RKBG Payslip Classic" print format.

Created: 2026-11-24

The classic payslip (laid out like the payslip Excel sheet) prints the company's full legal name
("RKBG IPTECH PVT. LTD.") and the company stamp under the slip. The Company records only hold the
short name ("RKBG IPTECH") and have no stamp image, so two Custom Fields are added to Company.
HR fills them in once per company; nothing is hard-coded in the print format.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Company": [
		{
			"fieldname": "custom_payslip_name",
			"label": "Name on Payslip",
			"fieldtype": "Data",
			"insert_after": "company_logo",
			"description": "Full legal name printed on the payslip, e.g. RKBG IPTECH PVT. LTD. "
			"Leave empty to print the Company name.",
			"translatable": 0,
		},
		{
			"fieldname": "custom_company_stamp",
			"label": "Company Stamp",
			"fieldtype": "Attach Image",
			"insert_after": "custom_payslip_name",
			"description": "Stamp / seal image printed under the payslip (RKBG Payslip Classic).",
		},
	],
}


def after_migrate():
	"""hooks.py after_migrate: (re)create the Company payslip fields. Safe to run on every migrate."""
	try:
		create_custom_fields(CUSTOM_FIELDS, update=True)
	except Exception:
		# Never fail a deploy over this; the error is listed in the Error Log.
		frappe.log_error(title="emp_tracking: Company payslip fields setup failed")
