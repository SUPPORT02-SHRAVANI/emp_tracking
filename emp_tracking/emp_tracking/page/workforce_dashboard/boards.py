# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""Turns a metrics.Dataset into the nine dashboards and their drill-down lists.

Every dashboard returns the same shape, which workforce_dashboard.js draws generically:
	{"kpis": [kpi...], "sections": [table | chart | bars | map | stats | timeline ...]}
Each KPI / bar / stat may carry a `drill` key; `drill()` turns that key into a list.
Rows carry `_doctype` / `_name` so a click opens the record's detail panel.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate

from emp_tracking.emp_tracking.page.workforce_dashboard.metrics import (
	AGE_BUCKETS,
	LONG_PENDING_DAYS,
	PRESENT,
	Dataset,
	age_bucket,
	pct,
	summarize,
)

# ---- column sets -----------------------------------------------------------

DAY_COLS = [
	("employee_name", "Employee", "text"),
	("date", "Date", "date"),
	("status", "Status", "status"),
	("mode", "Mode", "text"),
	("in_time", "In", "time"),
	("out_time", "Out", "time"),
	("working_hours", "Hours", "hours"),
	("field_hours", "Field", "hours"),
	("km", "KM", "km"),
]
LIVE_COLS = [
	("employee_name", "Employee", "text"),
	("designation", "Designation", "text"),
	("live", "Current Status", "status"),
	("in_time", "Checked In", "time"),
	("working_hours", "Hours Today", "hours"),
	("field_hours", "Field", "hours"),
	("km", "KM Today", "km"),
	("task", "Current Task / Site", "text"),
	("location_time", "Last Location", "ago"),
]
TASK_COLS = [
	("name", "Task", "text"),
	("subject", "Subject", "text"),
	("employee_name", "Employee", "text"),
	("category", "Type", "text"),
	("project_name", "Project", "text"),
	("custom_site", "Site", "text"),
	("priority", "Priority", "status"),
	("bucket", "Status", "status"),
	("due", "Due", "datetime"),
	("age_days", "Age (days)", "int"),
]
TASK_GROUP_COLS = [
	("label", "Name", "text"),
	("total", "Total", "int"),
	("completed", "Completed", "int"),
	("in_progress", "In Progress", "int"),
	("pending", "Pending", "int"),
	("delayed", "Delayed", "int"),
	("completion_pct", "Completion", "pct"),
]
CLAIM_COLS = [
	("name", "Claim", "text"),
	("employee_name", "Employee", "text"),
	("custom_claim_from", "From", "date"),
	("custom_claim_to", "To", "date"),
	("custom_claimed_km", "Claimed KM", "km"),
	("custom_gps_km", "GPS KM", "km"),
	("custom_eligible_km", "Eligible KM", "km"),
	("custom_km_source", "Source", "text"),
	("total_claimed_amount", "Amount", "currency"),
	("state", "Status", "status"),
]
CLAIM_GROUP_COLS = [
	("label", "Name", "text"),
	("claims", "Claims", "int"),
	("claimed_km", "Claimed KM", "km"),
	("gps_km", "GPS KM", "km"),
	("eligible_km", "Eligible KM", "km"),
	("amount", "Claimed", "currency"),
	("approved_amount", "Approved", "currency"),
	("pending", "Pending", "int"),
]
LEAVE_COLS = [
	("name", "Application", "text"),
	("employee_name", "Employee", "text"),
	("leave_type", "Leave Type", "text"),
	("from_date", "From", "date"),
	("to_date", "To", "date"),
	("total_leave_days", "Days", "float"),
	("status", "Status", "status"),
]
BALANCE_COLS = [
	("employee_name", "Employee", "text"),
	("leave_type", "Leave Type", "text"),
	("allocated", "Allocated", "float"),
	("taken", "Taken", "float"),
	("pending", "Pending", "float"),
	("balance", "Balance", "float"),
]
REG_COLS = [
	("name", "Request", "text"),
	("employee_name", "Employee", "text"),
	("from_date", "From", "date"),
	("to_date", "To", "date"),
	("reason", "Reason", "text"),
	("explanation", "Explanation", "text"),
	("state", "Status", "status"),
]
APPROVAL_COLS = [
	("request", "Request", "status"),
	("employee_name", "Employee", "text"),
	("detail", "Detail", "text"),
	("date", "For", "date"),
	("amount", "Amount", "currency"),
	("waiting_days", "Waiting (days)", "int"),
]
GPS_COLS = [
	("time", "Time", "datetime"),
	("employee_name", "Employee", "text"),
	("exception", "Exception", "status"),
	("detail", "Detail", "text"),
]
TRIP_COLS = [
	("name", "Trip", "text"),
	("employee_name", "Employee", "text"),
	("start_time", "Start", "datetime"),
	("end_time", "End", "datetime"),
	("hours", "Hours", "hours"),
	("total_distance_km", "KM", "km"),
	("sites", "Sites", "int"),
]
STOP_COLS = [
	("employee_name", "Employee", "text"),
	("title", "Site", "text"),
	("address", "Address", "text"),
	("start_time", "Arrived", "datetime"),
	("duration_minutes", "Minutes", "int"),
]
PERF_COLS = [
	("employee_name", "Employee", "text"),
	("team", "Team", "text"),
	("assigned", "Assigned", "int"),
	("completed", "Completed", "int"),
	("completion_pct", "Completion", "pct"),
	("on_time_pct", "On-time", "pct"),
	("working_hours", "Work Hrs", "hours"),
	("field_hours", "Field Hrs", "hours"),
	("office_hours", "Office Hrs", "hours"),
	("km", "Field KM", "km"),
	("attendance_pct", "Attendance", "pct"),
	("score", "Score", "score"),
]
GROUP_PERF_COLS = [("label", "Name", "text"), ("employees", "Employees", "int")] + PERF_COLS[2:]
ATT_EMP_COLS = [
	("employee_name", "Employee", "text"),
	("department", "Department", "text"),
	("expected_days", "Working Days", "int"),
	("present", "Present", "float"),
	("absent", "Absent", "int"),
	("leave", "Leave", "int"),
	("late", "Late", "int"),
	("missing_punch", "Missing Punch", "int"),
	("attendance_pct", "Attendance", "pct"),
	("avg_hours", "Avg Hrs/Day", "hours"),
]
EXC_COLS = [
	("severity", "Severity", "status"),
	("category_label", "Type", "text"),
	("title", "Item", "text"),
	("detail", "Detail", "text"),
	("employee_name", "Employee", "text"),
	("when", "When", "datetime"),
]

