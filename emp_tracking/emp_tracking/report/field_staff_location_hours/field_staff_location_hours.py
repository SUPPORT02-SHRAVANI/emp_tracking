# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Field Staff Location Hours (Script Report)
#
# How this file works
#   Hours per place per day for every field employee together (user's request, 2026-11-26):
#   at home (Employee Home Location), at the office (Shift Location), at complaint sites (field)
#   and elsewhere (other), from the phone's Location Pings, plus the complaints they were sent on.
#   Same rules as the NOC Dashboard's Employee sheet; built by noc_reports.location_hours.
#   (2026-11-27) People: the members of the Maintenance Teams (splicers, riders ...), plus anyone
#   else with Work Type = Field or with pings in the range; or only the employee / team / role
#   picked. Grouped Team -> person -> day. A person whose phone sent nothing is still listed,
#   marked "No location from app", so missing app data is visible instead of hidden.
#
# Change log
#   2026-11-26  Created.
#   2026-11-27  Redesign (user: "not good" — one person, one huge bar): team members always
#               listed, grouped by team, with role, "% in field" and "Last seen"; summary tiles;
#               the chart compares teams, shown only when there are two or more to compare.
# ---------------------------------------------------------------------------------------------

import frappe
from frappe import _
from frappe.utils import flt

from emp_tracking.emp_tracking.doctype.evision_settings.evision_settings import formula

from emp_tracking.noc_reports import location_hours, normalise

HOURS = ("field", "home", "office", "other", "total")
NO_TEAM = "Other field staff"


# Date: 2026-11-27
def people(filters):
	"""[(employee, team, role)]: team members (filtered by team / role), plus field staff and
	anyone with pings in the range who is in no team. One employee picked -> only them."""
	f = normalise(filters)
	members = frappe.db.sql("""select m.employee, m.parent team, m.role from `tabMaintenance Team Member` m
		join `tabMaintenance Team` t on t.name = m.parent
		where coalesce(m.active, 0) = 1 and coalesce(t.status, 'Active') = 'Active' order by m.parent, m.idx""", as_dict=True)
	out, seen = [], set()
	for m in members:
		if m.employee in seen:
			continue
		seen.add(m.employee)
		out.append((m.employee, m.team, m.role or ""))
	if not filters.get("team") and not filters.get("role"):
		pinged = frappe.get_all("Location Ping", filters={"timestamp": ["between", [f.from_date, f.to_date]]},
			pluck="employee", distinct=True, limit_page_length=0)
		field = frappe.get_all("Employee", filters={"status": "Active", "custom_work_type": "Field"}, pluck="name") \
			if frappe.get_meta("Employee").has_field("custom_work_type") else []
		out += [(e, NO_TEAM, "") for e in sorted(set(pinged) | set(field)) if e not in seen]
	if filters.get("employee"):
		out = [p for p in out if p[0] == filters["employee"]] or [(filters["employee"], NO_TEAM, "")]
	if filters.get("team"):
		out = [p for p in out if p[1] == filters["team"]]
	if filters.get("role"):
		out = [p for p in out if p[2] == filters["role"]]
	return out


