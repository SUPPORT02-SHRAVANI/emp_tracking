# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Employee Performance dashboard (Desk page /app/employee-performance): data
#
# How this file works
#   The page only draws; everything is counted here.
#   get_calls_dashboard: Supervisors / Splicers / Riders ranked on their Staff Monthly
#     Performance months (calls, SLA, MTTR, field time), scored with the Leaderboard Settings
#     weights (emp_tracking.performance.build_call_leaderboard). Also returns the month-by-month
#     trend, the field / home / office time split and, when one person is picked, that
#     person's months.
#   get_jobs_dashboard: the job-based ranking of the Performance Leaderboard report (FTTH Work
#     Orders) for one Rank choice, reusing the report's own execute().
#   Complaint calls (2026-10-27): the real complaints in Complaint Information where the person
#     is Splicer, 2nd Splicer, Rider or 2nd Rider, received in the period (optionally one Area).
#     The board gets calls per area for everyone; one person gets every complaint with its
#     received / assigned-to-team / restored times, time to assign, MTTR and SLA.
#
# Change log
#   2026-10-26  Created.
#   2026-10-27  Complaint calls by area and the person's complaint history (Area filter).
#   2026-10-27  RFO Type sent with each complaint (cause chart in the person's profile).
#   2026-10-31  area_calls(): each person's calls per area split by role (Splicer, 2nd Splicer,
#               Rider, 2nd Rider) for the "Who Attended Where" card.
#   2026-10-31  get_jobs_dashboard: "New Project" source removed (merged into FTTH Work Order).
# ---------------------------------------------------------------------------------------------

import frappe
from frappe import _
from frappe.utils import get_first_day, getdate, today

from emp_tracking.emp_tracking.doctype.staff_monthly_performance.staff_monthly_performance import get_call_points
from emp_tracking.performance import build_call_leaderboard, score_calls

STAFF_PERFORMANCE = "Staff Monthly Performance"
MONTH_FIELDS = [
	"employee", "employee_name", "designation", "month", "main_calls", "assistant_calls", "in_sla", "out_sla",
	"total_leaves", "working_days", "avg_mttr", "avg_field_time", "avg_home_time", "avg_office_time",
	"avg_working_time",
]

COMPLAINT = "Complaint Information"
# A complaint names up to two splicers and two riders; the person attended it in any of these roles.
COMPLAINT_ROLES = {"splicer": "Splicer", "second_splicer": "2nd Splicer", "rider": "Rider", "second_rider": "2nd Rider"}
COMPLAINT_FIELDS = [
	"name", "area", "linkid", "site", "society_name", "operatorcustomer", "complaint_type",
	"complaint_date_and_time", "call_assigned_on", "evision_closed_on", "delay_in_assigning",
	"evision_mttr", "evision_sla", "workflow_state", "link_status", "rfo_type", *COMPLAINT_ROLES,
]
NO_AREA = "No Area"


# Date: 2026-10-26
@frappe.whitelist()
def get_calls_dashboard(designation=None, from_date=None, to_date=None, employee=None, area=None):
	"""Everything the Maintenance Calls view draws.

	2026-10-27: area (optional) narrows the complaint-based parts: calls by area and the
	person's complaint history. The monthly figures have no area, so they are not filtered.
	"""
	frappe.has_permission(STAFF_PERFORMANCE, "read", throw=True)
	from_date, to_date = default_period(from_date, to_date)
	conditions = {"month": ["between", [get_first_day(from_date), to_date]]}
	if designation:
		conditions["designation"] = designation
	months = frappe.get_list(STAFF_PERFORMANCE, filters=conditions, fields=MONTH_FIELDS,
		order_by="month asc", limit_page_length=0)
	points = get_call_points()
	for m in months:
		m["participant"] = m.employee or m.employee_name
		m["score"] = score_calls(m, points)

	board = build_call_leaderboard(months, points)
	names = {m["participant"]: m.employee_name for m in months}
	for r in board:
		r["name"] = names.get(r["participant"]) or r["participant"]

	# Complaints in the same period: of the picked person in any role, otherwise of everyone in
	# the role(s) matching the designation, also people with no monthly figures yet
	complaints = complaint_calls(from_date, to_date, area, employee=employee,
		roles=None if employee else designation_roles(designation))

	result = {
		"from_date": str(from_date),
		"to_date": str(to_date),
		"board": board,
		"kpis": kpis(months, board),
		"trend": trend(months),
		"time_split": time_split(months),
		"person": person(months, employee, board) if employee else None,
		"can_see_complaints": complaints is not None,
		"area_calls": area_calls(complaints or [], board),
	}
	if employee and result["person"] is not None:
		result["person"]["complaints"] = complaints or []
		if not result["person"]["row"]:
			result["person"]["name"] = frappe.db.get_value("Employee", employee, "employee_name") or employee
	return result


