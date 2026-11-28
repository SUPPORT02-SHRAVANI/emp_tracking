# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# NOC reports: the numbers of the client's NOC report workbook, worked out from Complaint Information
#
# How this file works
#   One place computes every NOC summary, so the five Script Reports (report/noc_*) and the NOC
#   Dashboard page always show the same numbers. Each workbook tab maps to one function:
#     PENDING SUMMARY / TEAM WISE PENDING SUMMARY -> pending_summary(by_team)
#     UNIQUE CUT MASTER                           -> cut_master()
#     UNIQUE CUT TEAM SUMMARY                     -> cut_summary(by_team)
#     MAJOR OUTAGE CLOSURE                        -> major_outage()
#     ALL TEAM SUMMARY (pivots)                   -> sla_tat_summary(group_by)
#   Sheet columns -> fields: SR RECEIVED = complaint_date_and_time, Team SR CLOSED =
#   evision_closed_on, Actual SLA = evision_sla (closed - received within 4 h), MAINTAIN BY =
#   maintenance_team (vendor when no team), UNIQUE CUT = unique_cut, Splicer / SPLICER 1 =
#   splicer / second_splicer.
#   Scope (filters, defaults = the workbook's scope): own maintenance teams only (no vendors) and
#   RFO "Own Fiber Issue" only (a blank RFO, i.e. not closed yet, also counts), terminations left out.
#   A finished complaint without a Team SR closed time counts as closed at its Company close
#   time; with neither time it is left out (it would otherwise stay "pending" for ever). Checked on 2026-11-26 against the workbook: 3,555 of the 3,576
#   complaints found in both are Own Fiber Issue; the rest of the app's team complaints are NO
#   FIBER ISSUE / NOT OUR FIBER / IGNORE / terminations, which the workbook leaves out.
#   Rules copied from the workbook's LOGIC notes:
#     Opening carry forward = previous day's closing pending; Available = new + opening;
#     Closing pending = MAX(0, available - closed). The first day's opening is the real backlog
#     (received before it and not closed before it), where the workbook started from 0.
#     A cut's owner = MAINTAIN BY of its earliest SR; it is closed on the latest SR close, only
#     when every SR under it is closed; its SLA is OUT if any SR is OUT, else IN.
#     TAT bucket = days from received to Team SR closed: Within 1 Day / 1 Day / 2 Days / 3+ Days
#     (the workbook labels 3 days and more ">3 Days"); not closed = Open.
#   Added 2026-11-26 (user's points): who closed (per team and day), day / night calls (received
#   08:00-19:59 = Day), performance month-wise / day-wise (performance), team availability
#   (team_availability: Maintenance Team members Present in Attendance vs who was sent on the
#   day's complaints) and field staff hours per place (location_hours, same rules as the NOC
#   Dashboard's Employee sheet).
#
# Change log
#   2026-11-26  Created (user's request: show the NOC dashboard and reports like the NOC workbook).
#   2026-11-27  location_hours() takes an employee list (Field Staff Location Hours: team members).
#   2026-11-27  Own-fibre RFO, outage days per month and day / night hours from EVision Settings.
#   2026-11-28  Pending now and In SLA % through the editable formulas (EVision Settings > Formulas).
#   2026-11-26  who_closed, shift_of, performance, team_availability, location_hours, empty_message.
#   2026-11-26  Blank RFO counts as own fibre (RFO is filled only at closing), so new open
#               complaints show in the reports straight away.
# ---------------------------------------------------------------------------------------------

from collections import Counter, defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, get_datetime, get_first_day, getdate, nowdate

# 2026-11-27: own-fibre RFO, outage days per month and day / night hours come from EVision
# Settings; OWN_FIBER, OUTAGE_DAYS_PER_MONTH and DAY_START_HOUR / NIGHT_START_HOUR are the defaults
from emp_tracking.emp_tracking.doctype.evision_settings.evision_settings import formula, setting, sla_pct

from emp_tracking.emp_tracking.doctype.complaint_information.complaint_information import DONE_STATES

