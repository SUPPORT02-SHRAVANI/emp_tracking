# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# NOC Pending Summary (Script Report)
#
# How this file works
#   The NOC workbook's PENDING SUMMARY tab, and with "Team wise" ticked its TEAM WISE PENDING
#   SUMMARY tab: per day (per team) new SRs, opening carry forward, available, team SRs closed,
#   closing pending, closed In / Out of SLA. The numbers come from emp_tracking/noc_reports.py
#   (pending_summary), shared with the NOC Dashboard. The chart shows the daily totals.
#   Team wise is a tree: one bold row per day with the day's totals, its teams under it
#   (collapsed at first, see the .js), instead of 6 flat rows per day.
#
# Change log
#   2026-11-26  Created.
#   2026-11-26  Readable look (user: "doesn't look good"): short column names, team-wise tree,
#               chart shows every few days instead of truncated labels; colours in the .js
#               (evision.noc_formatter).
#   2026-11-26  Chart: day numbers as labels plus the ISO dates ("dates"), so the .js can shade
#               every other month (user's request).
#   2026-11-26  A period with no complaints shows a message (empty_message) instead of an empty
#               chart and rows of dashes; "Closed within 4 h" shows "–" when nothing was closed.
# ---------------------------------------------------------------------------------------------

from frappe import _

from emp_tracking.noc_reports import empty_message, nothing_happened, pending_summary

FIGURES = ("new", "opening", "available", "closed", "closing", "in_sla", "out_sla")


# Date: 2026-11-26
def execute(filters=None):
	filters = filters or {}
	by_team = bool(int(filters.get("team_wise") or 0))
	rows = pending_summary(filters, by_team=by_team)
	if nothing_happened(rows):
		return columns(by_team, _("SRs")), [], empty_message(filters)
	return columns(by_team, _("SRs")), as_tree(rows) if by_team else rows, None, chart(rows), summary(rows)


# Date: 2026-11-26
# Also used by NOC Unique Cut Summary with unit "Cuts". Team wise: the first column holds the
# day on group rows and the team on the rows under it.
# 2026-11-26: who_closed adds "Closed by" (splicer with count), used by the cut team summaries.
def columns(by_team, unit, who_closed=False):
	if by_team:
		cols = [{"fieldname": "label", "label": _("Day / team"), "fieldtype": "Data", "width": 200}]
	else:
		cols = [{"fieldname": "date", "label": _("Day"), "fieldtype": "Date", "width": 200}]
	for fieldname, label, width in (
		("new", _("{0} received").format(unit), 140),
		("opening", _("Opening"), 130),
		("available", _("Available"), 130),
		("closed", _("{0} closed").format(unit), 140),
		("closing", _("Pending"), 130),
		("in_sla", _("In SLA"), 130),
		("out_sla", _("Out of SLA"), 130),
	):
		cols.append({"fieldname": fieldname, "label": label, "fieldtype": "Int", "width": width})
	if who_closed:
		cols.append({"fieldname": "who_closed", "label": _("Closed by"), "fieldtype": "Data", "width": 320})
	return cols


# Date: 2026-11-26
def as_tree(rows):
	"""Per-team rows -> a bold day row with the totals (indent 0), then its teams (indent 1)."""
	out, day = [], None
	for r in rows:
		if r.date != day:
			day = r.date
			group = {"label": day.strftime("%a %d %b %Y"), "date": day, "indent": 0, "is_group": 1}
			group.update({k: 0 for k in FIGURES})
			out.append(group)
		for k in FIGURES:
			group[k] += r[k]
		out.append({"label": r.team, "date": r.date, "team": r.team, "indent": 1, **{k: r[k] for k in FIGURES},
			"who_closed": (r.get("who_closed") or "").title()})
	return out


# Date: 2026-11-26
def daily_totals(rows):
	"""Team-wise rows added up per day (rows already per day pass through)."""
	days = {}
	for r in rows:
		d = days.setdefault(r.date, {"new": 0, "closed": 0, "closing": 0, "in_sla": 0, "out_sla": 0})
		for k in d:
			d[k] += r[k]
	return days


# Date: 2026-11-26
def chart(rows):
	days = daily_totals(rows)
	return {
		# ISO dates of the labels: the .js shades every other month behind them (evision.month_bands)
		"dates": [str(d) for d in days],
		"data": {
			# day numbers (the chart shows every n-th one, see axisOptions); the month is named on
			# its background band
			"labels": [d.strftime("%d") for d in days],
			"datasets": [
				{"name": _("Received"), "values": [v["new"] for v in days.values()], "chartType": "bar"},
				{"name": _("Closed"), "values": [v["closed"] for v in days.values()], "chartType": "bar"},
				{"name": _("Pending"), "values": [v["closing"] for v in days.values()], "chartType": "line"},
			],
		},
		"type": "axis-mixed",
		"height": 260,
		"fieldtype": "Int",
		# blue = received, green = closed, amber = pending (the dashboard's colours)
		"colors": ["#3b82f6", "#22c55e", "#f59e0b"],
		# xIsSeries: Frappe Charts shows every n-th date instead of squeezing all into "...".
		# Sent as "ev_axis" (merged in by evision.noc_report_after_render): the report page
		# overwrites "axisOptions" with its own.
		"ev_axis": {"xIsSeries": 1, "xAxisMode": "tick"},
		"barOptions": {"spaceRatio": 0.35},
		"lineOptions": {"dotSize": 3},
	}


# Date: 2026-11-26
# Totals over the range (opening / closing are per day, so the summary shows the last day's pending).
def summary(rows):
	days = daily_totals(rows)
	if not days:
		return []
	received = sum(v["new"] for v in days.values())
	closed = sum(v["closed"] for v in days.values())
	in_sla = sum(v["in_sla"] for v in days.values())
	out_sla = sum(v["out_sla"] for v in days.values())
	pending = list(days.values())[-1]["closing"]
	# nothing closed: "–" in grey, not a red 0% that reads as "all late"
	# 2026-11-28: the hours come from EVision Settings (was a fixed "4 h")
	from emp_tracking.emp_tracking.doctype.evision_settings.evision_settings import setting, sla_pct

	label = _("Closed within {0} h").format(f"{setting('sla_hours'):g}")
	if in_sla + out_sla:
		pct = sla_pct(in_sla, out_sla)  # 2026-11-28: editable formula
		sla = {"label": label, "value": pct, "datatype": "Percent", "indicator": "Green" if pct >= 80 else "Red"}
	else:
		sla = {"label": label, "value": "–", "datatype": "Data", "indicator": "Gray"}
	return [
		{"label": _("Received"), "value": received, "datatype": "Int", "indicator": "Blue"},
		{"label": _("Closed"), "value": closed, "datatype": "Int", "indicator": "Green"},
		{"label": _("Pending at the end"), "value": pending, "datatype": "Int", "indicator": "Orange" if pending else "Green"},
		sla,
	]