# Date: 2026-10-27
def designation_roles(designation):
	"""Complaint fields that count for a designation: Splicers and Riders their own two, others all four."""
	if designation == "Splicer":
		return ["splicer", "second_splicer"]
	if designation == "Rider":
		return ["rider", "second_rider"]
	return list(COMPLAINT_ROLES)


# Date: 2026-10-27
def complaint_calls(from_date, to_date, area=None, employee=None, roles=None):
	"""Complaints received in the period, newest first.

	With `employee`: those where that Employee is Splicer, 2nd Splicer, Rider or 2nd Rider.
	Otherwise: those with anyone in one of the `roles` fields. Each row gets `people`: the
	[employee, role] pairs that count on it, so one complaint attended by two people counts once
	for each of them. Returns None when the user may not read Complaint Information (the page
	then hides these parts); get_list also applies the user's own permissions on complaints.
	"""
	if not frappe.has_permission(COMPLAINT, "read"):
		return None
	roles = roles or list(COMPLAINT_ROLES)
	# Dates on a Datetime field: Frappe's "between" runs from 00:00 of the first to the end of the last day
	filters = {"complaint_date_and_time": ["between", [from_date, to_date]]}
	if area:
		filters["area"] = area
	who = ["=", employee] if employee else ["is", "set"]
	rows = frappe.get_list(COMPLAINT, filters=filters, or_filters={field: who for field in roles},
		fields=COMPLAINT_FIELDS, order_by="complaint_date_and_time desc", limit_page_length=0)
	for row in rows:
		row["people"] = [[row[field], COMPLAINT_ROLES[field]] for field in roles
			if row[field] and (not employee or row[field] == employee)]
		row["area"] = row.area or NO_AREA
	return rows


# Date: 2026-10-27
def area_calls(complaints, board):
	"""Calls per area: overall (each complaint once) and per person (most calls first).

	Names come from the board, else from Employee (people with complaints but no monthly figures).
	2026-10-31: each person also gets "roles": [{role, calls, areas}] with their calls per area
	as Splicer, 2nd Splicer, Rider and 2nd Rider.
	"""
	names = {r["participant"]: r["name"] for r in board}
	missing = {emp for c in complaints for emp, _role in c.people} - set(names)
	if missing:
		names.update(dict(frappe.get_all("Employee", filters={"name": ["in", list(missing)]},
			fields=["name", "employee_name"], as_list=True)))
	overall, per_person = {}, {}
	for c in complaints:
		overall[c.area] = overall.get(c.area, 0) + 1
		for emp in {emp for emp, _role in c.people}:
			p = per_person.setdefault(emp, {"participant": emp, "name": names.get(emp, emp), "calls": 0,
				"restored": 0, "in_sla": 0, "areas": {}})
			p["calls"] += 1
			p["restored"] += 1 if c.evision_closed_on else 0
			p["in_sla"] += 1 if c.evision_sla == "In" else 0
			p["areas"][c.area] = p["areas"].get(c.area, 0) + 1
		# 2026-10-31: the same calls split by the role the person had on the complaint
		# (Splicer / 2nd Splicer / Rider / 2nd Rider), so the card shows one area row per role
		for emp, role in c.people:
			r = per_person[emp].setdefault("by_role", {}).setdefault(role, {"role": role, "calls": 0, "areas": {}})
			r["calls"] += 1
			r["areas"][c.area] = r["areas"].get(c.area, 0) + 1
	people = sorted(per_person.values(), key=lambda p: (-p["calls"], str(p["name"])))
	role_order = list(COMPLAINT_ROLES.values())
	for p in people:
		p["areas"] = sorted(p["areas"].items(), key=lambda a: (-a[1], a[0]))
		# Roles in the fixed order Splicer, 2nd Splicer, Rider, 2nd Rider; areas most calls first
		p["roles"] = sorted(p.pop("by_role", {}).values(), key=lambda r: role_order.index(r["role"]))
		for r in p["roles"]:
			r["areas"] = sorted(r["areas"].items(), key=lambda a: (-a[1], a[0]))
	return {
		"areas": sorted(overall.items(), key=lambda a: (-a[1], a[0])),
		"people": people,
	}