OWN_FIBER = "Own Fiber Issue"
OTHER = "OTHER"
IN, OUT = "IN", "OUT"
TAT_BUCKETS = ("Within 1 Day", "1 Day", "2 Days", "3+ Days")
OPEN = "Open"
# Major Outage Closure: the busiest days kept per team and month
OUTAGE_DAYS_PER_MONTH = 2
# Group-by choices of the SLA / TAT summary (the workbook's pivots), value -> row keys
GROUP_BY = {
	"Month, Team": ("month", "team"),
	"Month, Team, Splicer": ("month", "team", "splicer"),
	"Splicer, Team, Month": ("splicer", "team", "month"),
	"Team, Month, Date": ("team", "month", "date"),
	"Month, Date, Team, Splicer": ("month", "date", "team", "splicer"),
}
KEY_LABELS = {"month": "Month", "team": "Team", "splicer": "Splicer", "date": "Date"}


# ---- filters and data ---------------------------------------------------------------------


# Date: 2026-11-26
def normalise(filters):
	"""Filters with defaults: this month up to today, the workbook's scope switched on."""
	f = frappe._dict(filters or {})
	f.to_date = getdate(f.to_date or nowdate())
	f.from_date = getdate(f.from_date or get_first_day(f.to_date))
	if f.from_date > f.to_date:
		frappe.throw(_("From date must be on or before To date"))
	# Checks arrive as 0/1 or "0"/"1"; missing means on (the workbook's scope)
	f.own_fiber_only = int(f.own_fiber_only if f.own_fiber_only not in (None, "") else 1)
	f.own_teams_only = int(f.own_teams_only if f.own_teams_only not in (None, "") else 1)
	return f


# Date: 2026-11-26
def load(f, received_from=None):
	"""Complaints that matter between f.from_date and f.to_date: received by the end of the range
	and not closed before it starts (so the opening backlog is in), or, with received_from, only
	those received in [received_from, to_date]. frappe.get_list applies the user's permissions."""
	start, end = get_datetime(f.from_date), get_datetime(add_days(f.to_date, 1))
	filters = [["complaint_date_and_time", "<", end], ["complaint_date_and_time", "is", "set"]]
	or_filters = None
	if received_from:
		filters.append(["complaint_date_and_time", ">=", get_datetime(received_from)])
	else:
		or_filters = [["evision_closed_on", "is", "not set"], ["evision_closed_on", ">=", start]]
	if f.own_fiber_only:
		# the workbook's scope: fibre faults of our own, no terminations.
		# 2026-11-26: RFO is filled only when closing, so a blank RFO (still open, not decided) is
		# kept; only complaints marked with another RFO are left out (filtered after the query,
		# because the closing-date OR group below is the query's only OR group).
		filters.append(["request_type", "!=", "Termination"])
	if f.own_teams_only:
		filters.append(["maintenance_team", "is", "set"])
	if f.team:
		filters.append(["maintenance_team", "=", f.team])
	rows = frappe.get_list(
		"Complaint Information",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "complaint_code", "unique_cut", "complaint_date_and_time", "evision_closed_on",
			"company_closed_on", "workflow_state", "evision_sla", "maintenance_team", "mapped_vendor", "splicer",
			"second_splicer", "rider", "second_rider", "rfo"],
		limit_page_length=0,
	)
	# A finished complaint with no Team SR closed time (46 imported 2025 complaints on newsite.local)
	# is closed at the Company close time; with neither it is left out, rather than counted as
	# pending for ever.
	rows = [r for r in rows if r.evision_closed_on or r.company_closed_on or r.workflow_state not in DONE_STATES]
	if f.own_fiber_only:
		rows = [r for r in rows if not r.rfo or r.rfo == setting("own_fiber_rfo")]
	start_dt = get_datetime(f.from_date)
	names = employee_names({r.get(k) for r in rows for k in ("splicer", "second_splicer", "rider", "second_rider")})
	kept = []
	for r in rows:
		r.received = get_datetime(r.complaint_date_and_time)
		closed_on = r.evision_closed_on or (r.company_closed_on if r.workflow_state in DONE_STATES else None)
		r.closed = get_datetime(closed_on) if closed_on else None
		if not received_from and r.closed and r.closed < start_dt:
			continue  # closed (by the company time) before the range: not part of it
		kept.append(r)
	rows = kept
	for r in rows:
		r.received_day = r.received.date()
		r.closed_day = r.closed.date() if r.closed else None
		r.team = r.maintenance_team or r.mapped_vendor or OTHER
		r.cut = r.unique_cut or r.complaint_code or r.name
		r.sla = (r.evision_sla or "").upper() if r.closed else ""
		r.splicer_name = names.get(r.splicer) or OTHER
		r.splicer2_name = names.get(r.second_splicer) or ""
		r.tat = tat_bucket(r)
		# 2026-11-26: day / night call by received time, and everyone sent on it (team availability)
		r.shift = shift_of(r.received)
		r.people = [(k, r.get(k), names.get(r.get(k)) or r.get(k)) for k in ("splicer", "second_splicer", "rider", "second_rider") if r.get(k)]
	return rows


