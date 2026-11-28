# ---------------------------------------------------------------------------------------------
# Patch: EVision Settings gets its editable formula rows (SLA In, In SLA %, Pending now, office
# Present-from / Absent-under, In field %), each set to the formula the code used before, so
# nothing changes until someone edits one. Created 2026-11-28. Saving the page adds missing rows
# (EVisionSettings.sync_formulas); saved formulas are kept. Safe to run again.
# ---------------------------------------------------------------------------------------------

import frappe


def execute():
	frappe.reload_doc("emp_tracking", "doctype", "evision_formula")
	frappe.reload_doc("emp_tracking", "doctype", "evision_settings")
	frappe.get_single("EVision Settings").save(ignore_permissions=True)
