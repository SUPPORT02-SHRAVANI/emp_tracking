# ---------------------------------------------------------------------------------------------
# Patch: EVision Settings day / night call times from plain hours ("8", "20") to the 12-hour IST
# labels the page now shows ("8:00 AM", "8:00 PM"). Created 2026-11-28 (user: "show indian
# timing"). Saving the page converts them (EVisionSettings.validate). Safe to run again.
# ---------------------------------------------------------------------------------------------

import frappe


def execute():
	frappe.reload_doc("emp_tracking", "doctype", "evision_settings")
	doc = frappe.get_single("EVision Settings")
	doc.save(ignore_permissions=True)