# Date: 2026-11-26
# Day call = received 08:00 to 19:59, night call = the rest (user's choice, 2026-11-26).
DAY_START_HOUR, NIGHT_START_HOUR = 8, 20
DAY, NIGHT = "Day", "Night"


def shift_of(received):
	return DAY if setting("day_start_hour") <= received.hour < setting("night_start_hour") else NIGHT


# Date: 2026-11-26
def employee_names(ids):
	ids = [i for i in ids if i]
	if not ids:
		return {}
	rows = frappe.get_all("Employee", filters={"name": ["in", ids]}, fields=["name", "employee_name"])
	return {r.name: (r.employee_name or r.name).upper() for r in rows}


# Date: 2026-11-26
def tat_bucket(r):
	"""Workbook TAT Bucket from Team SR CLOSED - SR RECEIVED (in whole days)."""
	if not r.closed:
		return OPEN
	days = (r.closed - r.received).total_seconds() / 86400
	if days < 1:
		return TAT_BUCKETS[0]
	return TAT_BUCKETS[min(int(days), 3)]


# Date: 2026-11-26
def days_between(f):
	return [add_days(f.from_date, i) for i in range(date_diff(f.to_date, f.from_date) + 1)]


# ---- PENDING SUMMARY / TEAM WISE PENDING SUMMARY ------------------------------------------


# Date: 2026-11-26
def pending_summary(filters, by_team=False):
	"""One row per day (per team with by_team): new SRs, opening carry forward, available, team
	SRs closed, closing pending, and the closed SRs In / Out of SLA."""
	f = normalise(filters)
	return carry_forward(f, load(f), by_team, start=lambda r: r.received_day, end=lambda r: r.closed_day,
		sla=lambda r: r.sla, closer=lambda r: r.splicer_name)


# Date: 2026-11-26
# 2026-11-26: `closer` (optional) names who closed each item; every row then carries who_closed,
# "NAME (count), ..." for the items closed that day (user's request: "who closed it").
def carry_forward(f, items, by_team, start, end, sla, closer=None):
	"""The workbook's daily carry-forward table over `items` (SRs or cuts), each with .team."""
	days = days_between(f)
	teams = sorted({i.team for i in items}) if by_team else [None]
	new, closed, in_sla, out_sla = Counter(), Counter(), Counter(), Counter()
	closers = defaultdict(Counter)
	opening = Counter()
	for i in items:
		key = i.team if by_team else None
		s, e = start(i), end(i)
		if s < f.from_date and (e is None or e >= f.from_date):
			opening[key] += 1  # real backlog on the first day
		if f.from_date <= s <= f.to_date:
			new[(key, s)] += 1
		if e and f.from_date <= e <= f.to_date:
			closed[(key, e)] += 1
			if sla(i) == IN:
				in_sla[(key, e)] += 1
			elif sla(i) == OUT:
				out_sla[(key, e)] += 1
			if closer and closer(i):
				closers[(key, e)][closer(i)] += 1

	rows = []
	carry = dict(opening)
	for day in days:
		for team in teams:
			k = (team, day)
			available = new[k] + carry.get(team, 0)
			# 2026-11-28: editable "Pending now" formula (default max(0, opening + received - closed))
			closing = cint(formula("pending_now", opening=carry.get(team, 0), received=new[k], closed=closed[k]) or 0)
			rows.append(frappe._dict(date=day, team=team, new=new[k], opening=carry.get(team, 0),
				available=available, closed=closed[k], closing=closing, in_sla=in_sla[k], out_sla=out_sla[k],
				who_closed=with_counts(closers[k])))
			carry[team] = closing
	return rows


# ---- UNIQUE CUT MASTER / UNIQUE CUT TEAM SUMMARY ------------------------------------------