EXC_CATEGORIES = {
	"overdue": "Overdue Tasks",
	"sla": "SLA Breaches",
	"missing_attendance": "Missing Attendance",
	"long_pending": "Long Pending Tasks",
	"gps": "GPS Exceptions",
	"excess_km": "Excessive / Manual KM",
	"approvals": "Pending Approvals",
	"low_productivity": "Low Productivity",
}
SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}

# ---- building blocks -------------------------------------------------------


def kpi(label, value, fmt="int", hint=None, tone=None, drill=None):
	return {"label": label, "value": value, "fmt": fmt, "hint": hint, "tone": tone, "drill": drill}


def cols(spec):
	return [{"key": k, "label": label, "fmt": fmt} for k, label, fmt in spec]


def rows_for(spec, rows, extra=()):
	keys = [k for k, _l, _f in spec] + ["_doctype", "_name", "_drill", "employee", *extra]
	return [{k: r.get(k) for k in keys} for r in rows]


def table(title, spec, rows, drill=None, width="full", subtitle=None, empty=None, inline_actions=False, limit=None):
	shown = rows[:limit] if limit else rows
	return {
		"type": "table",
		"title": title,
		"subtitle": subtitle,
		"columns": cols(spec),
		"rows": rows_for(spec, shown),
		"total": len(rows),
		"drill": drill,
		"width": width,
		"empty": empty or _("Nothing to show for these filters"),
		"inline_actions": inline_actions,
	}


def chart(title, chart_type, labels, datasets, width="half", subtitle=None, stacked=False, colors=None):
	return {
		"type": "chart",
		"title": title,
		"subtitle": subtitle,
		"chart_type": chart_type,
		"labels": [str(x) for x in labels],
		"datasets": datasets,
		"width": width,
		"stacked": stacked,
		"colors": colors,
	}


def bars(title, items, fmt="int", width="half", subtitle=None):
	return {"type": "bars", "title": title, "subtitle": subtitle, "items": items, "fmt": fmt, "width": width}


def stats(title, items, width="third", drill=None):
	return {"type": "stats", "title": title, "items": items, "width": width, "drill": drill}


def tone(value, warn=0, bad=None):
	"""bad when value > bad (if given), warn when value > warn."""
	if bad is not None and value > bad:
		return "bad"
	return "warn" if value > warn else "ok"


def score_tone(score):
	if score is None:
		return None
	return "ok" if score >= 75 else ("warn" if score >= 60 else "bad")


def multi_day(ds):
	return ds.start != ds.end


def sum_of(rows, key):
	return round(sum(flt(r.get(key)) for r in rows), 2)


# ---- shared derivations ----------------------------------------------------


def live_rows(ds):
	out = []
	for emp, rec in ds.live.items():
		e = ds.employees.get(emp) or ds.for_today.employees.get(emp)
		t = rec.current_task
		loc = rec.location
		out.append(frappe._dict(
			rec,
			_doctype="Employee",
			_name=emp,
			designation=e.designation if e else None,
			task=f"{t.subject}" + (f" @ {t.custom_site}" if t.custom_site else "") if t else None,
			location_time=loc.timestamp if loc else None,
		))
	order = {"In Field": 0, "In Office": 1, "Checked Out": 2, "Not Checked In": 3, "Absent": 4, "On Leave": 5, "Holiday": 6}
	out.sort(key=lambda r: (order.get(r.live, 9), r.employee_name))
	return out


def map_points(ds):
	points = []
	for r in live_rows(ds):
		loc = r.get("location")
		if not loc:
			continue
		points.append({
			"employee": r.employee,
			"employee_name": r.employee_name,
			"lat": flt(loc.latitude),
			"lng": flt(loc.longitude),
			"time": loc.timestamp,
			"status": r.live,
			"task": r.task,
			"path": ds.movement(r.employee),
		})
	return points


def task_groups(tasks, key):
	groups = defaultdict(list)
	for t in tasks:
		groups[t.get(key) or "-"].append(t)
	out = []
	for label, members in sorted(groups.items()):
		completed = sum(1 for t in members if t.bucket == "Completed")
		out.append(frappe._dict(
			label=label,
			total=len(members),
			completed=completed,
			in_progress=sum(1 for t in members if t.bucket == "In Progress"),
			pending=sum(1 for t in members if t.bucket == "Pending"),
			delayed=sum(1 for t in members if t.delayed),
			completion_pct=pct(completed, len(members)),
			employee=members[0].employee if key == "employee_name" else None,
		))
	return out


def claim_groups(claims, key):
	groups = defaultdict(list)
	for c in claims:
		groups[c.get(key) or "-"].append(c)
	out = []
	for label, members in sorted(groups.items()):
		out.append(frappe._dict(
			label=label,
			claims=len(members),
			claimed_km=sum_of(members, "custom_claimed_km"),
			gps_km=sum_of(members, "custom_gps_km"),
			eligible_km=sum_of(members, "custom_eligible_km"),
			amount=sum_of(members, "total_claimed_amount"),
			approved_amount=sum_of([c for c in members if c.state == "Approved"], "total_sanctioned_amount"),
			pending=sum(1 for c in members if c.state == "Pending"),
			employee=members[0].employee if key == "employee_name" else None,
		))
	return out


def attendance_by_employee(ds):
	by_emp = defaultdict(list)
	for d in ds.days:
		by_emp[d.employee].append(d)
	out = []
	for emp in ds.ids:
		days = by_emp.get(emp, [])
		s = summarize(days, [], ds.today, ds.now)
		worked = [d for d in days if d.status in PRESENT]
		out.append(frappe._dict(
			s,
			_doctype="Employee",
			_name=emp,
			employee=emp,
			employee_name=ds.emp_name(emp),
			department=ds.employees[emp].department,
			avg_hours=round(sum(d.working_hours for d in worked) / len(worked), 2) if worked else 0,
		))
	return out


def day_rows(days):
	return [frappe._dict(d, _doctype="Attendance" if d.attendance else "Employee", _name=d.attendance or d.employee) for d in days]


def task_rows(tasks):
	return [frappe._dict(t, _doctype="Task", _name=t.name) for t in tasks]


