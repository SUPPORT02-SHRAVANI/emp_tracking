# ---------------------------------------------------------------------------------------------
# Patch: EVision Settings saved once with the values the code used before (DEFAULTS), so the page
# opens filled in and every rule keeps working as it did. Created 2026-11-27. Values already saved
# are kept; only empty ones are filled. Safe to run again.
# ---------------------------------------------------------------------------------------------

import frappe


def execute():
	frappe.reload_doc("emp_tracking", "doctype", "evision_settings")
	from emp_tracking.emp_tracking.doctype.evision_settings.evision_settings import DEFAULTS

	doc = frappe.get_single("EVision Settings")
	for field, value in DEFAULTS.items():
		# runs once (Patch Log), before anyone has used the page, so 0 here is still "never set"
		if doc.get(field) in (None, "", 0):
			doc.set(field, value)
	doc.save(ignore_permissions=True)