# Date: 2026-11-26
def build_cuts(rows):
	"""SRs -> one entry per unique cut, by the workbook's CUT LOGIC."""
	by_cut = defaultdict(list)
	for r in rows:
		by_cut[r.cut].append(r)
	cuts = []
	for cut, srs in by_cut.items():
		srs.sort(key=lambda r: r.received)
		first = srs[0]
		all_closed = all(r.closed for r in srs)
		last = max(srs, key=lambda r: r.closed) if all_closed else None
		cuts.append(frappe._dict(
			cut=cut, first_received=first.received, first_day=first.received_day, team=first.team,
			sr_count=len(srs), closed=last.closed if last else None, closed_day=last.closed_day if last else None,
			sla=(OUT if any(r.sla == OUT for r in srs) else IN) if all_closed else "",
			# who closed the cut: the splicer of the SR closed last
			closer=last.splicer_name if last else "", complaints=[r.name for r in srs],
		))
	return sorted(cuts, key=lambda c: c.first_received)


# Date: 2026-11-26
def cut_master(filters):
	"""UNIQUE CUT MASTER: cuts first received in the date range."""
	f = normalise(filters)
	return [c for c in build_cuts(load(f)) if f.from_date <= c.first_day <= f.to_date]


# Date: 2026-11-26
def cut_summary(filters, by_team=True):
	"""UNIQUE CUT TEAM SUMMARY: the carry-forward table counted in cuts instead of SRs."""
	f = normalise(filters)
	return carry_forward(f, build_cuts(load(f)), by_team, start=lambda c: c.first_day, end=lambda c: c.closed_day,
		sla=lambda c: c.sla, closer=lambda c: c.closer)


# ---- MAJOR OUTAGE CLOSURE -----------------------------------------------------------------


# Date: 2026-11-26
def major_outage(filters):
	"""Per month and team, the OUTAGE_DAYS_PER_MONTH days with the most new cuts (rank 1 = most;
	ties go to the bigger total, then the earlier day), with the cut figures of that day and who
	worked: closers of the cuts closed that day, splicers / 2nd splicers on the SRs received that
	day, and how many different splicers that is. The workbook's PRESENT TEAM COUNT and AVAILABLE
	SPLICER were typed by hand; "Splicers Working" is the closest figure in the data."""
	f = normalise(filters)
	rows = load(f)
	cuts = build_cuts(rows)
	table = carry_forward(f, cuts, True, start=lambda c: c.first_day, end=lambda c: c.closed_day, sla=lambda c: c.sla)

	closers = defaultdict(Counter)
	for c in cuts:
		if c.closed_day and c.closer:
			closers[(c.team, c.closed_day)][c.closer] += 1
	splicers, splicers2 = defaultdict(Counter), defaultdict(Counter)
	for r in rows:
		splicers[(r.team, r.received_day)][r.splicer_name] += 1
		if r.splicer2_name:
			splicers2[(r.team, r.received_day)][r.splicer2_name] += 1

	by_month_team = defaultdict(list)
	for t in table:
		if t.new:
			by_month_team[(get_first_day(t.date), t.team)].append(t)
	out = []
	for (month, team) in sorted(by_month_team):
		days = sorted(by_month_team[(month, team)], key=lambda t: (-t.new, -t.available, t.date))
		for rank, t in enumerate(days[:setting("outage_days_per_month")], 1):
			k = (team, t.date)
			working = {n for n in splicers[k] if n != OTHER} | set(splicers2[k]) | {n for n in closers[k] if n != OTHER}
			out.append(frappe._dict(
				month=month, team=team, rank=rank, date=t.date, new=t.new, opening=t.opening, total=t.available,
				closed=t.closed, closing=t.closing, in_sla=t.in_sla, out_sla=t.out_sla,
				who_closed=with_counts(closers[k]) or _("NO CUT CLOSED"), splicers=with_counts(splicers[k]),
				splicers2=with_counts(splicers2[k]) or "NA", working=len(working),
			))
	return out


# Date: 2026-11-26
def with_counts(counter):
	"""Counter -> "NAME (3), OTHER NAME (1)", most first (the workbook's WHO CLOSED format)."""
	return ", ".join(f"{name} ({n})" for name, n in counter.most_common())


# ---- ALL TEAM SUMMARY (pivots) ------------------------------------------------------------