def claim_rows(claims):
	return [frappe._dict(c, _doctype="Expense Claim", _name=c.name) for c in claims]


def leave_rows(apps):
	return [frappe._dict(a, _doctype="Leave Application", _name=a.name) for a in sorted(apps, key=lambda a: a.from_date, reverse=True)]


def reg_rows(regs):
	return [frappe._dict(r, _doctype="Attendance Request", _name=r.name) for r in regs]


def trip_rows(ds):
	return [frappe._dict(t, _doctype="Trip 2", _name=t.name, sites=len(ds.stops_by_trip.get(t.name, []))) for t in reversed(ds.trips)]


def stop_rows(ds):
	return [frappe._dict(s, _doctype="Trip Stop", _name=s.name) for s in reversed(ds.stops)]


def exception_rows(ds, category=None):
	rows = [frappe._dict(e, category_label=EXC_CATEGORIES[e.category]) for e in ds.exceptions if not category or e.category == category]
	rows.sort(key=lambda r: (SEVERITY_ORDER.get(r.severity, 9), str(r.when or "")))
	return rows


def all_claims(ds):
	"""Claims raised in the period plus anything still waiting, without duplicates."""
	seen = {c.name for c in ds.claims}
	return ds.claims + [c for c in ds.pending_claims if c.name not in seen]


# ---- dashboards ------------------------------------------------------------


def employee_board(ds):
	if not ds.ids:
		return {"kpis": [], "sections": [], "message": _("No employee record is linked to your user. Ask HR to set the User ID on your Employee record.")}

	emp = ds.ids[0]
	e = ds.employees[emp]
	now = ds.live.get(emp) or frappe._dict()
	today = ds.for_today
	perf = ds.performance[0]
	month = Dataset({**ds.filters, "period": "This Month"}, ds.user).performance[0]
	balances = [b for b in ds.leave_balances if b.employee == emp]
	claims = all_claims(ds)
	pending_claims = [c for c in claims if c.state == "Pending"]

	# Hours are not split: a field employee's working time is all field, an office employee's all office.
	if ds.work_type.get(emp) == "Field":
		hours = [kpi(_("Field Hours Today"), now.get("working_hours"), "hours", hint=_("Field employee · all working hours"), drill="field:trips")]
	else:
		hours = [kpi(_("Office Hours Today"), now.get("working_hours"), "hours", hint=_("Office employee · all working hours"), drill="att:all")]
	kpis = [
		kpi(_("Today's Status"), now.get("live"), "status", hint=_("In at {0}").format(frappe.format(now.in_time, "Time")) if now.get("in_time") else None, drill="att:all"),
		*hours,
		kpi(_("Field KM Today"), now.get("km"), "km", hint=_("{0} km this period").format(perf.km), drill="field:trips"),
		kpi(_("Tasks Assigned"), perf.assigned, drill="task:all"),
		kpi(_("Tasks Completed"), perf.completed, tone="ok", drill="task:completed"),
		kpi(_("Tasks Pending"), perf.pending + perf.in_progress, hint=_("{0} delayed").format(perf.delayed), tone=tone(perf.delayed), drill="task:open"),
		kpi(_("Leave Balance"), sum(b.balance for b in balances), "float", hint=", ".join(f"{b.leave_type}: {b.balance:g}" for b in balances) or _("No allocation"), drill="leave:balances"),
		kpi(_("Petrol Claims Pending"), len(pending_claims), hint=frappe.format(sum(flt(c.total_claimed_amount) for c in pending_claims), "Currency"), drill="claim:pending"),
	]

	timeline = []
	for log in today.checkins.get((emp, today.today), []):
		out = log.log_type == "OUT"
		timeline.append({"time": log.time, "label": _("Checked out") if out else _("Checked in"), "detail": log.custom_work_mode or "", "tone": "neutral" if out else "ok"})
	for t in today.trips_by_day.get((emp, today.today), []):
		timeline.append({"time": t.start_time, "label": _("Trip started"), "detail": t.vehicle or "", "tone": "info"})
		for s in today.stops_by_trip.get(t.name, []):
			timeline.append({"time": s.start_time, "label": _("Site visit: {0}").format(s.title or "-"), "detail": s.address or "", "tone": "info"})
		if t.end_time:
			timeline.append({"time": t.end_time, "label": _("Trip ended"), "detail": f"{flt(t.total_distance_km):g} km", "tone": "neutral"})
	timeline.sort(key=lambda x: x["time"])

	daily = ds.daily_trend() if multi_day(ds) else Dataset({**ds.filters, "period": "This Week"}, ds.user).daily_trend()
	day_map = {d.date: d for d in ds.days} if multi_day(ds) else {}
	labels = [frappe.format(dt, "Date") for dt, _b in daily]

	compare = []
	for label, key, fmt in (
		("Attendance", "attendance_pct", "pct"),
		("Task completion", "completion_pct", "pct"),
		("On-time completion", "on_time_pct", "pct"),
		("Working hours", "working_hours", "hours"),
		("Field hours", "field_hours", "hours"),
		("Office hours", "office_hours", "hours"),
		("Field KM", "km", "km"),
		("Score", "score", "score"),
	):
		compare.append({"metric": label, "today": (today.performance[0] if today.ids else {}).get(key), "month": month.get(key), "period": perf.get(key), "fmt": fmt})

	open_tasks = sorted(ds.tasks, key=lambda t: (not t.is_open, t.due or ds.now))
	return {
		"title": e.employee_name,
		"subtitle": " · ".join(x for x in (e.designation, e.department) if x),
		# Shown as a badge in the header, so the tiles fill whole rows.
		"score": {"value": perf.score, "month": month.score, "drill": "perf:all"},
		"kpis": kpis,
		"sections": [
			{"type": "timeline", "title": _("Today's Timeline"), "items": timeline, "width": "third"},
			table(_("My Tasks"), [c for c in TASK_COLS if c[0] not in ("employee_name",)], task_rows(open_tasks), drill="task:all", width="two-thirds", limit=8),
			{"type": "compare", "title": _("Daily & Monthly Performance"), "rows": compare, "columns": [_("Today"), _("This Month"), _("Selected Period")], "width": "half"},
			chart(_("Daily Working Hours"), "bar", labels, [
				{"name": _("Office"), "values": [round(b["hours"] - day_map[dt].field_hours, 2) if dt in day_map else round(b["hours"], 2) for dt, b in daily]},
				{"name": _("Field"), "values": [day_map[dt].field_hours if dt in day_map else 0 for dt, b in daily]},
			], stacked=True, subtitle=_("Office vs field, per day")),
			table(_("Leave Balance"), [c for c in BALANCE_COLS if c[0] != "employee_name"], balances, drill="leave:balances", width="half"),
			table(_("Petrol Claims"), [c for c in CLAIM_COLS if c[0] != "employee_name"], claim_rows(claims), drill="claim:all", width="half", limit=6),
		],
	}


