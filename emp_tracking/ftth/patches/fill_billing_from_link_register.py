# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt
#
# One-time patch (2026-10-29): fill the new Billing tab (HOTO No / Date, AT and signature status,
# billing year, section name) on existing FTTH Work Orders from their Link Register's HOTO rows.
# Written straight to the database: no notifications, "modified" unchanged, and only empty fields.

import frappe

from emp_tracking.ftth.logic import hoto_values

BILLING_FIELDS = ("hoto_no", "hoto_date", "at_status", "hoto_signature_status", "billing_year",
				  "billing_section_name", "is_billed")


# Date: 2026-10-29
def execute():
	"""Copy each linked Link Register's latest HOTO details onto its work orders."""
	frappe.reload_doc("ftth_tracker", "doctype", "ftth_work_order")
	hotos = {}
	for h in frappe.get_all("FTTH Link HOTO", filters={"parenttype": "FTTH Link"},
							fields=["parent", "hoto_no", "hoto_date", "year", "section_name"]):
		hotos.setdefault(h.parent, []).append(h)
	billed = dict(frappe.get_all("FTTH Link", fields=["name", "is_billed"], as_list=True))
	for wo in frappe.get_all("FTTH Work Order", filters={"ftth_link": ["is", "set"]},
							 fields=["name", "ftth_link", *BILLING_FIELDS]):
		values = {k: v for k, v in hoto_values(hotos.get(wo.ftth_link)).items() if not wo.get(k)}
		if billed.get(wo.ftth_link) and not wo.is_billed:
			values["is_billed"] = 1
		if values:
			frappe.db.set_value("FTTH Work Order", wo.name, values, update_modified=False)