# Date: 2026-10-26
def default_period(from_date, to_date):
	"""Default: from the earliest month on record (the sheet data starts April 2025) to today."""
	if not from_date:
		first = frappe.get_all(STAFF_PERFORMANCE, fields=["month"], order_by="month asc", limit=1)
		from_date = first[0].month if first else get_first_day(today())
	return getdate(from_date), getdate(to_date or today())


# Date: 2026-10-26
def kpis(months, board):
	closed_in = sum(m.in_sla or 0 for m in months)
	closed_out = sum(m.out_sla or 0 for m in months)
	calls = sum((m.main_calls or 0) + (m.assistant_calls or 0) for m in months)
	mttr = [(m.avg_mttr, m.main_calls or 1) for m in months if m.avg_mttr]
	field = [m.avg_field_time for m in months if m.avg_field_time is not None]
	return {
		"people": len(board),
		"calls": calls,
		"sla_pct": round(closed_in * 100 / (closed_in + closed_out)) if closed_in + closed_out else 0,
		"avg_mttr": round(sum(a * w for a, w in mttr) / sum(w for _, w in mttr)) if mttr else 0,
		"avg_field_time": round(sum(field) / len(field)) if field else 0,
		"leaves": sum(m.total_leaves or 0 for m in months),
		"points": round(sum(r["points"] for r in board), 2),
	}


# Date: 2026-10-26
def trend(months):
	"""Per calendar month: calls, In / Out SLA, SLA % and total score, oldest first."""
	by_month = {}
	for m in months:
		t = by_month.setdefault(str(m.month), {"calls": 0, "in_sla": 0, "out_sla": 0, "score": 0.0})
		t["calls"] += (m.main_calls or 0) + (m.assistant_calls or 0)
		t["in_sla"] += m.in_sla or 0
		t["out_sla"] += m.out_sla or 0
		t["score"] += m.score
	rows = []
	for month in sorted(by_month):
		t = by_month[month]
		closed = t["in_sla"] + t["out_sla"]
		rows.append({"month": month, **t, "score": round(t["score"], 2),
			"sla_pct": round(t["in_sla"] * 100 / closed) if closed else 0})
	return rows


# Date: 2026-10-26
def time_split(months):
	"""Average daily hours on field / home / office location over the chosen months."""
	keys = ("avg_field_time", "avg_home_time", "avg_office_time")
	known = [m for m in months if any(m.get(k) for k in keys)]
	if not known:
		return {"field": 0, "home": 0, "office": 0}
	avg = lambda k: round(sum(m.get(k) or 0 for m in known) / len(known) / 3600, 2)  # noqa: E731
	return {"field": avg("avg_field_time"), "home": avg("avg_home_time"), "office": avg("avg_office_time")}


# Date: 2026-10-26
def person(months, employee, board):
	"""One person's row on the board plus their months, for the drill-down card."""
	mine = [m for m in months if m["participant"] == employee]
	row = next((r for r in board if r["participant"] == employee), None)
	if not mine or not row:
		return {"name": employee, "months": [], "row": None}
	return {
		"name": row["name"],
		"row": row,
		"months": [{
			"month": str(m.month), "score": m.score, "calls": m.main_calls or 0, "assistant_calls": m.assistant_calls or 0,
			"in_sla": m.in_sla or 0, "out_sla": m.out_sla or 0, "leaves": m.total_leaves or 0,
			"field_hours": round((m.avg_field_time or 0) / 3600, 2), "mttr_hours": round((m.avg_mttr or 0) / 3600, 2),
		} for m in mine],
	}


# Date: 2026-10-26
@frappe.whitelist()
def get_jobs_dashboard(rank_by="Vendor", source=None, from_date=None, to_date=None):
	"""Job-based ranking (FTTH Work Orders) from the Performance Leaderboard report."""
	from emp_tracking.emp_tracking.report.performance_leaderboard.performance_leaderboard import execute

	if source not in (None, "", "FTTH Work Order"):
		frappe.throw(_("Unknown source"))
	_cols, rows, _msg, _chart, _summary = execute({"rank_by": rank_by, "source": source,
		"from_date": from_date, "to_date": to_date})
	for r in rows:
		r["name"] = r.get("participant_name") or r.get("participant")
	totals = {
		"players": len(rows),
		"rfs_done": sum(r.get("rfs_done") or 0 for r in rows),
		"fiber_m": round(sum(r.get("fiber_m") or 0 for r in rows)),
		"home_pass": sum(r.get("home_pass") or 0 for r in rows),
	}
	return {"board": rows, "totals": totals}
