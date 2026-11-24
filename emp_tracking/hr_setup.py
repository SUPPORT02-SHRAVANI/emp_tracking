# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""HR / Payroll setup shipped with the app: Salary Components, Leave Types, Salary Structures,
HR Settings, Payroll Settings and the "RKBG IPTECH" Letter Head.

Created: 2026-11-24

Why not plain fixtures: Frappe re-imports fixtures on every migrate and overwrites the record, so
HR edits made on another site (formulas, accounts, settings) would be reset on each deploy, and a
submitted Salary Structure whose Company is missing would stop the migrate. Here every record is
only CREATED when it does not exist yet; existing records are never changed. Settings are applied
once per site (SETTINGS_FLAG). No employee or transaction data (Employees, Salary Slips, Payroll
Entries, Assignments) is shipped.

The records live as JSON in emp_tracking/hr_setup/ (one file per doctype). Refresh them from the
site where HR set them up with:

	bench --site newsite.local execute emp_tracking.hr_setup.export_hr_setup

Form/list settings of the HR doctypes (Property Setters) are fixtures instead (hooks.py), because
those should be the same on every site.
"""

import json
import os

import frappe
from frappe.model import table_fields

DATA_DIR = os.path.join(os.path.dirname(__file__), "hr_setup")

# Order matters on import: components before the leave types / structures that link to them.
MASTERS = ("Salary Component", "Leave Type", "Salary Structure")
SETTINGS = ("HR Settings", "Payroll Settings")
LETTER_HEADS = ("RKBG IPTECH",)
# Set once the settings were applied on a site, so later changes made there by HR are kept.
SETTINGS_FLAG = "emp_tracking_hr_settings_applied"

# The letter head shows the RKBG Group logo, a site file (/files/...) that does not exist on other
# sites; the export points it at the copy shipped in public/images instead.
LOGO_SITE_URL = "/files/rkbg_group_logo.png"
LOGO_APP_URL = "/assets/emp_tracking/images/rkbg_group_logo.png"

# Bookkeeping fields Frappe sets itself; left out of the JSON.
SKIP_FIELDS = {
	"owner", "creation", "modified", "modified_by", "amended_from",
	"_user_tags", "_comments", "_assign", "_liked_by", "_seen",
}
SKIP_CHILD_FIELDS = SKIP_FIELDS | {"name", "parent", "parentfield", "parenttype", "docstatus"}


# ---------------------------------------------------------------------------------------------
# Export (run by hand on the site where HR set things up)
# ---------------------------------------------------------------------------------------------


def _clean(doc):
	"""Return the doc as a plain dict without bookkeeping fields, child rows without their ids."""
	d = {k: v for k, v in doc.as_dict(no_nulls=True, convert_dates_to_str=True).items() if k not in SKIP_FIELDS}
	for df in doc.meta.get_table_fields():
		d[df.fieldname] = [
			{k: v for k, v in row.items() if k not in SKIP_CHILD_FIELDS}
			for row in d.get(df.fieldname) or []
		]
	return d


def _write(filename, data):
	os.makedirs(DATA_DIR, exist_ok=True)
	with open(os.path.join(DATA_DIR, filename), "w", encoding="utf-8") as f:
		json.dump(data, f, indent=1, ensure_ascii=False, sort_keys=True, default=str)
		f.write("\n")


def export_hr_setup():
	"""Write the HR masters, settings and letter head of this site to emp_tracking/hr_setup/*.json."""
	for doctype in MASTERS:
		# Cancelled structures (docstatus 2) are history, not setup.
		filters = {"docstatus": ["<", 2]} if doctype == "Salary Structure" else {}
		names = frappe.get_all(doctype, filters=filters, pluck="name", order_by="name")
		_write(frappe.scrub(doctype) + ".json", [_clean(frappe.get_doc(doctype, n)) for n in names])

	settings = {}
	for doctype in SETTINGS:
		d = _clean(frappe.get_single(doctype))
		for k in ("name", "doctype", "docstatus", "idx"):
			d.pop(k, None)
		settings[doctype] = d
	_write("settings.json", settings)

	heads = []
	for name in LETTER_HEADS:
		if frappe.db.exists("Letter Head", name):
			d = _clean(frappe.get_doc("Letter Head", name))
			d["is_default"] = 0  # never take over another site's default letter head
			for k in ("content", "footer"):
				if d.get(k):
					d[k] = d[k].replace(LOGO_SITE_URL, LOGO_APP_URL)
			heads.append(d)
	_write("letter_head.json", heads)
	print(f"HR setup exported to {DATA_DIR}")


# ---------------------------------------------------------------------------------------------
# Import (after every migrate; only creates what is missing)
# ---------------------------------------------------------------------------------------------


def _read(filename):
	path = os.path.join(DATA_DIR, filename)
	if not os.path.exists(path):
		return []
	with open(path, encoding="utf-8") as f:
		return json.load(f)


def _link_ok(doctype, value):
	return not value or bool(frappe.db.exists(doctype, value))


def _drop_missing_links(doctype, d):
	"""Blank parent Link fields whose target is missing on this site (accounts, letter heads ...),
	so the insert does not fail on a site with a different chart of accounts."""
	meta = frappe.get_meta(doctype)
	for df in meta.get("fields", {"fieldtype": "Link"}):
		if d.get(df.fieldname) and not _link_ok(df.options, d[df.fieldname]):
			d[df.fieldname] = None


def _create_salary_component(d):
	# Account rows are per company; keep only rows whose company and account exist here.
	d["accounts"] = [
		r for r in d.get("accounts") or []
		if _link_ok("Company", r.get("company")) and _link_ok("Account", r.get("account"))
	]
	_drop_missing_links("Salary Component", d)
	frappe.get_doc(d).insert(ignore_permissions=True)


def _create_leave_type(d):
	_drop_missing_links("Leave Type", d)
	frappe.get_doc(d).insert(ignore_permissions=True)


def _create_salary_structure(d):
	# A structure belongs to one company and lists components; skip it when either is missing.
	if not frappe.db.exists("Company", d.get("company")):
		return
	for table in ("earnings", "deductions"):
		for row in d.get(table) or []:
			if not frappe.db.exists("Salary Component", row.get("salary_component")):
				return
	company = d["company"]
	_drop_missing_links("Salary Structure", d)
	d["company"] = company
	submit = d.pop("docstatus", 0) == 1
	doc = frappe.get_doc(d)
	doc.insert(ignore_permissions=True)
	if submit:
		doc.submit()


CREATORS = {
	"Salary Component": _create_salary_component,
	"Leave Type": _create_leave_type,
	"Salary Structure": _create_salary_structure,
}


def _apply_settings():
	"""Copy HR / Payroll Settings once per site; later edits on that site are left alone."""
	if frappe.db.get_default(SETTINGS_FLAG):
		return
	data = _read("settings.json") or {}
	for doctype, values in data.items():
		doc = frappe.get_single(doctype)
		meta = frappe.get_meta(doctype)
		for field, value in values.items():
			df = meta.get_field(field)
			if not df or df.fieldtype in table_fields:
				continue
			if df.fieldtype == "Link" and not _link_ok(df.options, value):
				continue
			doc.set(field, value)
		doc.flags.ignore_permissions = True
		doc.save()
	frappe.db.set_default(SETTINGS_FLAG, "1")


def _run(title, fn, *args):
	"""Run one step; a failure is logged and the migrate goes on."""
	try:
		fn(*args)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"emp_tracking HR setup: {title}")


def after_migrate():
	"""hooks.py after_migrate: create the shipped HR setup where missing. Safe on every migrate."""
	if "hrms" not in frappe.get_installed_apps():
		return
	for doctype in MASTERS:
		for d in _read(frappe.scrub(doctype) + ".json"):
			if not frappe.db.exists(doctype, d.get("name")):
				_run(f"{doctype} {d.get('name')}", CREATORS[doctype], dict(d))
	for d in _read("letter_head.json"):
		if not frappe.db.exists("Letter Head", d.get("name")):
			_run(f"Letter Head {d.get('name')}", lambda x: frappe.get_doc(x).insert(ignore_permissions=True), dict(d))
	_run("HR / Payroll Settings", _apply_settings)
