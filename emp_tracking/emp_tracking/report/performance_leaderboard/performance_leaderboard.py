# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Performance Leaderboard (Script Report)
#
# Ranks people and teams by points earned on completed jobs whose RFS Date falls in the chosen
# period. Jobs come from FTTH Work Order (ftth_tracker app), status "RFS Done".
# Point values come from Leaderboard Settings; the scoring rules, levels and badges live in
# emp_tracking/performance.py (pure python, unit-tested).
#
# Change log
#   2026-10-24  Created (New Project only).
#   2026-10-24  Also scores FTTH Work Orders ("Source" filter). The report was empty on
#               newsite.local because the FTTH data copied from OH.local lives in FTTH Work
#               Order, not New Project. Each "Rank" choice maps to the matching field of each
#               source (see SOURCES).
#   2026-10-24  "Maintenance Calls" source: ranks Supervisors, Splicers and Riders on their
#               monthly Staff Monthly Performance records (calls, SLA, MTTR, field time),
#               scored like the company's monthly sheets (see call_leaderboard).
#   2026-10-31  New Project source removed: New Project was merged into FTTH Work Order and the
#               doctype deleted (patches/remove_new_project.py).
# ---------------------------------------------------------------------------------------------

import frappe
from frappe import _
from frappe.utils import cint, flt, get_first_day, getdate, today

from emp_tracking.emp_tracking.doctype.staff_monthly_performance.staff_monthly_performance import get_call_points
from emp_tracking.performance import DEFAULT_POINTS, build_call_leaderboard, build_leaderboard

FTTH_WORK_ORDER = "FTTH Work Order"
MAINTENANCE_CALLS = "Maintenance Calls"
STAFF_PERFORMANCE = "Staff Monthly Performance"

# Rank choice -> column label
RANK_LABELS = {
	"Employee": _("Employee / Field Staff"),
	"Fiber Pulling Team": _("Fiber Team"),
	"Vendor": _("Vendor / IBD Team"),
	"Area": _("Area"),
	"Area Manager": _("Area Manager"),
	"GIS": _("GIS"),
}

# Per source: Rank choice -> (work field, Link doctype of the participant or None for Data).
# "members" means the people in the job's team tables / staff fields (see get_members).
SOURCES = {
	FTTH_WORK_ORDER: {
		"Employee": ("members", "Field Staff"),
		"Fiber Pulling Team": ("fiber_team", "Fiber Team"),
		"Vendor": ("ibd_team", "IBD Team"),
		"Area": ("area", None),
		"Area Manager": ("area_manager", None),
		"GIS": ("gis", "GIS Node"),
	},
}

