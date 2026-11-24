# ---------------------------------------------------------------------------------------------
# Patch: load the FY 2025-26 "Location and Calls Data" sheets into Staff Monthly Performance
#
# How this file works
#   Runs once during "bench migrate". staff_performance_fy2025_26.json holds the Summary
#   sheets of LOCATION_AND_CALLS_DATA_OF_SUPERVISOR_2025_2026 and LOCATION_DATA_AND_CALLS_DATA_
#   OF_SPLICER_AND_RIDER_2025_2026 (April 2025 to March 2026, 17 people, 204 person-months),
#   transcribed on 2026-10-24. Times are in seconds. A person-month that already exists is
#   skipped, so running it again adds nothing twice and keeps any later corrections.
#   Not loaded: Raj Kashinath Rathod (the sheet rows are mostly #REF! errors) and Dilip Pawar /
#   Mahesh Khedekar (only yearly totals in the marks sheet, no monthly rows).
#
# Change log
#   2026-10-24  Created.
# ---------------------------------------------------------------------------------------------

import json
import os

import frappe


# Date: 2026-10-24
def execute():
	frappe.reload_doc("emp_tracking", "doctype", "staff_monthly_performance")
	path = os.path.join(os.path.dirname(__file__), "staff_performance_fy2025_26.json")
	with open(path, encoding="utf-8") as f:
		rows = json.load(f)
	for row in rows:
		if frappe.db.exists("Staff Monthly Performance", {"employee_name": row["employee_name"], "month": row["month"]}):
			continue
		# Link the Employee only if that record exists on this site
		if row.get("employee") and not frappe.db.exists("Employee", row["employee"]):
			row["employee"] = None
		frappe.get_doc({"doctype": "Staff Monthly Performance", **row}).insert(ignore_permissions=True)
