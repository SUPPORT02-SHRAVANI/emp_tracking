# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# NOC Unique Cut Summary (Script Report)
#
# How this file works
#   The NOC workbook's UNIQUE CUT TEAM SUMMARY tab: the same carry-forward table as NOC Pending
#   Summary, counted in fibre cuts (Complaint Information.unique_cut) instead of SRs. A cut belongs
#   to the team of its earliest SR and is closed when its last SR is closed (noc_reports.cut_summary).
#   Team wise is on by default, like the workbook tab. Columns, tree, chart and summary are the
#   Pending Summary's, so the two reports read the same way.
#
# Change log
#   2026-11-26  Created.
#   2026-11-26  Team wise shown as a tree (day totals, teams under each day), like Pending Summary.
#   2026-11-26  Empty period: a message instead of an empty chart (empty_message).
#   2026-11-26  "Closed by" column (team wise): the splicer who closed each cut, with counts.
# ---------------------------------------------------------------------------------------------

from frappe import _

from emp_tracking.emp_tracking.report.noc_pending_summary.noc_pending_summary import as_tree, chart, columns, summary
from emp_tracking.noc_reports import cut_summary, empty_message, nothing_happened


# Date: 2026-11-26
def execute(filters=None):
	filters = filters or {}
	by_team = bool(int(filters.get("team_wise") if filters.get("team_wise") not in (None, "") else 1))
	rows = cut_summary(filters, by_team=by_team)
	if nothing_happened(rows):
		return columns(by_team, _("Cuts"), who_closed=by_team), [], empty_message(filters)
	return columns(by_team, _("Cuts"), who_closed=by_team), as_tree(rows) if by_team else rows, None, chart(rows), summary(rows)