# Date: 2026-11-26
def sla_tat_summary(filters, group_by="Month, Team"):
	"""SRs received in the range counted by the chosen row keys against TAT bucket x SLA (the
	workbook's pivots count SR rows), plus unique cuts, In-SLA % and average MTTR (pivot 14)."""
	f = normalise(filters)
	keys = GROUP_BY.get(group_by) or GROUP_BY["Month, Team"]
	rows = load(f, received_from=f.from_date)
	groups = defaultdict(list)
	for r in rows:
		values = {"month": get_first_day(r.received_day), "team": r.team, "splicer": r.splicer_name, "date": r.received_day}
		groups[tuple(values[k] for k in keys)].append(r)
	out = []
	for key in sorted(groups):
		members = groups[key]
		row = frappe._dict(zip(keys, key))
		for bucket in TAT_BUCKETS:
			for sla in (IN, OUT):
				row[column_key(bucket, sla)] = sum(1 for r in members if r.tat == bucket and r.sla == sla)
		row.open = sum(1 for r in members if r.tat == OPEN)
		row.in_sla = sum(1 for r in members if r.sla == IN)
		row.out_sla = sum(1 for r in members if r.sla == OUT)
		row.total = len(members)
		row.cuts = len({r.cut for r in members})
		closed = [r for r in members if r.closed]
		row.sla_pct = sla_pct(row.in_sla, row.out_sla) if closed else None
		row.avg_mttr = round(sum((r.closed - r.received).total_seconds() for r in closed) / len(closed) / 3600, 2) if closed else None
		out.append(row)
	return keys, out


# Date: 2026-11-26
def column_key(bucket, sla):
	return frappe.scrub(f"{bucket} {sla}").replace("+", "plus")


# ---- performance: month-wise / day-wise, day and night calls (2026-11-26) -------------------

PERF_ROWS = {
	"Month": ("month",),
	"Day": ("date",),
	"Month, Team": ("month", "team"),
	"Day, Team": ("date", "team"),
	"Month, Splicer": ("month", "splicer"),
	"Team, Month": ("team", "month"),
}


# Date: 2026-11-26
def performance(filters, rows_by="Month"):
	"""SRs received in the range per period (and team / splicer), split into day and night calls:
	received, closed, In / Out of SLA, In-SLA % and average MTTR (hours) for each, plus totals."""
	f = normalise(filters)
	keys = PERF_ROWS.get(rows_by) or PERF_ROWS["Month"]
	groups = defaultdict(list)
	for r in load(f, received_from=f.from_date):
		values = {"month": get_first_day(r.received_day), "date": r.received_day, "team": r.team, "splicer": r.splicer_name}
		groups[tuple(values[k] for k in keys)].append(r)
	out = []
	for key in sorted(groups):
		row = frappe._dict(zip(keys, key))
		for prefix, members in (("day", [r for r in groups[key] if r.shift == DAY]),
				("night", [r for r in groups[key] if r.shift == NIGHT]), ("all", groups[key])):
			row.update(figures(prefix, members))
		out.append(row)
	return keys, out


# Date: 2026-11-26
def figures(prefix, members):
	closed = [r for r in members if r.closed]
	in_sla = sum(1 for r in closed if r.sla == IN)
	out_sla = sum(1 for r in closed if r.sla == OUT)
	return {
		f"{prefix}_received": len(members),
		f"{prefix}_closed": len(closed),
		f"{prefix}_in": in_sla,
		f"{prefix}_out": out_sla,
		f"{prefix}_pct": sla_pct(in_sla, out_sla),
		f"{prefix}_mttr": round(sum((r.closed - r.received).total_seconds() for r in closed) / len(closed) / 3600, 1)
			if closed else None,
	}


# ---- team availability per day (2026-11-26) -------------------------------------------------

PRESENT = ("Present", "Half Day", "Work From Home")