def team_board(ds):
	live = live_rows(ds)
	count = defaultdict(int)
	for r in live:
		count[r.live] += 1
		if r.live in ("In Field", "In Office", "Checked Out"):
			count["present"] += 1
	field = sum(1 for r in live if r.mode == "Field")
	office = sum(1 for r in live if r.mode == "Office")
	tasks = ds.tasks
	done = sum(1 for t in tasks if t.bucket == "Completed")
	approvals = ds.approvals

	return {
		"kpis": [
			kpi(_("Team Size"), len(live), drill="live:all"),
			kpi(_("Present"), count["present"], tone="ok", hint=pct_hint(count["present"], len(live)), drill="live:present"),
			kpi(_("Absent / Not In"), count["Absent"] + count["Not Checked In"], tone=tone(count["Absent"] + count["Not Checked In"]), drill="live:absent"),
			kpi(_("On Leave"), count["On Leave"], drill="live:On Leave"),
			kpi(_("In Field"), field, drill="live:field"),
			kpi(_("In Office"), office, drill="live:office"),
			kpi(_("Team Completion"), pct(done, len(tasks)), "pct", hint=_("{0} of {1} tasks").format(done, len(tasks)), drill="task:completed"),
			kpi(_("Delayed Tasks"), sum(1 for t in tasks if t.delayed), tone=tone(sum(1 for t in tasks if t.delayed)), drill="task:delayed"),
			kpi(_("Pending Approvals"), len(approvals), tone=tone(len(approvals)), drill="approvals:all"),
		],
		"sections": [
			bars(_("Team Attendance Today"), [
				{"label": _("Present"), "value": count["present"], "drill": "live:present", "tone": "ok"},
				{"label": _("Absent / Not checked in"), "value": count["Absent"] + count["Not Checked In"], "drill": "live:absent", "tone": "bad"},
				{"label": _("On Leave"), "value": count["On Leave"], "drill": "live:On Leave", "tone": "warn"},
				{"label": _("Field"), "value": field, "drill": "live:field"},
				{"label": _("Office"), "value": office, "drill": "live:office"},
			], width="third"),
			table(_("Employee-wise Current Status"), LIVE_COLS, live, drill="live:all", width="two-thirds"),
			{"type": "map", "title": _("Field Employee Location & Movement"), "points": map_points(ds), "width": "half"},
			table(_("Tasks by Employee"), TASK_GROUP_COLS, task_groups(tasks, "employee_name"), drill="task:all", width="half"),
			table(_("Pending Approvals"), APPROVAL_COLS, approvals, drill="approvals:all", inline_actions=True,
				empty=_("No approvals waiting")),
			table(_("Employee Performance"), PERF_COLS, sorted(ds.performance, key=lambda r: -(r.score or 0)), drill="perf:all"),
		],
	}


def hr_board(ds):
	days = ds.days
	present = sum(1 for d in days if d.status in PRESENT)
	absent = sum(1 for d in days if d.status in ("Absent", "Not Checked In"))
	leave = sum(1 for d in days if d.status == "On Leave")
	late = sum(1 for d in days if d.late)
	missing_punch = sum(1 for d in days if d.missing_punch)
	expected = sum(1 for d in days if d.status not in ("Holiday", "On Leave"))
	regs = ds.regularizations
	pending_regs = [r for r in regs if r.docstatus == 0]
	pending_leaves = [a for a in ds.leave_apps if a.docstatus == 0 and a.status == "Open"]
	unit = _("employee-days") if multi_day(ds) else _("employees today")

	trend = ds.daily_trend()
	monthly = ds.monthly_attendance()
	period_leaves = [a for a in ds.leave_apps if getdate(a.from_date) <= ds.end and getdate(a.to_date) >= ds.start or a.status == "Open"]

	return {
		"kpis": [
			kpi(_("Attendance %"), pct(present, expected), "pct", hint=_("Present / working days, excl. leave"), tone=pct_tone(pct(present, expected)), drill="att:all"),
			kpi(_("Present"), present, hint=unit, tone="ok", drill="att:present"),
			kpi(_("Absent"), absent, hint=unit, tone=tone(absent), drill="att:absent"),
			kpi(_("On Leave"), leave, hint=unit, drill="att:leave"),
			kpi(_("Late Arrivals"), late, hint=_("After 09:45"), tone=tone(late), drill="att:late"),
			kpi(_("Missing Punch"), missing_punch, tone=tone(missing_punch), drill="att:missing_punch"),
			kpi(_("Regularizations Pending"), len(pending_regs), tone=tone(len(pending_regs)), drill="reg:pending"),
			kpi(_("Leave Requests Pending"), len(pending_leaves), tone=tone(len(pending_leaves)), drill="leave:open"),
		],
		"sections": [
			chart(_("Daily Attendance Trend"), "line", [frappe.format(dt, "Date") for dt, _b in trend], [
				{"name": _("Present"), "values": [b["present"] for _dt, b in trend]},
				{"name": _("Absent"), "values": [b["absent"] for _dt, b in trend]},
				{"name": _("Leave"), "values": [b["leave"] for _dt, b in trend]},
				{"name": _("Late"), "values": [b["late"] for _dt, b in trend]},
			], subtitle=_("Employees per day")),
			chart(_("Monthly Attendance %"), "bar", [m for m, _v in monthly], [
				{"name": _("Attendance %"), "values": [v or 0 for _m, v in monthly]},
			], subtitle=_("Last 6 months, marked attendance")),
			table(_("Employee-wise Attendance"), ATT_EMP_COLS, attendance_by_employee(ds), drill="att:all"),
			table(_("Leave Balances"), BALANCE_COLS, ds.leave_balances, drill="leave:balances", width="half"),
			table(_("Leave Status"), LEAVE_COLS, leave_rows(period_leaves), drill="leave:all", width="half", limit=10),
			table(_("Attendance Regularization"), REG_COLS, reg_rows(regs), drill="reg:all", width="half", inline_actions=True,
				empty=_("No regularization requests")),
			table(_("Late / Missing Punch"), DAY_COLS, day_rows([d for d in days if d.late or d.missing_punch]), drill="att:exceptions", width="half", limit=10),
		],
	}


