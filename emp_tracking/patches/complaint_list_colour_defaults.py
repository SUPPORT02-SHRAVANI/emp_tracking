# ---------------------------------------------------------------------------------------------
# Patch: Complaint List Colours gets its default colours (2026-11-28, user: the main site's
# colours table was empty - the earlier complaint_list_colours patch, which also set complaint
# team areas, was not deployed). Only rows that are missing are added; rows already there keep
# their colour. Safe to run again.
# ---------------------------------------------------------------------------------------------

import frappe


def execute():
	frappe.reload_doc("emp_tracking", "doctype", "complaint_list_colour")
	frappe.reload_doc("emp_tracking", "doctype", "complaint_list_colours")
	from emp_tracking.emp_tracking.doctype.complaint_list_colours.complaint_list_colours import set_defaults

	print("Complaint list colours added:", set_defaults())
	frappe.db.commit()
