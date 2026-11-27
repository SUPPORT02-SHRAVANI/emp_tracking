# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Patch: fill Complaint Information.unique_cut for complaints saved before the field existed
#
# How this file works
#   The NOC sheet import (noc_complaint_import.py, 2026-10-27) kept the sheet's UNIQUE CUT only
#   as a "Unique cut: <number>" line in complaint_details. That number is copied into the new
#   unique_cut field; complaints without the line get their Complaint Code, and those without a
#   code their own name (the same rule as ComplaintInformation.set_unique_cut()).
#   Only empty unique_cut values are written, so a cut typed by NOC is never overwritten and the
#   patch can run twice. Plain SQL: 28k rows, no controller logic needed.
#
# Change log
#   2026-11-26  Created (NOC reports count unique cuts, as in the NOC sheet).
# ---------------------------------------------------------------------------------------------

import frappe

MARK = "Unique cut: "


# Date: 2026-11-26
def execute():
	table = "`tabComplaint Information`"
	# 1. the number after "Unique cut: ", up to the end of that line (importer writes one item per line)
	frappe.db.sql(
		f"""update {table}
		set unique_cut = left(trim(substring_index(substring_index(complaint_details, %(mark)s, -1), '\n', 1)), 140)
		where ifnull(unique_cut, '') = '' and complaint_details like %(like)s""",
		{"mark": MARK, "like": f"%{MARK}%"},
	)
	# 2. otherwise the complaint is its own cut
	frappe.db.sql(f"update {table} set unique_cut = complaint_code where ifnull(unique_cut, '') = '' and ifnull(complaint_code, '') != ''")
	frappe.db.sql(f"update {table} set unique_cut = name where ifnull(unique_cut, '') = ''")