def field_board(ds):
	live = live_rows(ds)
	in_field = [r for r in live if r.live == "In Field"]
	days = ds.days
	field_hours = sum_of(days, "field_hours")
	km = sum_of(days, "km")
	sites = len(ds.stops)
	gps = ds.gps_exceptions
	active = [t for t in ds.for_today.trips if not t.end_time]

	by_emp = defaultdict(lambda: frappe._dict(field_hours=0, km=0, sites=0))
	for d in days:
		b = by_emp[d.employee]
		b.field_hours += d.field_hours
		b.km += d.km
		b.sites += d.sites
	field_rows = []
	for r in live:
		b = by_emp[r.employee]
		if not (b.km or b.field_hours or r.live == "In Field"):
			continue
		loc = r.location
		field_rows.append(frappe._dict(
			r,
			latest=f"{flt(loc.latitude):.5f}, {flt(loc.longitude):.5f}" if loc else None,
			period_hours=round(b.field_hours, 2),
			period_km=round(b.km, 1),
			sites_visited=b.sites,
		))

	return {
		"kpis": [
			kpi(_("In Field Now"), len(in_field), drill="live:In Field"),
			kpi(_("Active Trips"), len(active), drill="field:trips"),
			kpi(_("Field Hours"), field_hours, "hours", drill="field:trips"),
			kpi(_("Distance Travelled"), km, "km", drill="field:trips"),
			kpi(_("Sites Visited"), sites, drill="field:sites"),
			kpi(_("GPS Exceptions"), len(gps), tone=tone(len(gps)), drill="gps:all"),
		],
		"sections": [
			{"type": "map", "title": _("Latest Location & Today's Movement"), "points": map_points(ds), "width": "full"},
			table(_("Field Employees"), [
				("employee_name", "Employee", "text"),
				("live", "Status", "status"),
				("latest", "Latest Location", "text"),
				("location_time", "Updated", "ago"),
				("task", "Assigned Task / Site", "text"),
				("period_hours", "Field Hours", "hours"),
				("period_km", "Distance", "km"),
				("sites_visited", "Sites", "int"),
			], field_rows, drill="live:field"),
			bars(_("Distance by Employee"), [
				{"label": r.employee_name, "value": r.period_km, "drill": f"field:trips:{r.employee}"} for r in sorted(field_rows, key=lambda r: -r.period_km)
			], fmt="km"),
			table(_("GPS / Movement Exceptions"), GPS_COLS, gps, drill="gps:all", width="half", limit=8, empty=_("No GPS exceptions")),
			table(_("Sites Visited"), STOP_COLS, stop_rows(ds), drill="field:sites", width="half", limit=8),
			table(_("Trips"), TRIP_COLS, trip_rows(ds), drill="field:trips", width="half", limit=8),
		],
	}


def tasks_board(ds):
	tasks = ds.tasks
	n = defaultdict(int)
	for t in tasks:
		n[t.bucket] += 1
	delayed = sum(1 for t in tasks if t.delayed)
	open_tasks = [t for t in tasks if t.is_open]
	completed = [t for t in tasks if t.bucket == "Completed"]
	ages = defaultdict(int)
	for t in open_tasks:
		ages[age_bucket(t.age_days)] += 1

	return {
		"kpis": [
			kpi(_("Total Tasks"), len(tasks), drill="task:all"),
			kpi(_("Completed"), n["Completed"], tone="ok", drill="task:completed"),
			kpi(_("In Progress"), n["In Progress"], drill="task:in_progress"),
			kpi(_("Pending"), n["Pending"], drill="task:pending"),
			kpi(_("Delayed"), delayed, tone=tone(delayed), drill="task:delayed"),
			kpi(_("On-time Completion"), pct(sum(1 for t in completed if t.on_time), len(completed)), "pct", drill="task:completed"),
			kpi(_("Avg Age (open)"), round(sum(t.age_days for t in open_tasks) / len(open_tasks), 1) if open_tasks else 0, "float",
				hint=_("days · {0} older than {1} days").format(sum(1 for t in open_tasks if t.long_pending), LONG_PENDING_DAYS), drill="task:open"),
		],
		"sections": [
			chart(_("Status"), "donut", [_("Completed"), _("In Progress"), _("Pending")],
				[{"name": _("Tasks"), "values": [n["Completed"], n["In Progress"], n["Pending"]]}], width="third"),
			bars(_("Task Ageing (open tasks)"), [
				{"label": label, "value": ages[label], "drill": f"task:age:{label}", "tone": "bad" if lo > LONG_PENDING_DAYS else None}
				for lo, _hi, label in AGE_BUCKETS
			], width="third"),
			table(_("Project / Maintenance"), TASK_GROUP_COLS, [dict(r, _drill=f"task:category:{r.label}") for r in task_groups(tasks, "category")], width="third"),
			table(_("Project-wise Status"), TASK_GROUP_COLS, [dict(r, _drill=f"task:project:{r.label}") for r in task_groups([t for t in tasks if t.project], "project_name")], width="half"),
			table(_("Employee-wise Status"), TASK_GROUP_COLS, [dict(r, _drill=f"task:employee:{r.employee}") for r in task_groups(tasks, "employee_name")], width="half"),
			table(_("Delayed Tasks"), TASK_COLS, task_rows([t for t in tasks if t.delayed]), drill="task:delayed", empty=_("No delayed tasks")),
		],
	}