# Date: 2026-11-26
def team_availability(filters):
	"""Per day and team: the team's members (Maintenance Team > Members), who of them was Present
	in Attendance (submitted), who was sent on that day's complaints (splicer / rider / 2nd), and
	present members who got no complaint. Teams without a member list still show who was sent."""
	f = normalise(filters)
	team_filter = {"parent": f.team} if f.team else {}
	members = frappe.get_all("Maintenance Team Member", filters={"parenttype": "Maintenance Team", **team_filter},
		fields=["parent", "employee", "employee_name", "role"], limit_page_length=0)
	by_team = defaultdict(list)
	for m in members:
		by_team[m.parent].append(m)

	present = defaultdict(set)  # day -> employees present
	if members:
		for a in frappe.get_all("Attendance", filters={"docstatus": 1, "status": ["in", PRESENT],
				"attendance_date": ["between", [f.from_date, f.to_date]], "employee": ["in", list({m.employee for m in members})]},
				fields=["employee", "attendance_date"], limit_page_length=0):
			present[getdate(a.attendance_date)].add(a.employee)

	sent = defaultdict(Counter)  # (team, day) -> {name: complaints}
	sent_ids = defaultdict(set)
	received = Counter()
	for r in load(f, received_from=f.from_date):
		received[(r.team, r.received_day)] += 1
		for _field, emp, name in r.people:
			sent[(r.team, r.received_day)][(name or emp).upper()] += 1
			sent_ids[(r.team, r.received_day)].add(emp)

	teams = sorted(set(by_team) | {t for t, _d in received})
	out = []
	for day in days_between(f):
		for team in teams:
			k = (team, day)
			team_members = by_team.get(team, [])
			here = [m for m in team_members if m.employee in present[day]]
			idle = [m for m in here if m.employee not in sent_ids[k]]
			if not (team_members or received[k] or sent[k]):
				continue
			out.append(frappe._dict(
				date=day, team=team, members=len(team_members),
				splicers=sum(1 for m in team_members if m.role == "Splicer"),
				present=len(here), present_splicers=sum(1 for m in here if m.role == "Splicer"),
				present_names=", ".join(f"{m.employee_name or m.employee} ({m.role})" for m in here),
				received=received[k], assigned=len(sent[k]), assigned_names=with_counts(sent[k]),
				idle_names=", ".join(m.employee_name or m.employee for m in idle),
				no_members=not team_members,
			))
	return out


# ---- field staff hours per place per day (2026-11-26) ----------------------------------------


# Date: 2026-11-26
def location_hours(filters, employees=None):
	"""Hours at home / office / complaint sites (field) / elsewhere per field employee per day,
	from the phone's Location Pings, with the complaints they were sent on. Same rules as the NOC
	Dashboard's Employee sheet (noc_dashboard.add_location_hours / add_complaint_counts). Employees:
	the given list (2026-11-27: the report passes the team members), else the one picked, else
	everyone with Work Type = Field or with pings in the range."""
	from emp_tracking.emp_tracking.page.noc_dashboard.noc_dashboard import (
		LOCATION_TYPES,
		add_complaint_counts,
		add_location_hours,
		new_day,
	)

	f = normalise(filters)
	if employees is not None:
		employees = list(employees)
	elif f.employee:
		employees = [f.employee]
	else:
		pinged = frappe.get_all("Location Ping", filters={"timestamp": ["between", [f.from_date, f.to_date]]},
			pluck="employee", distinct=True, limit_page_length=0)
		field = frappe.get_all("Employee", filters={"status": "Active", "custom_work_type": "Field"}, pluck="name") \
			if frappe.get_meta("Employee").has_field("custom_work_type") else []
		employees = sorted(set(pinged) | set(field))
	names = dict(frappe.get_all("Employee", filters={"name": ["in", employees or [""]]},
		fields=["name", "employee_name"], as_list=True))
	out = []
	for emp in employees:
		days = {d: new_day() for d in days_between(f)}
		add_location_hours(days, emp, f.from_date, f.to_date)
		add_complaint_counts(days, emp, f.from_date, f.to_date)
		for day, v in days.items():
			total = sum(v[t] for t in LOCATION_TYPES)
			if not (total or v["complaints"]):
				continue  # a day with no pings and no complaints adds nothing
			out.append(frappe._dict(employee=emp, employee_name=names.get(emp) or emp, date=day,
				**{t: round(v[t] / 3600, 2) for t in LOCATION_TYPES}, total=round(total / 3600, 2),
				complaints=v["complaints"]))
	return out


# ---- empty periods (2026-11-26) -------------------------------------------------------------


