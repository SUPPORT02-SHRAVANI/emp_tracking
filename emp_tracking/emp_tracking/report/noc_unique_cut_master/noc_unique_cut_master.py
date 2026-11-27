# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# NOC Unique Cut Master (Script Report)
#
# How this file works
#   The NOC workbook's UNIQUE CUT MASTER tab: one row per fibre cut (Complaint Information.
#   unique_cut) first received in the date range, with its owner team (earliest SR), SR count,
#   closed date (last SR closed, only when all are closed) and SLA (OUT if any SR is OUT).
#   Built by emp_tracking/noc_reports.py (cut_master). "Cut SLA" filters to IN / OUT / open cuts.
#
# Change log
#   2026-11-26  Created.
#   2026-11-26  Readable look: shorter column names, names in title case, SLA chip (.js formatter).
# ---------------------------------------------------------------------------------------------

from frappe import _

from emp_tracking.noc_reports import cut_master, empty_message


# Date: 2026-11-26
def execute(filters=None):
	filters = filters or {}
	cuts = cut_master(filters)
	# 2026-11-26: empty period -> message (columns built below are kept for the empty table)
	message = None if cuts else empty_message(filters)
	wanted = filters.get("cut_sla")
	if wanted == "Open":
		cuts = [c for c in cuts if not c.closed]
	elif wanted in ("IN", "OUT"):
		cuts = [c for c in cuts if c.sla == wanted]
	rows = [{
		"cut": c.cut, "first_received": c.first_received, "team": c.team.title(), "sr_count": c.sr_count,
		"closed": c.closed, "sla": c.sla or _("Open"), "closer": c.closer.title(),
		# the first complaint opens from the row; the rest are listed by name
		"complaint": c.complaints[0], "others": ", ".join(c.complaints[1:]),
	} for c in cuts]
	columns = [
		{"fieldname": "cut", "label": _("Unique cut"), "fieldtype": "Data", "width": 115},
		{"fieldname": "first_received", "label": _("First SR received"), "fieldtype": "Datetime", "width": 180},
		{"fieldname": "team", "label": _("Team"), "fieldtype": "Data", "width": 95},
		{"fieldname": "sr_count", "label": _("SRs"), "fieldtype": "Int", "width": 65},
		{"fieldname": "closed", "label": _("Cut closed"), "fieldtype": "Datetime", "width": 180},
		{"fieldname": "sla", "label": _("SLA"), "fieldtype": "Data", "width": 75},
		{"fieldname": "closer", "label": _("Closed by"), "fieldtype": "Data", "width": 170},
		{"fieldname": "complaint", "label": _("Complaint"), "fieldtype": "Link", "options": "Complaint Information", "width": 150},
		{"fieldname": "others", "label": _("Other complaints on the cut"), "fieldtype": "Data", "width": 220},
	]
	return columns, rows, message