def claims_board(ds):
	claims = all_claims(ds)
	period = ds.claims
	state = defaultdict(int)
	amount_by_state = defaultdict(float)
	for c in claims:
		state[c.state] += 1
		amount_by_state[c.state] += flt(c.total_claimed_amount)
	gps_km = sum_of(ds.days, "km")
	excess = [c for c in claims if c.excessive]

	return {
		"kpis": [
			kpi(_("Total KM (GPS)"), gps_km, "km", hint=_("Field trips in period"), drill="field:trips"),
			kpi(_("Claimed KM"), sum_of(period, "custom_claimed_km"), "km", drill="claim:all"),
			kpi(_("Eligible KM"), sum_of(period, "custom_eligible_km"), "km", hint=_("Limited to GPS-verified KM"), drill="claim:all"),
			kpi(_("Claims Submitted"), len(period), drill="claim:all"),
			kpi(_("Pending"), state["Pending"], tone=tone(state["Pending"]), hint=frappe.format(amount_by_state["Pending"], "Currency"), drill="claim:pending"),
			kpi(_("Approved"), state["Approved"], tone="ok", hint=frappe.format(amount_by_state["Approved"], "Currency"), drill="claim:approved"),
			kpi(_("Rejected"), state["Rejected"], drill="claim:rejected"),
			kpi(_("Claim Amount"), sum_of(period, "total_claimed_amount"), "currency", hint=_("Approved {0}").format(
				frappe.format(sum_of([c for c in period if c.state == "Approved"], "total_sanctioned_amount"), "Currency")), drill="claim:all"),
			kpi(_("Excess / Manual KM"), len(excess), tone=tone(len(excess)), drill="claim:excess"),
		],
		"sections": [
			table(_("Pending Claims"), CLAIM_COLS, claim_rows([c for c in claims if c.state == "Pending"]), drill="claim:pending",
				inline_actions=True, empty=_("No claims waiting")),
			table(_("Employee-wise Claims"), CLAIM_GROUP_COLS, [dict(r, _drill=f"claim:employee:{r.employee}") for r in claim_groups(claims, "employee_name")], width="half"),
			table(_("Team-wise Claims"), CLAIM_GROUP_COLS, claim_groups(claims, "team"), width="half"),
			chart(_("Claim Amount by Status"), "donut", [_("Pending"), _("Approved"), _("Rejected")],
				[{"name": _("Amount"), "values": [round(amount_by_state[s], 2) for s in ("Pending", "Approved", "Rejected")]}], width="third"),
			table(_("Excessive / Manual KM"), CLAIM_COLS, claim_rows(excess), drill="claim:excess", width="two-thirds", empty=_("No excess KM claims")),
		],
	}


def performance_board(ds):
	perf = ds.performance
	totals = frappe._dict()
	for f in ("assigned", "completed", "on_time", "working_hours", "field_hours", "office_hours", "km"):
		totals[f] = round(sum(flt(r[f]) for r in perf), 2)
	scores = [r.score for r in perf if r.score is not None]
	avg = round(sum(scores) / len(scores)) if scores else None

	return {
		"kpis": [
			kpi(_("Tasks Assigned"), totals.assigned, drill="task:all"),
			kpi(_("Tasks Completed"), totals.completed, tone="ok", drill="task:completed"),
			kpi(_("Completion %"), pct(totals.completed, totals.assigned), "pct", tone=pct_tone(pct(totals.completed, totals.assigned))),
			kpi(_("On-time Completion %"), pct(totals.on_time, totals.completed), "pct", tone=pct_tone(pct(totals.on_time, totals.completed))),
			kpi(_("Working Hours"), totals.working_hours, "hours", drill="att:all"),
			kpi(_("Field Hours"), totals.field_hours, "hours", drill="field:trips"),
			kpi(_("Office Hours"), totals.office_hours, "hours"),
			kpi(_("Field KM"), totals.km, "km", drill="field:trips"),
			kpi(_("Avg Score"), avg, "score", tone=score_tone(avg), hint=_("{0} below 60").format(len(ds.low_performers)), drill="perf:low"),
		],
		"sections": [
			bars(_("Score by Employee"), [
				{"label": r.employee_name, "value": r.score or 0, "tone": score_tone(r.score), "drill": f"task:employee:{r.employee}"}
				for r in sorted(perf, key=lambda r: -(r.score or 0))
			], fmt="score", width="third", subtitle=_("Completion 35 · On-time 25 · Attendance 20 · Hours 20")),
			table(_("Employee Performance"), PERF_COLS, sorted(perf, key=lambda r: -(r.score or 0)), drill="perf:all", width="two-thirds"),
			table(_("Team Performance"), GROUP_PERF_COLS, ds.group_performance("team"), width="half"),
			table(_("Department Performance"), GROUP_PERF_COLS, ds.group_performance("department"), width="half"),
		],
	}