# Date: 2026-11-26
def empty_message(filters):
	"""Shown by the NOC reports instead of an empty chart and rows of dashes when nothing was
	received or closed in the range: says so, and names the latest complaint date on the site."""
	f = normalise(filters)
	latest = frappe.get_list("Complaint Information", fields=["complaint_date_and_time"],
		order_by="complaint_date_and_time desc", limit_page_length=1)
	tail = ""
	if latest and latest[0].complaint_date_and_time:
		tail = " " + _("The latest complaint on this site was received on {0}.").format(
			frappe.utils.formatdate(latest[0].complaint_date_and_time, "d MMM yyyy"))
	return (
		'<div style="padding:18px 20px;border:1px dashed var(--ev-border-strong, #ddd);border-radius:12px;'
		'text-align:center;font-size:13px;color:var(--ev-text-3, #555)">'
		f'<div style="font-weight:600;color:var(--ev-text, #171717);margin-bottom:4px">{_("No complaints in this period")}</div>'
		+ _("Nothing was received or closed between {0} and {1}.").format(
			frappe.utils.formatdate(f.from_date, "d MMM yyyy"), frappe.utils.formatdate(f.to_date, "d MMM yyyy"))
		+ tail + " " + _("Pick other dates above.") + "</div>"
	)


# Date: 2026-11-26
def nothing_happened(rows):
	"""True when a carry-forward table has no SR / cut received, closed or pending on any day."""
	return not any(r.new or r.closed or r.opening for r in rows)


# ---- NOC Dashboard ------------------------------------------------------------------------


# Date: 2026-11-26
@frappe.whitelist()
def get_performance(from_date=None, to_date=None, team=None, own_fiber_only=1, own_teams_only=1):
	"""NOC Dashboard "Performance" section: KPI totals, the daily pending series, a row per team,
	TAT buckets and the major outage days, all from the functions above."""
	frappe.has_permission("Complaint Information", "read", throw=True)
	f = normalise({"from_date": from_date, "to_date": to_date, "team": team,
		"own_fiber_only": own_fiber_only, "own_teams_only": own_teams_only})
	rows = load(f)
	cuts = build_cuts(rows)
	sr_args = dict(start=lambda r: r.received_day, end=lambda r: r.closed_day, sla=lambda r: r.sla)
	cut_args = dict(start=lambda c: c.first_day, end=lambda c: c.closed_day, sla=lambda c: c.sla)
	daily = carry_forward(f, rows, False, **sr_args)
	team_days = carry_forward(f, rows, True, **sr_args)
	cut_days = carry_forward(f, cuts, True, **cut_args)

	received = [r for r in rows if f.from_date <= r.received_day <= f.to_date]
	closed = [r for r in rows if r.closed_day and f.from_date <= r.closed_day <= f.to_date]
	in_sla = sum(1 for r in closed if r.sla == IN)
	out_sla = sum(1 for r in closed if r.sla == OUT)

	teams = []
	for team_name in sorted({t.team for t in team_days}):
		mine = [t for t in team_days if t.team == team_name]
		my_cuts = [t for t in cut_days if t.team == team_name]
		t_in, t_out = sum(t.in_sla for t in mine), sum(t.out_sla for t in mine)
		teams.append({
			"team": team_name, "received": sum(t.new for t in mine), "closed": sum(t.closed for t in mine),
			"pending": mine[-1].closing if mine else 0, "in_sla": t_in, "out_sla": t_out,
			"sla_pct": sla_pct(t_in, t_out),
			"new_cuts": sum(t.new for t in my_cuts), "closed_cuts": sum(t.closed for t in my_cuts),
		})

	return {
		"from_date": str(f.from_date),
		"to_date": str(f.to_date),
		"kpis": {
			# 2026-11-26: for the dashboard's carry-forward strip (opening + received - closed = pending)
			"opening": daily[0].opening if daily else 0,
			"received": len(received),
			"closed": len(closed),
			"pending": daily[-1].closing if daily else 0,
			"in_sla": in_sla,
			"out_sla": out_sla,
			"sla_pct": sla_pct(in_sla, out_sla),
			"new_cuts": sum(1 for c in cuts if f.from_date <= c.first_day <= f.to_date),
			"closed_cuts": sum(1 for c in cuts if c.closed_day and f.from_date <= c.closed_day <= f.to_date),
			"avg_mttr_hours": round(sum((r.closed - r.received).total_seconds() for r in closed) / len(closed) / 3600, 1)
				if closed else None,
			"sla_hours": setting("sla_hours"),  # 2026-11-28: for the "closed within N hours" caption
		},
		"daily": [{"date": str(d.date), "new": d.new, "closed": d.closed, "pending": d.closing} for d in daily],
		"teams": teams,
		"tat": [{"bucket": b, "count": sum(1 for r in received if r.tat == b)} for b in TAT_BUCKETS + (OPEN,)],
		"outages": [dict(o, month=str(o.month), date=str(o.date)) for o in major_outage(f)],
	}
