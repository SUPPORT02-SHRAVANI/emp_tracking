"""Employee: company-wise Employee Code (custom_employee_code), e.g. IPT-0001.

Created: 2026-11-20

How it works:
- Each Company has an "Employee Code Prefix" (Company.custom_employee_code_prefix, a Custom Field
  made by after_migrate below): RKBG IPTECH → IPT, RKBG AUTOTECH → AUT, RKBG INFRATECH → INF.
- The Employee form (public/js/employee.js) shows the next code as soon as a company is picked
  (get_next_employee_code; read only, the counter is not used up).
- On insert (before_insert doc event) the code is fixed for good: a blank code, a code of another
  prefix, or a code already used by another employee gets the next number of the company's
  counter (Series "<PREFIX>-"). A free code with the right prefix (typed, or from Data Import) is
  kept and the counter is moved up to it, so later codes never clash with imported ones.
- The Employee ID (name) is not touched: it stays on the "Employee Master ID" naming series.
- Companies without a prefix (e.g. SWSPL) are left alone.

Change log:
	2026-11-20  Created: Employee ID series per company (named the Employee IPT-0001 ...).
	2026-11-20  Changed: the series now fills Employee Code (custom_employee_code) instead of the
	            Employee ID, and the form shows the code as soon as the company is picked. Reason: the
	            form's Employee ID is the "Employee Master ID" (RKBG-MID-) series; IPT-#### is the
	            separate Employee Code, as in the employee sheet.
"""

import re

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.model.naming import make_autoname

PREFIX_FIELD = "custom_employee_code_prefix"
CODE_FIELD = "custom_employee_code"  # "Employee Code" Custom Field on Employee (made in the UI)

# Default prefixes, written only where the company exists and its prefix is still blank, so a prefix
# changed later in the Company form is never overwritten by a migrate.
DEFAULT_PREFIXES = {
	"RKBG IPTECH": "IPT",
	"RKBG AUTOTECH": "AUT",
	"RKBG INFRATECH": "INF",
}


def employee_code_prefix(company):
	"""The company's Employee Code Prefix, upper case without a trailing '-', or None."""
	if not company or not frappe.get_meta("Company").has_field(PREFIX_FIELD):
		return None  # field not created yet (code deployed before migrate)
	prefix = (frappe.db.get_value("Company", company, PREFIX_FIELD) or "").strip().strip("-").upper()
	return prefix or None


def _series_current(prefix):
	# make_autoname("IPT-.####") keeps its counter in the Series table under the key "IPT-".
	# Plain SQL: tabSeries has no creation column, so frappe.db.get_value (orders by creation) fails.
	row = frappe.db.sql("select `current` from `tabSeries` where `name` = %s", f"{prefix}-")
	return int(row[0][0] or 0) if row else 0


@frappe.whitelist()
def get_next_employee_code(company):
	"""Preview for the form: the code the next employee of this company will get (not reserved)."""
	prefix = employee_code_prefix(company)
	return f"{prefix}-{_series_current(prefix) + 1:04d}" if prefix else None


def before_insert(doc, method=None):
	# Date: 2026-11-20
	prefix = employee_code_prefix(doc.company)
	if not prefix or not doc.meta.has_field(CODE_FIELD):
		return
	code = (doc.get(CODE_FIELD) or "").strip().upper()
	match = re.fullmatch(rf"{re.escape(prefix)}-(\d+)", code)
	used = code and frappe.db.exists("Employee", {CODE_FIELD: code})
	if match and not used:
		# keep the given code (imported / typed) and move the counter up to it, so it is never given again
		number = int(match.group(1))
		if number > _series_current(prefix):
			# insert or raise the counter in one statement (no ORM: tabSeries is not a normal doctype table)
			frappe.db.sql(
				"insert into `tabSeries` (`name`, `current`) values (%s, %s) "
				"on duplicate key update `current` = greatest(`current`, values(`current`))",
				(f"{prefix}-", number),
			)
		doc.set(CODE_FIELD, code)
		return
	# blank, other prefix (company changed), or taken by someone else (form preview raced): next number
	while True:
		code = make_autoname(f"{prefix}-.####", "Employee", doc)
		if not frappe.db.exists("Employee", {CODE_FIELD: code}):
			break
	doc.set(CODE_FIELD, code)


def after_migrate():
	"""Keeps the prefix field and the default prefixes on every migrate; never fails a deploy."""
	try:
		setup()
	except Exception:
		frappe.log_error(title="emp_tracking: Employee code prefix setup after migrate failed")


def setup():
	create_custom_fields(
		{
			"Company": [
				{
					"fieldname": PREFIX_FIELD,
					"label": "Employee Code Prefix",
					"fieldtype": "Data",
					"insert_after": "abbr",
					"description": "New employees of this company get an Employee Code like PREFIX-0001 "
					"(e.g. IPT-0001). Leave blank for no automatic code.",
				}
			]
		},
		update=True,
	)
	for company, prefix in DEFAULT_PREFIXES.items():
		if frappe.db.exists("Company", company) and not frappe.db.get_value("Company", company, PREFIX_FIELD):
			frappe.db.set_value("Company", company, PREFIX_FIELD, prefix, update_modified=False)