def management_board(ds):
	live = live_rows(ds)
	present_now = sum(1 for r in live if r.live in ("In Field", "In Office", "Checked Out"))
	days = ds.days
	present = sum(1 for d in days if d.status in PRESENT)
	expected = sum(1 for d in days if d.status not in ("Holiday", "On Leave"))
	tasks = ds.tasks
	done = sum(1 for t in tasks if t.bucket == "Completed")
	completed = [t for t in tasks if t.bucket == "Completed"]
	open_tasks = [t for t in tasks if t.is_open]
	delayed = sum(1 for t in tasks if t.delayed)
	claims = all_claims(ds)
	perf = ds.performance
	scores = [r.score for r in perf if r.score is not None]
	avg = round(sum(scores) / len(scores)) if scores else None
	exc = ds.exceptions
	exc_count = defaultdict(int)
	for x in exc:
		exc_count[x.category] += 1
	hours = sum_of(days, "working_hours")
	expected_hours = sum(flt(r.expected_hours) for r in perf)
	ranked = sorted([r for r in perf if r.score is not None], key=lambda r: -r.score)

	return {
		"kpis": [
			kpi(_("Headcount"), len(ds.ids), drill="live:all"),
			kpi(_("Present Today"), present_now, hint=pct_hint(present_now, len(live)), tone="ok", drill="live:present"),
			kpi(_("Attendance %"), pct(present, expected), "pct", tone=pct_tone(pct(present, expected)), drill="att:all"),
			kpi(_("Open Tasks"), len(open_tasks), drill="task:open"),
			kpi(_("Delayed Tasks"), delayed, tone=tone(delayed), drill="task:delayed"),
			kpi(_("Field KM"), sum_of(days, "km"), "km", drill="field:trips"),
			kpi(_("Petrol Cost"), sum_of([c for c in claims if c.state == "Approved"], "total_sanctioned_amount"), "currency",
				hint=_("Approved · {0} pending").format(frappe.format(sum_of([c for c in claims if c.state == "Pending"], "total_claimed_amount"), "Currency")), drill="claim:all"),
			kpi(_("Avg Performance"), avg, "score", tone=score_tone(avg), drill="perf:all"),
			kpi(_("Open Exceptions"), len(exc), tone=tone(len(exc)), drill="exc:all"),
		],
		"sections": [
			stats(_("Workforce"), [
				{"label": _("Headcount"), "value": len(ds.ids), "fmt": "int", "drill": "live:all"},
				{"label": _("In field now"), "value": sum(1 for r in live if r.live == "In Field"), "fmt": "int", "drill": "live:In Field"},
				{"label": _("In office now"), "value": sum(1 for r in live if r.live == "In Office"), "fmt": "int", "drill": "live:In Office"},
				{"label": _("Not checked in"), "value": sum(1 for r in live if r.live in ("Not Checked In", "Absent")), "fmt": "int", "drill": "live:absent"},
			]),
			stats(_("Attendance"), [
				{"label": _("Attendance %"), "value": pct(present, expected), "fmt": "pct", "drill": "att:all"},
				{"label": _("Late arrivals"), "value": sum(1 for d in days if d.late), "fmt": "int", "drill": "att:late"},
				{"label": _("Missing punch"), "value": sum(1 for d in days if d.missing_punch), "fmt": "int", "drill": "att:missing_punch"},
				{"label": _("Absent days"), "value": sum(1 for d in days if d.status == "Absent"), "fmt": "int", "drill": "att:absent"},
			]),
			stats(_("Tasks"), [
				{"label": _("Completion %"), "value": pct(done, len(tasks)), "fmt": "pct", "drill": "task:completed"},
				{"label": _("On-time %"), "value": pct(sum(1 for t in completed if t.on_time), len(completed)), "fmt": "pct", "drill": "task:completed"},
				{"label": _("Open"), "value": len(open_tasks), "fmt": "int", "drill": "task:open"},
				{"label": _("Delayed"), "value": delayed, "fmt": "int", "drill": "task:delayed"},
			]),
			stats(_("Field Operations"), [
				{"label": _("Distance"), "value": sum_of(days, "km"), "fmt": "km", "drill": "field:trips"},
				{"label": _("Field hours"), "value": sum_of(days, "field_hours"), "fmt": "hours", "drill": "field:trips"},
				{"label": _("Sites visited"), "value": len(ds.stops), "fmt": "int", "drill": "field:sites"},
				{"label": _("GPS exceptions"), "value": len(ds.gps_exceptions), "fmt": "int", "drill": "gps:all"},
			]),
			stats(_("Productivity"), [
				{"label": _("Working hours"), "value": hours, "fmt": "hours", "drill": "att:all"},
				{"label": _("Hours vs expected"), "value": pct(hours, expected_hours), "fmt": "pct"},
				{"label": _("Avg score"), "value": avg, "fmt": "score", "drill": "perf:all"},
				{"label": _("Low productivity"), "value": len(ds.low_performers), "fmt": "int", "drill": "perf:low"},
			]),
			stats(_("Leave"), [
				{"label": _("On leave today"), "value": sum(1 for r in live if r.live == "On Leave"), "fmt": "int", "drill": "live:On Leave"},
				{"label": _("Leave days in period"), "value": sum(1 for d in days if d.status == "On Leave"), "fmt": "int", "drill": "att:leave"},
				{"label": _("Requests pending"), "value": sum(1 for a in ds.leave_apps if a.docstatus == 0 and a.status == "Open"), "fmt": "int", "drill": "leave:open"},
			]),
			stats(_("Petrol Cost"), [
				{"label": _("Claimed"), "value": sum_of(claims, "total_claimed_amount"), "fmt": "currency", "drill": "claim:all"},
				{"label": _("Approved"), "value": sum_of([c for c in claims if c.state == "Approved"], "total_sanctioned_amount"), "fmt": "currency", "drill": "claim:approved"},
				{"label": _("Pending"), "value": sum_of([c for c in claims if c.state == "Pending"], "total_claimed_amount"), "fmt": "currency", "drill": "claim:pending"},
				{"label": _("Excess KM claims"), "value": sum(1 for c in claims if c.excessive), "fmt": "int", "drill": "claim:excess"},
			]),
			stats(_("Performance"), [
				{"label": _("Top: {0}").format(r.employee_name), "value": r.score, "fmt": "score", "drill": f"task:employee:{r.employee}"} for r in ranked[:2]
			] + [
				{"label": _("Lowest: {0}").format(r.employee_name), "value": r.score, "fmt": "score", "drill": f"task:employee:{r.employee}"} for r in ranked[-2:][::-1] if len(ranked) > 2
			]),
			bars(_("Exceptions"), [
				{"label": label, "value": exc_count[key], "drill": f"exc:{key}", "tone": "bad" if exc_count[key] else "ok"} for key, label in EXC_CATEGORIES.items()
			], width="third"),
			table(_("Department Summary"), GROUP_PERF_COLS, ds.group_performance("department"), width="full"),
			chart(_("Attendance & Hours Trend"), "line", [frappe.format(dt, "Date") for dt, _b in ds.daily_trend()], [
				{"name": _("Present"), "values": [b["present"] for _dt, b in ds.daily_trend()]},
				{"name": _("Absent"), "values": [b["absent"] for _dt, b in ds.daily_trend()]},
				{"name": _("On Leave"), "values": [b["leave"] for _dt, b in ds.daily_trend()]},
			]),
			bars(_("Petrol Cost by Team"), [
				{"label": r.label, "value": r.approved_amount + sum_of([c for c in claims if c.team == r.label and c.state == "Pending"], "total_claimed_amount")}
				for r in claim_groups(claims, "team")
			], fmt="currency", subtitle=_("Approved + pending")),
		],
	}


def exceptions_board(ds):
	rows = exception_rows(ds)
	count = defaultdict(int)
	by_emp = defaultdict(int)
	for r in rows:
		count[r.category] += 1
		by_emp[r.employee_name] += 1

	return {
		"kpis": [kpi(_(label), count[key], tone="bad" if count[key] else "ok", drill=f"exc:{key}") for key, label in EXC_CATEGORIES.items()],
		"sections": [
			table(_("Needs Action"), EXC_COLS, rows, drill="exc:all", width="two-thirds", limit=25, empty=_("Nothing needs attention right now")),
			bars(_("Exceptions by Employee"), [
				{"label": name, "value": n, "tone": "bad"} for name, n in sorted(by_emp.items(), key=lambda x: -x[1])
			], width="third"),
		],
	}


