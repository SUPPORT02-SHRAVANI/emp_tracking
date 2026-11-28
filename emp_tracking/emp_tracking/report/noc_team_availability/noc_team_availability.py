# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# NOC Team Availability (Script Report)
#
# How this file works
#   Per day and team (user's request, 2026-11-26: "if Team 3 is available, how many splicers were
#   there that day and who was assigned"): the team's members and splicers (Maintenance Team >
#   Members), who of them was Present in Attendance, the SRs received, who was sent on them
#   (splicer / rider / 2nd, with counts) and present members who got no complaint.
#   Built by noc_reports.team_availability. Grouped by day (tree): a bold day row with the
#   totals, its teams under it.
#   Teams without a member list show "Members not set" and only who was sent.
#
# Change log
#   2026-11-26  Created.
#   2026-11-28  Dashboard: chart of members present and SRs per day for each team; more tiles.
# ---------------------------------------------------------------------------------------------

from frappe import _

from emp_tracking.noc_reports import empty_message, team_availability

COUNTS = ("members", "splicers", "present", "present_splicers", "received", "assigned")


# Date: 2026-11-26
def execute(filters=None):
	filters = filters or {}
	cols = [
		{"fieldname": "label", "label": _("Day / team"), "fieldtype": "Data", "width": 160},
		{"fieldname": "members", "label": _("Members"), "fieldtype": "Int", "width": 85},
		{"fieldname": "splicers", "label": _("Splicers"), "fieldtype": "Int", "width": 80},
		{"fieldname": "present", "label": _("Present"), "fieldtype": "Int", "width": 80},
		{"fieldname": "present_splicers", "label": _("Splicers present"), "fieldtype": "Int", "width": 115},
		{"fieldname": "received", "label": _("SRs received"), "fieldtype": "Int", "width": 105},
		{"fieldname": "assigned", "label": _("People sent"), "fieldtype": "Int", "width": 95},
		{"fieldname": "assigned_names", "label": _("Who was sent (calls)"), "fieldtype": "Data", "width": 300},
		{"fieldname": "present_names", "label": _("Present"), "fieldtype": "Data", "width": 260},
		{"fieldname": "idle_names", "label": _("Present, no call"), "fieldtype": "Data", "width": 200},
	]
	rows = team_availability(filters)
	if not rows:
		return cols, [], empty_message(filters)

	data, day, group = [], None, None
	for r in rows:
		if r.date != day:
			day = r.date
			group = {"label": day.strftime("%a %d %b %Y"), "indent": 0, "is_group": 1, **{k: 0 for k in COUNTS}}
			data.append(group)
		for k in COUNTS:
			group[k] += r[k]
		data.append({
			"label": r.team.title(), "indent": 1, **{k: r[k] for k in COUNTS},
			"assigned_names": r.assigned_names.title(),
			"present_names": r.present_names if not r.no_members else _("Members not set"),
			"idle_names": r.idle_names,
		})
	return cols, data, None, chart(rows), summary(rows)


# Date: 2026-11-28
def chart(rows):
	"""Per team, on average per day: members present and SRs received (user: "make dashboard")."""
	teams = {}
	for r in rows:
		t = teams.setdefault(r.team.title(), {"days": set(), "present": 0, "received": 0})
		t["days"].add(r.date)
		t["present"] += r.present
		t["received"] += r.received
	avg = lambda t, k: round(t[k] / len(t["days"]), 1) if t["days"] else 0
	return {
		"data": {"labels": list(teams), "datasets": [
			{"name": _("Present per day"), "values": [avg(t, "present") for t in teams.values()]},
			{"name": _("SRs per day"), "values": [avg(t, "received") for t in teams.values()]}]},
		"type": "bar", "height": 220, "barOptions": {"spaceRatio": 0.5}, "colors": ["#3b82f6", "#f97316"],
	}


# Date: 2026-11-26 (2026-11-28: days, present per day, people sent added)
def summary(rows):
	set_up = {r.team for r in rows if not r.no_members}
	missing = sorted({r.team for r in rows if r.no_members})
	days = len({r.date for r in rows}) or 1
	cards = [
		{"label": _("Teams with members"), "value": len(set_up), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Days"), "value": len({r.date for r in rows}), "datatype": "Int", "indicator": "Blue"},
		{"label": _("SRs received"), "value": sum(r.received for r in rows), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Present per day"), "value": f"{sum(r.present for r in rows) / days:.1f}", "datatype": "Data",
			"indicator": "Green"},
		{"label": _("People sent"), "value": sum(r.assigned for r in rows), "datatype": "Int", "indicator": "Orange"},
	]
	if missing:
		cards.append({"label": _("Teams without a member list"), "value": len(missing), "datatype": "Int", "indicator": "Orange"})
	return cards
