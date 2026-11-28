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
#   2026-11-28  Dashboard on top: summary tiles and a chart of cuts per team (In / Out / Open).
# ---------------------------------------------------------------------------------------------

from frappe import _

from emp_tracking.emp_tracking.doctype.evision_settings.evision_settings import sla_pct

from emp_tracking.noc_reports import cut_master, empty_message


# Date: 2026-11-26
def execute(filters=None):
	filters = filters or {}
	cuts = cut_master(filters)
	all_cuts = list(cuts)  # 2026-11-28: the dashboard counts every cut, before the Cut SLA filter
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
	if not all_cuts:
		return columns, rows, message
	return columns, rows, message, chart(all_cuts), summary(all_cuts)


# Date: 2026-11-28
def summary(cuts):
	"""Dashboard tiles (user: "for all summary reports make dashboard")."""
	closed = [c for c in cuts if c.closed]
	inside = sum(1 for c in closed if c.sla == "IN")
	return [
		{"label": _("Cuts"), "value": len(cuts), "datatype": "Int", "indicator": "Blue"},
		{"label": _("SRs on them"), "value": sum(c.sr_count for c in cuts), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Closed"), "value": len(closed), "datatype": "Int", "indicator": "Green"},
		{"label": _("Still open"), "value": len(cuts) - len(closed), "datatype": "Int", "indicator": "Orange"},
		{"label": _("In SLA"), "value": f"{sla_pct(inside, len(closed) - inside, 0):g} %" if closed else "–", "datatype": "Data",
			"indicator": "Green"},
		{"label": _("Out of SLA"), "value": len(closed) - inside, "datatype": "Int", "indicator": "Red"},
	]


# Date: 2026-11-28
def chart(cuts):
	"""Cuts per owner team: In SLA, Out of SLA, still open."""
	teams = {}
	for c in cuts:
		t = teams.setdefault(c.team.title(), [0, 0, 0])
		t[0 if c.closed and c.sla == "IN" else 1 if c.closed else 2] += 1
	return {
		"data": {"labels": list(teams), "datasets": [
			{"name": _("In SLA"), "values": [v[0] for v in teams.values()]},
			{"name": _("Out of SLA"), "values": [v[1] for v in teams.values()]},
			{"name": _("Open"), "values": [v[2] for v in teams.values()]}]},
		"type": "bar", "height": 220, "fieldtype": "Int", "ev_axis": {"integer": 1}, "barOptions": {"stacked": 1, "spaceRatio": 0.5},
		"colors": ["#22c55e", "#ef4444", "#f59e0b"],
	}
