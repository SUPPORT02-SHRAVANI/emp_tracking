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
#   Employees: the one picked, else everyone with Work Type = Field or with pings in the range.
#   Grouped by employee (tree): a bold row with the employee's totals, the days under it.
#
# Change log
#   2026-11-26  Created.
# ---------------------------------------------------------------------------------------------

from frappe import _

from emp_tracking.noc_reports import location_hours

HOURS = ("field", "home", "office", "other", "total")


# Date: 2026-11-26
def execute(filters=None):
	filters = filters or {}
	cols = [
		{"fieldname": "label", "label": _("Employee / day"), "fieldtype": "Data", "width": 210},
		{"fieldname": "field", "label": _("Field (h)"), "fieldtype": "Float", "precision": 1, "width": 95},
		{"fieldname": "home", "label": _("Home (h)"), "fieldtype": "Float", "precision": 1, "width": 95},
		{"fieldname": "office", "label": _("Office (h)"), "fieldtype": "Float", "precision": 1, "width": 95},
		{"fieldname": "other", "label": _("Other (h)"), "fieldtype": "Float", "precision": 1, "width": 95},
		{"fieldname": "total", "label": _("Tracked (h)"), "fieldtype": "Float", "precision": 1, "width": 105},
		{"fieldname": "complaints", "label": _("Complaints"), "fieldtype": "Int", "width": 100},
	]
	rows = location_hours(filters)
	if not rows:
		return cols, [], _("No location pings or complaints for field staff in this period. Hours come from the phone app's location pings.")

	data, emp, group = [], None, None
	for r in rows:
		if r.employee != emp:
			emp = r.employee
			group = {"label": r.employee_name, "indent": 0, "is_group": 1, "complaints": 0, **{k: 0 for k in HOURS}}
			data.append(group)
		for k in HOURS:
			group[k] = round(group[k] + r[k], 2)
		group["complaints"] += r.complaints
		data.append({"label": r.date.strftime("%a %d %b %Y"), "indent": 1, "complaints": r.complaints, **{k: r[k] for k in HOURS}})

	chart = {
		"data": {
			"labels": [g["label"] for g in data if g.get("is_group")][:30],
			"datasets": [{"name": _(k.title()), "values": [g[k] for g in data if g.get("is_group")][:30]}
				for k in ("field", "home", "office", "other")],
		},
		"type": "bar",
		"height": 240,
		"barOptions": {"stacked": 1, "spaceRatio": 0.45},
		# field = green (at work), home = indigo, office = blue, other = grey
		"colors": ["#22c55e", "#6366f1", "#3b82f6", "#9ca3af"],
	}
	return cols, data, None, chart
