# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt
#
# One-time patch (2026-10-29): fill the new Stage field on every existing FTTH Work Order.
# 2026-10-29: run again after the AT & HOTO / Billing / Closed stages were added.
# Written straight to the database, so no stage notifications go out and "modified" stays as it
# was. Later saves keep the stage up to date through logic.derive().

import frappe

from emp_tracking.ftth.logic import compute_stage

FIELDS = ("name", "issue_type", "rfs_date", "work_completed_date", "b_end_issue", "approval_date",
		  "survey_distance", "fiber_team", "fiber_id", "reading_a_snap", "reading_b_snap", "splicer",
		  "splicing_snaps_done", "splicing_snap_a", "splicing_snap_b", "at_status", "hoto_date", "payment_status")


# Date: 2026-10-29
def execute():
	"""Work out the stage of each work order from its saved values and store it."""
	frappe.reload_doc("ftth_tracker", "doctype", "ftth_work_order")
	for row in frappe.get_all("FTTH Work Order", fields=list(FIELDS)):
		frappe.db.set_value("FTTH Work Order", row.name, "stage", compute_stage(row), update_modified=False)