# Date: 2026-11-26 (2026-11-27: team -> person -> day, people without app data listed)
def execute(filters=None):
	filters = frappe._dict(filters or {})
	cols = [
		{"fieldname": "label", "label": _("Team / person / day"), "fieldtype": "Data", "width": 240},
		{"fieldname": "role", "label": _("Role"), "fieldtype": "Data", "width": 85},
		{"fieldname": "field", "label": _("Field (h)"), "fieldtype": "Float", "precision": 1, "width": 85},
		{"fieldname": "home", "label": _("Home (h)"), "fieldtype": "Float", "precision": 1, "width": 85},
		{"fieldname": "office", "label": _("Office (h)"), "fieldtype": "Float", "precision": 1, "width": 85},
		{"fieldname": "other", "label": _("Other (h)"), "fieldtype": "Float", "precision": 1, "width": 85},
		{"fieldname": "total", "label": _("Tracked (h)"), "fieldtype": "Float", "precision": 1, "width": 95},
		{"fieldname": "field_pct", "label": _("In field"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "complaints", "label": _("Complaints"), "fieldtype": "Int", "width": 95},
		{"fieldname": "last_seen", "label": _("Last seen (app)"), "fieldtype": "Data", "width": 170},
	]
	who = people(filters)
	if not who:
		return cols, [], _("No team members or field staff for these filters.")

	rows = location_hours(filters, [p[0] for p in who])
	days_of = {}
	for r in rows:
		days_of.setdefault(r.employee, []).append(r)
	names = dict(frappe.get_all("Employee", filters={"name": ["in", [p[0] for p in who]]},
		fields=["name", "employee_name"], as_list=True))
	last = dict(frappe.db.sql("""select employee, max(timestamp) from `tabLocation Ping`
		where employee in %s group by employee""", (tuple(p[0] for p in who),)))

	def pct(g):
		# 2026-11-28: editable "In field %" formula
		if not g["total"]:
			return None
		v = formula("in_field_pct", field_hours=g["field"], home_hours=g["home"], office_hours=g["office"],
			other_hours=g["other"], tracked_hours=g["total"])
		return None if v is None else round(v, 0)

	data, teams, team_row = [], [], None
	for emp, team, role in who:
		if not team_row or team_row["label"] != team:
			team_row = {"label": team, "indent": 0, "is_group": 1, "complaints": 0, "people": 0, "on_app": 0,
				**{k: 0 for k in HOURS}}
			data.append(team_row)
			teams.append(team_row)
		days = days_of.get(emp, [])
		person = {"label": names.get(emp) or emp, "indent": 1, "role": _(role) if role else "",
			"complaints": sum(d.complaints for d in days), **{k: round(sum(d[k] for d in days), 2) for k in HOURS}}
		person["field_pct"] = pct(person)
		person["last_seen"] = frappe.utils.format_datetime(last[emp], "d MMM yyyy, HH:mm") if last.get(emp) \
			else _("No location from app")
		data.append(person)
		team_row["people"] += 1
		team_row["on_app"] += 1 if person["total"] else 0
		team_row["complaints"] += person["complaints"]
		for k in HOURS:
			team_row[k] = round(team_row[k] + person[k], 2)
		for d in days:
			data.append({"label": d.date.strftime("%a %d %b"), "indent": 2, "complaints": d.complaints,
				**{k: d[k] for k in HOURS}, "field_pct": pct(d)})
	for t in teams:
		t["field_pct"] = pct(t)
		t["role"] = _("{0} people").format(t["people"])
		t["last_seen"] = _("{0} of {1} sent location").format(t["on_app"], t["people"])

	total = {k: round(sum(t[k] for t in teams), 1) for k in HOURS}
	staff = sum(t["people"] for t in teams)
	on_app = sum(t["on_app"] for t in teams)
	summary = [
		{"label": _("Field staff"), "value": staff, "datatype": "Int", "indicator": "Blue"},
		{"label": _("Sent location"), "value": f"{on_app} / {staff}", "datatype": "Data",
			"indicator": "Green" if staff and on_app == staff else "Orange" if on_app else "Red"},
		# hours as text ("12.5 h"): a Float tile shows the site's 3-decimal format ("0.100")
		{"label": _("Field hours"), "value": f"{total['field']:g} h", "datatype": "Data", "indicator": "Green"},
		{"label": _("Home / office hours"), "value": f"{total['home']:g} h / {total['office']:g} h", "datatype": "Data",
			"indicator": "Gray"},
		{"label": _("Complaints"), "value": sum(t["complaints"] for t in teams), "datatype": "Int", "indicator": "Blue"},
	]

	# the chart compares teams; with fewer than two that have hours it would be one big bar
	with_hours = [t for t in teams if t["total"]]
	chart = None
	if len(with_hours) >= 2:
		chart = {
			"data": {"labels": [t["label"] for t in with_hours],
				"datasets": [{"name": _(k.title()), "values": [t[k] for t in with_hours]} for k in ("field", "home", "office", "other")]},
			"type": "bar", "height": 220, "barOptions": {"stacked": 1, "spaceRatio": 0.6},
			# field = green (at work), home = indigo, office = blue, other = grey
			"colors": ["#22c55e", "#6366f1", "#3b82f6", "#9ca3af"],
		}
	message = None
	if not on_app:
		message = _("None of these {0} people sent location from the phone app in this period, so hours are 0. "
			"Hours come from the app's location pings.").format(staff)
	return cols, data, message, chart, summary