BUILDERS = {
	"employee": employee_board,
	"team": team_board,
	"hr": hr_board,
	"field": field_board,
	"tasks": tasks_board,
	"claims": claims_board,
	"performance": performance_board,
	"management": management_board,
	"exceptions": exceptions_board,
}


def pct_hint(part, whole):
	value = pct(part, whole)
	return _("{0}% of team").format(value) if value is not None else None


def pct_tone(value):
	if value is None:
		return None
	return "ok" if value >= 90 else ("warn" if value >= 75 else "bad")


# ---- drill-down ------------------------------------------------------------


def drill(ds, key):
	"""Return (title, column spec, rows) for a drill key such as `task:delayed` or `task:project:PROJ-0001`."""
	parts = key.split(":", 2)
	group, what, arg = parts[0], parts[1] if len(parts) > 1 else "all", parts[2] if len(parts) > 2 else None

	if group == "att":
		pick = {
			"all": ("Attendance", lambda d: d.status != "Holiday"),
			"present": ("Present", lambda d: d.status in PRESENT),
			"absent": ("Absent / Not checked in", lambda d: d.status in ("Absent", "Not Checked In")),
			"leave": ("On Leave", lambda d: d.status == "On Leave"),
			"late": ("Late Arrivals", lambda d: d.late),
			"missing_punch": ("Missing Punch", lambda d: d.missing_punch),
			"missing": ("Missing Attendance", lambda d: d.missing),
			"exceptions": ("Late / Missing Punch", lambda d: d.late or d.missing_punch),
			"field": ("Field Days", lambda d: d.mode == "Field"),
			"office": ("Office Days", lambda d: d.mode == "Office"),
		}.get(what) or unknown_drill(key)
		return pick[0], DAY_COLS, day_rows(sorted([d for d in ds.days if pick[1](d)], key=lambda d: (d.date, d.employee_name), reverse=True))

	if group == "live":
		rows = live_rows(ds)
		test = {
			"all": lambda r: True,
			"present": lambda r: r.live in ("In Field", "In Office", "Checked Out"),
			"absent": lambda r: r.live in ("Absent", "Not Checked In"),
			"field": lambda r: r.mode == "Field",
			"office": lambda r: r.mode == "Office",
		}.get(what, lambda r: r.live == what)
		return f"Current Status: {what.title() if what in ('all', 'present', 'absent', 'field', 'office') else what}", LIVE_COLS, [r for r in rows if test(r)]

	if group == "task":
		tasks = ds.tasks
		if what == "all":
			title, picked = "All Tasks", tasks
		elif what == "completed":
			title, picked = "Completed Tasks", [t for t in tasks if t.bucket == "Completed"]
		elif what == "in_progress":
			title, picked = "Tasks In Progress", [t for t in tasks if t.bucket == "In Progress"]
		elif what == "pending":
			title, picked = "Pending Tasks", [t for t in tasks if t.bucket == "Pending"]
		elif what == "open":
			title, picked = "Open Tasks", [t for t in tasks if t.is_open]
		elif what == "delayed":
			title, picked = "Delayed Tasks", [t for t in tasks if t.delayed]
		elif what == "age":
			title, picked = f"Open Tasks Aged {arg}", [t for t in tasks if t.is_open and age_bucket(t.age_days) == arg]
		elif what == "project":
			title, picked = f"Project: {arg}", [t for t in tasks if t.project_name == arg or t.project == arg]
		elif what == "category":
			title, picked = f"{arg} Tasks", [t for t in tasks if t.category == arg]
		elif what == "employee":
			title, picked = f"Tasks: {ds.emp_name(arg)}", [t for t in tasks if t.employee == arg]
		else:
			title, picked = "Tasks", []
		return title, TASK_COLS, task_rows(picked)

	if group == "claim":
		claims = all_claims(ds)
		test = {
			"all": lambda c: True,
			"pending": lambda c: c.state == "Pending",
			"approved": lambda c: c.state == "Approved",
			"rejected": lambda c: c.state == "Rejected",
			"excess": lambda c: c.excessive,
			"employee": lambda c: c.employee == arg,
		}.get(what) or unknown_drill(key)
		return f"Petrol Claims: {ds.emp_name(arg) if arg else what.title()}", CLAIM_COLS, claim_rows([c for c in claims if test(c)])

	if group == "leave":
		if what == "balances":
			return "Leave Balances", BALANCE_COLS, ds.leave_balances
		test = {
			"all": lambda a: True,
			"open": lambda a: a.docstatus == 0 and a.status == "Open",
			"approved": lambda a: a.status == "Approved",
			"rejected": lambda a: a.status == "Rejected",
		}.get(what) or unknown_drill(key)
		return f"Leave Applications: {what.title()}", LEAVE_COLS, leave_rows([a for a in ds.leave_apps if test(a)])

	if group == "reg":
		regs = ds.regularizations if what == "all" else [r for r in ds.regularizations if r.docstatus == 0]
		return "Attendance Regularization", REG_COLS, reg_rows(regs)

	if group == "approvals":
		return "Pending Approvals", APPROVAL_COLS, ds.approvals

	if group == "field":
		if what == "sites":
			return "Sites Visited", STOP_COLS, stop_rows(ds)
		trips = trip_rows(ds)
		if arg:
			trips = [t for t in trips if t.employee == arg]
		return f"Trips{': ' + ds.emp_name(arg) if arg else ''}", TRIP_COLS, trips

	if group == "gps":
		return "GPS / Movement Exceptions", GPS_COLS, ds.gps_exceptions

	if group == "perf":
		rows = ds.low_performers if what == "low" else ds.performance
		return "Low Productivity" if what == "low" else "Employee Performance", PERF_COLS, sorted(rows, key=lambda r: r.score or 0)

	if group == "exc":
		category = None if what == "all" else what
		return EXC_CATEGORIES.get(category, "All Exceptions"), EXC_COLS, exception_rows(ds, category)

	frappe.throw(_("Unknown drill-down {0}").format(key))


def unknown_drill(key):
	frappe.throw(_("Unknown drill-down {0}").format(key))