# Everyone on an FTTH job; the same person in two roles is credited once
FTTH_STAFF_FIELDS = ("splicer", "assistant_splicer", "splicer_2", "rider_1", "rider_2")
FTTH_FIELDS = [
	"name", "rfs_date", "days_to_rfs", "hp", "eff_final_distance", "splicing_snaps_done", "rework_required_date",
	"fiber_team", "ibd_team", "area", "area_manager", "gis", *FTTH_STAFF_FIELDS,
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if filters.source == MAINTENANCE_CALLS:
		return call_leaderboard(filters)
	if filters.rank_by not in RANK_LABELS:
		filters.rank_by = "Vendor"
	points = get_points()
	sources = get_sources(filters)
	jobs = []
	for source in sources:
		jobs.extend(get_jobs(source, filters))
	rows = build_leaderboard(jobs, points)
	add_names(rows)
	for r in rows:
		r["badges"] = "  ".join(r["badges"])
	if cint(filters.top):
		rows = [r for r in rows if r["rank"] <= cint(filters.top)]
	return get_columns(filters, sources), rows, None, get_chart(rows), get_summary(rows)


def get_points():
	"""Point values from Leaderboard Settings, falling back to DEFAULT_POINTS for fields never saved.

	get_singles_dict only returns stored values, so a missing key means "use the default"
	while a stored 0 is respected (a manager may switch a rule off on purpose).
	"""
	stored = frappe.db.get_singles_dict("Leaderboard Settings")
	return {key: cint(stored[key]) if stored.get(key) not in (None, "") else default
		for key, default in DEFAULT_POINTS.items()}


def get_sources(filters):
	"""Sources chosen in the filter that exist on this site, that the user may read, and
	that have a field for the chosen Rank."""
	wanted = [filters.source] if filters.source in SOURCES else list(SOURCES)
	return [s for s in wanted
		if frappe.db.exists("DocType", s)  # ftth_tracker is optional
		and frappe.has_permission(s, "read")
		and filters.rank_by in SOURCES[s]]


def period(filters):
	# Default: 1 January of this year to today
	from_date = getdate(filters.from_date or get_first_day(today()).replace(month=1))
	return from_date, getdate(filters.to_date or today())


def get_jobs(source, filters):
	"""Completed jobs of one source in the period, as plain dicts for emp_tracking.performance."""
	from_date, to_date = period(filters)
	conditions = {"rfs_date": ["between", [from_date, to_date]], "status": "RFS Done"}
	fields = FTTH_FIELDS
	# Area is plain text on FTTH Work Order, so match it as text
	if filters.area:
		conditions["area"] = ["like", f"%{filters.area}%"]
	# get_list (not get_all) so the user's own permissions on the source doctype apply
	rows = frappe.get_list(source, filters=conditions, fields=fields, limit_page_length=0)

	field, link = SOURCES[source][filters.rank_by]
	members = get_members(source, rows) if field == "members" else {}
	jobs = []
	for p in rows:
		who = members.get(p.name, []) if field == "members" else ([p.get(field)] if p.get(field) else [])
		job = ftth_job(p)
		# Key = (Link doctype, name) so an Employee and a Field Staff with the same ID stay apart
		job["participants"] = [(link, w) for w in who]
		jobs.append(job)
	return jobs


def get_members(source, rows):
	"""{job name: sorted list of people on it} (the work order's splicer / rider fields)."""
	return {p.name: sorted({p.get(f) for f in FTTH_STAFF_FIELDS if p.get(f)}) for p in rows}


def ftth_job(p):
	return {
		"rfs_date": getdate(p.rfs_date),
		# eff_final_distance already falls back to survey / planning distance (emp_tracking.ftth.logic)
		"fiber_m": flt(p.eff_final_distance),
		"hp": cint(p.hp),
		# days_to_rfs is worked out by the work order itself; empty when a date is missing
		"days_to_rfs": cint(p.days_to_rfs) if p.days_to_rfs not in (None, "") and cint(p.days_to_rfs) >= 0 else None,
		# "Splicing Snaps A & B" ticks itself when both snaps are attached
		"proof_complete": bool(p.splicing_snaps_done),
		"rework": bool(p.rework_required_date),
	}


# Readable name per Link doctype: (doctype, name field)
NAME_FIELDS = {"Employee": "employee_name", "User": "full_name"}


def add_names(rows):
	"""Split the (doctype, name) key back out and add a readable name for Employees and Users."""
	wanted = {}
	for r in rows:
		r["participant_type"], r["participant"] = r["participant"]
		if r["participant_type"] in NAME_FIELDS:
			wanted.setdefault(r["participant_type"], set()).add(r["participant"])
	names = {}
	for doctype, ids in wanted.items():
		for name, full in frappe.get_all(doctype, filters={"name": ["in", list(ids)]},
				fields=["name", NAME_FIELDS[doctype]], as_list=True):
			names[(doctype, name)] = full
	for r in rows:
		r["participant_name"] = names.get((r["participant_type"], r["participant"])) or r["participant"]


def get_columns(filters, sources):
	links = {SOURCES[s][filters.rank_by][1] for s in sources}
	participant = {"fieldname": "participant", "label": RANK_LABELS[filters.rank_by], "width": 160}
	link = next(iter(links)) if len(links) == 1 else None
	# Several sources pointing at different doctypes (or plain text): show the name as text
	participant.update({"fieldtype": "Link", "options": link} if link else {"fieldtype": "Data"})
	columns = [{"fieldname": "rank", "label": _("Rank"), "fieldtype": "Data", "width": 80}, participant]
	if links & set(NAME_FIELDS):
		columns.append({"fieldname": "participant_name", "label": _("Name"), "fieldtype": "Data", "width": 160})
	return columns + [
		{"fieldname": "points", "label": _("Points"), "fieldtype": "Int", "width": 90},
		{"fieldname": "level", "label": _("Level"), "fieldtype": "Data", "width": 100},
		{"fieldname": "level_progress", "label": _("To Next Level"), "fieldtype": "Percent", "width": 150},
		{"fieldname": "badges", "label": _("Badges"), "fieldtype": "Data", "width": 260},
		{"fieldname": "rfs_done", "label": _("RFS Done"), "fieldtype": "Int", "width": 90},
		{"fieldname": "fiber_m", "label": _("Fiber Laid (m)"), "fieldtype": "Float", "precision": 0, "width": 120},
		{"fieldname": "home_pass", "label": _("Home Pass"), "fieldtype": "Int", "width": 100},
		{"fieldname": "on_time_pct", "label": _("On Time %"), "fieldtype": "Percent", "width": 100},
		{"fieldname": "avg_days", "label": _("Avg Days to RFS"), "fieldtype": "Float", "precision": 1, "width": 120},
		{"fieldname": "clean", "label": _("Clean Jobs"), "fieldtype": "Int", "width": 100},
		{"fieldname": "missing_proof", "label": _("Missing Snaps"), "fieldtype": "Int", "width": 110},
		{"fieldname": "rework", "label": _("Re-work"), "fieldtype": "Int", "width": 90},
		{"fieldname": "streak_weeks", "label": _("Best Streak (wks)"), "fieldtype": "Int", "width": 120},
		{"fieldname": "participant_type", "label": _("Type"), "fieldtype": "Data", "width": 110, "hidden": 1},
	]


def get_chart(rows):
	top = rows[:10]
	if not top:
		return None
	return {
		"data": {
			"labels": [str(r["participant_name"]) for r in top],
			"datasets": [{"name": _("Points"), "values": [r["points"] for r in top]}],
		},
		"type": "bar",
		"colors": ["#5e64ff"],
	}


def get_summary(rows):
	if not rows:
		return []
	leader = rows[0]
	return [
		{"label": _("Leader"), "value": f"{leader['medal']} {leader['participant_name']}", "datatype": "Data", "indicator": "Green"},
		{"label": _("Leader Points"), "value": leader["points"], "datatype": "Int", "indicator": "Blue"},
		{"label": _("Players"), "value": len(rows), "datatype": "Int", "indicator": "Grey"},
		{"label": _("Badges Earned"), "value": sum(len(r["badges"].split("  ")) for r in rows if r["badges"]),
			"datatype": "Int", "indicator": "Orange"},
	]


# ---------------------------------------------------------------------------------------------
# Maintenance Calls source (added 2026-10-24)
# ---------------------------------------------------------------------------------------------

def call_leaderboard(filters):
	"""Rank people on their Staff Monthly Performance months in the period.

	A month counts when its 1st day falls between the 1st of the From month and the To date.
	Supervisor and Splicer scores use different weights, so pick a Designation to compare
	like with like (blank = everyone).
	"""
	if not frappe.has_permission(STAFF_PERFORMANCE, "read"):
		return call_columns(), [], _("You cannot read Staff Monthly Performance."), None, []
	from_date, to_date = period(filters)
	conditions = {"month": ["between", [get_first_day(from_date), to_date]]}
	if filters.designation:
		conditions["designation"] = filters.designation
	months = frappe.get_list(STAFF_PERFORMANCE, filters=conditions, limit_page_length=0, fields=[
		"employee", "employee_name", "designation", "main_calls", "assistant_calls", "in_sla", "out_sla",
		"total_leaves", "working_days", "avg_mttr", "avg_field_time", "avg_working_time"])
	for m in months:
		# Same (doctype, name) key as the job sources; a person not linked to an Employee keeps the name
		m["participant"] = ("Employee", m.employee) if m.employee else (None, m.employee_name)
	rows = build_call_leaderboard(months, get_call_points())
	add_names(rows)
	for r in rows:
		r["badges"] = "  ".join(r["badges"])
	if cint(filters.top):
		rows = [r for r in rows if r["rank"] <= cint(filters.top)]
	message = None if rows else _("No Staff Monthly Performance records in this period. The sheet data covers April 2025 to March 2026.")
	return call_columns(), rows, message, get_chart(rows), get_summary(rows)


def call_columns():
	return [
		{"fieldname": "rank", "label": _("Rank"), "fieldtype": "Data", "width": 80},
		{"fieldname": "participant", "label": _("Employee"), "fieldtype": "Data", "width": 130},
		{"fieldname": "participant_name", "label": _("Name"), "fieldtype": "Data", "width": 170},
		{"fieldname": "designation", "label": _("Designation"), "fieldtype": "Data", "width": 100},
		{"fieldname": "points", "label": _("Points"), "fieldtype": "Float", "precision": 2, "width": 90},
		{"fieldname": "level", "label": _("Level"), "fieldtype": "Data", "width": 100},
		{"fieldname": "level_progress", "label": _("To Next Level"), "fieldtype": "Percent", "width": 150},
		{"fieldname": "badges", "label": _("Badges"), "fieldtype": "Data", "width": 280},
		{"fieldname": "main_calls", "label": _("Calls"), "fieldtype": "Int", "width": 80},
		{"fieldname": "assistant_calls", "label": _("Assistant Calls"), "fieldtype": "Int", "width": 110},
		{"fieldname": "in_sla", "label": _("In SLA"), "fieldtype": "Int", "width": 80},
		{"fieldname": "out_sla", "label": _("Out of SLA"), "fieldtype": "Int", "width": 90},
		{"fieldname": "sla_pct", "label": _("SLA %"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "avg_mttr", "label": _("Avg MTTR"), "fieldtype": "Duration", "width": 110},
		{"fieldname": "avg_field_time", "label": _("Avg Field Time / Day"), "fieldtype": "Duration", "width": 140},
		{"fieldname": "avg_working_time", "label": _("Avg Working Hours / Day"), "fieldtype": "Duration", "width": 150},
		{"fieldname": "leaves", "label": _("Leaves"), "fieldtype": "Int", "width": 80},
		{"fieldname": "working_days", "label": _("Working Days"), "fieldtype": "Int", "width": 100},
		{"fieldname": "months", "label": _("Months"), "fieldtype": "Int", "width": 80},
	]
