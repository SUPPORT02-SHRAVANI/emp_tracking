# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# NOC Performance (Script Report)
#
# How this file works
#   Performance month-wise or day-wise (user's request, 2026-11-26), optionally per team or
#   splicer, day calls against night calls. A call is a Day call when it was received
#   08:00-19:59, otherwise Night (noc_reports.shift_of). Built by noc_reports.performance.
#   Layout: one bold row per period (and team / splicer) with the totals, and under it a "Day
#   calls" and a "Night calls" row, each with calls, closed, still open, In / Out of SLA (4 h),
#   In-SLA % and average MTTR in hours.
#   Chart: with one period, day vs night split into In SLA / Out of SLA; with several, day and
#   night calls per period (first 40).
#
# Change log
#   2026-11-26  Created.
#   2026-11-26  Redesigned (user did not like the first version: 18 cut-off columns, one big
#               block as chart): day / night as rows under each period, 7 short columns,
#               chart that compares day and night, whole numbers on the axis.
# ---------------------------------------------------------------------------------------------

from frappe import _

from emp_tracking.noc_reports import empty_message, performance

FIGURES = ("received", "closed", "open", "in", "out", "pct", "mttr")
CHART_ROWS = 40


# Date: 2026-11-26
def execute(filters=None):
	filters = filters or {}
	keys, rows = performance(filters, filters.get("rows_by") or "Month")
	cols = [
		{"fieldname": "label", "label": _("Period / calls"), "fieldtype": "Data", "width": 300},
		{"fieldname": "received", "label": _("Calls"), "fieldtype": "Int", "width": 150},
		{"fieldname": "closed", "label": _("Closed"), "fieldtype": "Int", "width": 150},
		{"fieldname": "open", "label": _("Still open"), "fieldtype": "Int", "width": 150},
		{"fieldname": "in_sla", "label": _("In SLA"), "fieldtype": "Int", "width": 150},
		{"fieldname": "out_sla", "label": _("Out of SLA"), "fieldtype": "Int", "width": 150},
		{"fieldname": "sla_pct", "label": _("In SLA %"), "fieldtype": "Percent", "width": 150},
		{"fieldname": "mttr", "label": _("Avg MTTR (h)"), "fieldtype": "Float", "precision": 1, "width": 150},
	]
	if not rows:
		return cols, [], empty_message(filters)

	data = []
	for r in rows:
		data.append({"label": title(keys, r), "indent": 0, "is_group": 1, **part(r, "all")})
		data.append({"label": _("Day calls (08:00-20:00)"), "indent": 1, **part(r, "day")})
		data.append({"label": _("Night calls (20:00-08:00)"), "indent": 1, **part(r, "night")})
	return cols, data, None, chart(keys, rows), summary(rows)


# Date: 2026-11-26
def title(keys, r):
	parts = []
	for k in keys:
		v = r[k]
		if k == "month":
			v = v.strftime("%B %Y")
		elif k == "date":
			v = v.strftime("%a %d %b %Y")
		else:
			v = str(v).title()
		parts.append(v)
	return " - ".join(parts)


# Date: 2026-11-26
def part(r, prefix):
	return {
		"received": r[f"{prefix}_received"], "closed": r[f"{prefix}_closed"],
		"open": r[f"{prefix}_received"] - r[f"{prefix}_closed"], "in_sla": r[f"{prefix}_in"],
		"out_sla": r[f"{prefix}_out"], "sla_pct": r[f"{prefix}_pct"], "mttr": r[f"{prefix}_mttr"],
	}


# Date: 2026-11-26
def chart(keys, rows):
	# whole numbers on the y axis (merged in by evision.noc_report_after_render)
	common = {"height": 250, "fieldtype": "Int", "ev_axis": {"integer": 1}}
	if len(rows) == 1:
		r = rows[0]
		return {
			**common,
			"data": {
				"labels": [_("Day calls"), _("Night calls")],
				"datasets": [
					{"name": _("In SLA"), "values": [r.day_in, r.night_in]},
					{"name": _("Out of SLA"), "values": [r.day_out, r.night_out]},
					{"name": _("Still open"), "values": [r.day_received - r.day_closed, r.night_received - r.night_closed]},
				],
			},
			"type": "bar",
			"barOptions": {"stacked": 1, "spaceRatio": 0.5},
			"colors": ["#22c55e", "#ef4444", "#f59e0b"],
		}
	shown = rows[:CHART_ROWS]
	return {
		**common,
		"data": {
			"labels": [short(keys, r) for r in shown],
			"datasets": [
				{"name": _("Day calls"), "values": [r.day_received for r in shown]},
				{"name": _("Night calls"), "values": [r.night_received for r in shown]},
			],
		},
		"type": "bar",
		"barOptions": {"stacked": 1, "spaceRatio": 0.5},
		# day = amber (sun), night = indigo
		"colors": ["#f59e0b", "#6366f1"],
	}


# Date: 2026-11-26
def short(keys, r):
	parts = []
	for k in keys:
		v = r[k]
		parts.append(v.strftime("%b %y") if k == "month" else v.strftime("%d %b") if k == "date" else str(v).title())
	return " ".join(parts)


# Date: 2026-11-26
def summary(rows):
	def total(key):
		return sum(r[key] or 0 for r in rows)

	cards = []
	for prefix, name, colour in (("day", _("Day"), "Orange"), ("night", _("Night"), "Purple")):
		calls, closed = total(f"{prefix}_received"), total(f"{prefix}_closed")
		i, o = total(f"{prefix}_in"), total(f"{prefix}_out")
		cards.append({"label": _("{0} calls").format(name), "value": calls, "datatype": "Int", "indicator": colour})
		if i + o:
			pct = round(100.0 * i / (i + o), 1)
			cards.append({"label": _("{0} in SLA").format(name), "value": pct, "datatype": "Percent",
				"indicator": "Green" if pct >= 80 else "Red"})
		else:
			cards.append({"label": _("{0} in SLA").format(name), "value": "–", "datatype": "Data", "indicator": "Gray"})
		hours = [r[f"{prefix}_mttr"] * r[f"{prefix}_closed"] for r in rows if r[f"{prefix}_mttr"] is not None]
		mttr = round(sum(hours) / closed, 1) if closed and hours else None
		cards.append({"label": _("{0} avg MTTR").format(name), "value": f"{mttr} h" if mttr is not None else "–",
			"datatype": "Data", "indicator": "Blue"})
	return cards
