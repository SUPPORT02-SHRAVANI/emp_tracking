# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Team Cable Summary (Script Report)
#
# How this file works
#   Adds up Team Monthly Cable entries per month (rows) and Maintenance Team (columns), with a
#   Total column and the report's total row: the same layout as the "Fiber Maintenance &
#   Project Data" pivot (Sum of Total cable). Project / Maintenance filter: blank = both.
#   The chart stacks the teams per month.
#
# Change log
#   2026-10-27  Created.
# ---------------------------------------------------------------------------------------------

import frappe
from frappe import _
from frappe.utils import getdate


# Date: 2026-10-27
def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = {}
	if filters.work_type:
		conditions["work_type"] = filters.work_type
	if filters.team:
		conditions["team"] = filters.team
	if filters.from_date and filters.to_date:
		conditions["date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.from_date:
		conditions["date"] = [">=", filters.from_date]
	elif filters.to_date:
		conditions["date"] = ["<=", filters.to_date]

	# get_list applies the user's permissions on Team Monthly Cable
	sums = frappe.get_list("Team Monthly Cable", filters=conditions,
		fields=["month", "team", {"SUM": "total_cable", "as": "cable"}] if frappe_v16() else
			["month", "team", "sum(total_cable) as cable"],
		group_by="month, team", order_by="month asc", limit_page_length=0)

	teams = sorted({s.team for s in sums})
	keys = {team: frappe.scrub(team) for team in teams}
	by_month = {}
	for s in sums:
		row = by_month.setdefault(s.month, {"month": f"{getdate(s.month):%b %Y}", "total": 0})
		row[keys[s.team]] = (row.get(keys[s.team]) or 0) + s.cable
		row["total"] += s.cable
	data = [by_month[m] for m in sorted(by_month)]

	columns = [{"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 110}]
	columns += [{"fieldname": keys[t], "label": t, "fieldtype": "Float", "precision": 0, "width": 120} for t in teams]
	columns.append({"fieldname": "total", "label": _("Total (m)"), "fieldtype": "Float", "precision": 0, "width": 130})

	chart = {
		"data": {
			"labels": [r["month"] for r in data],
			"datasets": [{"name": t, "values": [r.get(keys[t]) or 0 for r in data]} for t in teams],
		},
		"type": "bar",
		"barOptions": {"stacked": 1},
	} if data else None

	total = sum(r["total"] for r in data)
	summary = [{"label": _("Total Cable"), "value": total, "datatype": "Float", "indicator": "Blue"}] if data else []
	return columns, data, None, chart, summary


# Date: 2026-10-27
def frappe_v16():
	"""Frappe 16 wants aggregate fields as dicts; older versions take the SQL text."""
	return int(frappe.__version__.split(".")[0]) >= 16
