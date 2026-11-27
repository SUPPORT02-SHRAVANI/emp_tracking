# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# NOC Cut Team Summary (Script Report)
#
# How this file works
#   The "normal" cut team summary (user's request, 2026-11-26): per day and team, every SR counted
#   (repeat SRs on one fibre cut each count), next to NOC Unique Cut Summary which counts each cut
#   once. Columns: received, opening, available, closed, pending, In / Out of SLA and who closed
#   them (splicer with count). Built by noc_reports.pending_summary(by_team=True); the columns,
#   tree, chart and summary are NOC Pending Summary's.
#
# Change log
#   2026-11-26  Created.
# ---------------------------------------------------------------------------------------------

from frappe import _

from emp_tracking.emp_tracking.report.noc_pending_summary.noc_pending_summary import as_tree, chart, columns, summary
from emp_tracking.noc_reports import empty_message, nothing_happened, pending_summary


# Date: 2026-11-26
def execute(filters=None):
	filters = filters or {}
	rows = pending_summary(filters, by_team=True)
	cols = columns(True, _("SRs"), who_closed=True)
	if nothing_happened(rows):
		return cols, [], empty_message(filters)
	return cols, as_tree(rows), None, chart(rows), summary(rows)
