# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Stores the Maintenance Calls weights in Leaderboard Settings.
# The call fields were added to the settings after they were first saved, so the form showed
# 0.000 for them while the scoring used CALL_POINTS (performance.py). Saving the form as it was
# would have stored those zeros and wiped every call score. This writes the defaults (the
# FY 2025-26 sheet formula: splicer call x 1, assistant call x 0.5, In SLA x 0.25, Out of SLA
# x -0.25; supervisor In / Out SLA 0.5) only into fields that have no value yet, so a weight
# someone already set is kept. Safe to run again.
#
# Change log
#   2026-10-27  Created.
# ---------------------------------------------------------------------------------------------

import frappe

from emp_tracking.performance import CALL_POINTS


def execute():
	if not frappe.db.exists("DocType", "Leaderboard Settings"):
		return
	stored = frappe.db.get_singles_dict("Leaderboard Settings")
	for field, value in CALL_POINTS.items():
		if stored.get(field) in (None, ""):
			frappe.db.set_single_value("Leaderboard Settings", field, value)
