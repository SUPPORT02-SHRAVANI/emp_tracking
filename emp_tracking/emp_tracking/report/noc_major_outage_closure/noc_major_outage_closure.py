# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# NOC Major Outage Closure (Script Report)
#
# How this file works
#   The NOC workbook's MAJOR OUTAGE CLOSURE tab: for every month and team, the 2 days with the
#   most new cuts (rank 1 = busiest), that day's cut figures, who closed the cuts (splicer with
#   count), the splicers and 2nd splicers on that day's SRs, and how many different splicers
#   worked. Built by emp_tracking/noc_reports.py (major_outage). The workbook's PRESENT TEAM
#   COUNT / AVAILABLE SPLICER were typed by hand; "Splicers working" is taken from the complaints.
#
# Change log
#   2026-11-26  Created.
#   2026-11-26  Readable look: rows grouped under a bold month row (tree), short column names,
#               names in title case.
#   2026-11-26  Narrower columns so the table fits the screen; no 2nd splicer shown blank.
#   2026-11-28  Dashboard on top: summary tiles and a chart of new / closed cuts per team.
# ---------------------------------------------------------------------------------------------

from frappe import _

from emp_tracking.emp_tracking.doctype.evision_settings.evision_settings import sla_pct

from emp_tracking.noc_reports import empty_message, major_outage


# Date: 2026-11-26
def execute(filters=None):
	data, month = [], None
	for r in major_outage(filters or {}):
		if r.month != month:
			month = r.month
			data.append({"label": r.month.strftime("%B %Y"), "indent": 0, "is_group": 1})
		data.append({
			"label": r.team.title(), "indent": 1, "rank": r.rank, "date": r.date, "new": r.new, "opening": r.opening,
			"total": r.total, "closed": r.closed, "closing": r.closing, "in_sla": r.in_sla, "out_sla": r.out_sla,
			"who_closed": r.who_closed.title(), "splicers": r.splicers.title(),
			# "NA" (no 2nd splicer) shown blank, not "Na"
			"splicers2": "" if r.splicers2 == "NA" else r.splicers2.title(),
			"working": r.working,
		})
	columns = [
		{"fieldname": "label", "label": _("Month / team"), "fieldtype": "Data", "width": 130},
		# 2026-11-26: widths add up to about 1,500 px, so the table fits a laptop / desktop screen
		# without scrolling sideways (user's request: "make it full screen")
		{"fieldname": "rank", "label": _("Rank"), "fieldtype": "Int", "width": 60},
		{"fieldname": "date", "label": _("Busiest day"), "fieldtype": "Date", "width": 105},
		{"fieldname": "new", "label": _("New cuts"), "fieldtype": "Int", "width": 85},
		{"fieldname": "opening", "label": _("Opening"), "fieldtype": "Int", "width": 85},
		{"fieldname": "total", "label": _("Total"), "fieldtype": "Int", "width": 65},
		{"fieldname": "closed", "label": _("Closed"), "fieldtype": "Int", "width": 75},
		{"fieldname": "closing", "label": _("Pending"), "fieldtype": "Int", "width": 80},
		{"fieldname": "in_sla", "label": _("In SLA"), "fieldtype": "Int", "width": 70},
		{"fieldname": "out_sla", "label": _("Out of SLA"), "fieldtype": "Int", "width": 90},
		{"fieldname": "who_closed", "label": _("Closed by"), "fieldtype": "Data", "width": 220},
		{"fieldname": "splicers", "label": _("Splicers on new SRs"), "fieldtype": "Data", "width": 190},
		{"fieldname": "splicers2", "label": _("2nd splicers"), "fieldtype": "Data", "width": 120},
		{"fieldname": "working", "label": _("Working"), "fieldtype": "Int", "width": 80},
	]
	# 2026-11-26: empty period -> message instead of an empty table
	if not data:
		return columns, data, empty_message(filters or {})
	rows = [d for d in data if not d.get("is_group")]
	return columns, data, None, chart(rows), summary(rows)


# Date: 2026-11-28
def summary(rows):
	"""Dashboard tiles (user: "for all summary reports make dashboard")."""
	closed = sum(r["in_sla"] + r["out_sla"] for r in rows)
	busiest = max(rows, key=lambda r: r["new"])
	return [
		{"label": _("Months"), "value": len({r["date"].strftime("%Y-%m") for r in rows}), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Outage days"), "value": len(rows), "datatype": "Int", "indicator": "Blue"},
		{"label": _("New cuts on them"), "value": sum(r["new"] for r in rows), "datatype": "Int", "indicator": "Orange"},
		{"label": _("Closed"), "value": sum(r["closed"] for r in rows), "datatype": "Int", "indicator": "Green"},
		{"label": _("In SLA"), "value": f"{sla_pct(sum(r['in_sla'] for r in rows), sum(r['out_sla'] for r in rows), 0):g} %" if closed else "–",
			"datatype": "Data", "indicator": "Green"},
		{"label": _("Busiest day"), "value": f"{busiest['date'].strftime('%d %b %Y')} · {busiest['label']} · {busiest['new']}",
			"datatype": "Data", "indicator": "Red"},
	]


# Date: 2026-11-28
def chart(rows):
	"""New cuts and closed cuts on the outage days, per team."""
	teams = {}
	for r in rows:
		t = teams.setdefault(r["label"], [0, 0])
		t[0] += r["new"]
		t[1] += r["closed"]
	return {
		"data": {"labels": list(teams), "datasets": [
			{"name": _("New cuts"), "values": [v[0] for v in teams.values()]},
			{"name": _("Closed"), "values": [v[1] for v in teams.values()]}]},
		"type": "bar", "height": 220, "fieldtype": "Int", "ev_axis": {"integer": 1}, "barOptions": {"spaceRatio": 0.5},
		"colors": ["#f97316", "#22c55e"],
	}
