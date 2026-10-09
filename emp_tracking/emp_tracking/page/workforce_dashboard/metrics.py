# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""Loads workforce data for one user + filter set and derives every number the dashboards show.

Sources are the standard HRMS / ERPNext doctypes (Employee, Attendance, Employee Checkin,
Leave Application, Leave Allocation, Attendance Request, Task, Project, Expense Claim)
plus this app's GPS tracking (Trip 2, Trip Stop, Location Ping).

Everything is scoped to the employees `access.get_scope` allows, then narrowed by the filters.
Loaders are cached per Dataset, so a dashboard only queries what it actually uses.
"""

import datetime
from collections import defaultdict
from functools import cached_property

import frappe
from frappe.utils import add_days, flt, get_datetime, get_first_day, getdate, now_datetime

from emp_tracking.emp_tracking.page.workforce_dashboard.access import get_scope, team_of

PETROL = "Petrol"
LATE_AFTER = datetime.time(9, 45)  # 09:30 shift start + 15 min grace
OFFICE_START = datetime.time(9, 30)
STANDARD_HOURS = 8
LONG_PENDING_DAYS = 7
SLA_HOURS = {"Urgent": 4, "High": 24, "Medium": 72, "Low": 168}
GPS_MAX_ACCURACY_M = 100
GPS_MAX_GAP_MINUTES = 30
GPS_MAX_SPEED_KMH = 120
EXCESS_KM_TOLERANCE = 1.10  # claimed KM may exceed GPS KM by 10% before it is flagged
LOW_SCORE = 60
MAX_RANGE_DAYS = 366

PERIODS = ("Today", "This Week", "This Month", "Last 30 Days", "Custom")
PRESENT = ("Present", "Half Day", "Work From Home")
OPEN_TASK = ("Pending", "In Progress")
AGE_BUCKETS = ((0, 2, "0-2 days"), (3, 7, "3-7 days"), (8, 15, "8-15 days"), (16, 30, "16-30 days"), (31, None, "30+ days"))
SCORE_WEIGHTS = (("completion_pct", 35), ("on_time_pct", 25), ("attendance_pct", 20), ("productivity_pct", 20))

EMP_FIELDS = [
	"name",
	"employee_name",
	"department",
	"designation",
	"reports_to",
	"user_id",
	"image",
	"cell_number",
	"company",
	"holiday_list",
	"date_of_joining",
	"custom_work_type",
]


def resolve_period(period, from_date=None, to_date=None):
	today = getdate()
	if period == "This Week":
		return add_days(today, -today.weekday()), today
	if period == "This Month":
		return get_first_day(today), today
	if period == "Last 30 Days":
		return add_days(today, -29), today
	if period == "Custom":
		start, end = getdate(from_date or today), getdate(to_date or today)
		if start > end:
			start, end = end, start
		if (end - start).days > MAX_RANGE_DAYS:
			start = add_days(end, -MAX_RANGE_DAYS)
		return start, end
	return today, today


def pct(part, whole):
	return round(100.0 * part / whole, 1) if whole else None


def day_start(d):
	return datetime.datetime.combine(getdate(d), datetime.time.min)


def day_end(d):
	return datetime.datetime.combine(getdate(d), datetime.time(23, 59, 59))


def hours_between(start, end):
	return max((get_datetime(end) - get_datetime(start)).total_seconds() / 3600.0, 0)


class Dataset:
	def __init__(self, filters=None, user=None):
		f = frappe._dict(frappe.parse_json(filters) if isinstance(filters, str) else (filters or {}))
		self.filters = f
		self.user = user or frappe.session.user
		self.period = f.period if f.period in PERIODS else "Today"
		self.start, self.end = resolve_period(self.period, f.from_date, f.to_date)
		self.today = getdate()
		self.now = now_datetime()
		self.category = f.category if f.category in ("Project", "Maintenance") else None
		self.project = f.project or None

		self.level, self.own, scope = get_scope(self.user)
		self.scope = set(scope)
		ids = self._narrow(scope, f)
		self.employees = {
			e.name: e
			for e in frappe.get_all(
				"Employee", filters={"name": ["in", ids]}, fields=EMP_FIELDS, order_by="employee_name asc"
			)
		} if ids else {}
		self.ids = list(self.employees)

	def _narrow(self, scope, f):
		ids = set(scope)
		if f.employee:
			ids &= {f.employee}
		if f.team:
			ids &= {f.team, *team_of(f.team)}
		if f.department and ids:
			ids &= set(
				frappe.get_all("Employee", filters={"department": f.department, "name": ["in", list(ids)]}, pluck="name")
			)
		return list(ids)

	def emp_name(self, emp):
		e = self.employees.get(emp)
		return e.employee_name if e else emp

	def in_scope(self, emp):
		return emp in self.scope

	@cached_property
	def for_today(self):
		"""Live status always reflects today, whatever period is selected."""
		if self.start == self.end == self.today:
			return self
		return Dataset({**self.filters, "period": "Today"}, self.user)

	@cached_property
	def work_type(self):
		"""Field or Office per employee: the Employee's Work Type, else Field if they made GPS trips in the last 30 days."""
		unset = [e for e, row in self.employees.items() if row.custom_work_type not in ("Field", "Office")]
		travelled = set(frappe.get_all(
			"Trip 2",
			filters={"employee": ["in", unset], "start_time": [">=", day_start(add_days(self.today, -30))]},
			pluck="employee",
			distinct=True,
		)) if unset else set()
		return {
			e: row.custom_work_type if row.custom_work_type in ("Field", "Office") else ("Field" if e in travelled else "Office")
			for e, row in self.employees.items()
		}

	# ---- calendar ---------------------------------------------------------

	@cached_property
	def holidays(self):
		company_list, lists = {}, {}
		for e in self.employees.values():
			hl = e.holiday_list
			if not hl and e.company:
				if e.company not in company_list:
					company_list[e.company] = frappe.get_cached_value("Company", e.company, "default_holiday_list")
				hl = company_list[e.company]
			lists[e.name] = hl

		dates = defaultdict(set)
		names = [h for h in set(lists.values()) if h]
		if names:
			for h in frappe.get_all(
				"Holiday",
				filters={"parent": ["in", names], "holiday_date": ["between", [self.start, self.end]]},
				fields=["parent", "holiday_date"],
				parent_doctype="Holiday List",
			):
				dates[h.parent].add(getdate(h.holiday_date))
		return {emp: dates.get(hl, set()) for emp, hl in lists.items()}

	# ---- attendance -------------------------------------------------------

	@cached_property
	def attendance(self):
		if not self.ids:
			return {}
		rows = frappe.get_all(
			"Attendance",
			filters={"employee": ["in", self.ids], "docstatus": 1, "attendance_date": ["between", [self.start, self.end]]},
			fields=["name", "employee", "attendance_date", "status", "working_hours", "late_entry", "in_time", "out_time", "leave_type"],
		)
		return {(r.employee, getdate(r.attendance_date)): r for r in rows}

	@cached_property
	def checkins(self):
		out = defaultdict(list)
		if not self.ids:
			return out
		for r in frappe.get_all(
			"Employee Checkin",
			filters={"employee": ["in", self.ids], "time": ["between", [day_start(self.start), day_end(self.end)]]},
			fields=["name", "employee", "time", "log_type", "custom_work_mode", "latitude", "longitude"],
			order_by="time asc",
		):
			out[(r.employee, getdate(r.time))].append(r)
		return out

	@cached_property
	def leave_apps(self):
		"""Leave applications touching the period, plus every one still awaiting approval."""
		if not self.ids:
			return []
		fields = ["name", "employee", "employee_name", "leave_type", "from_date", "to_date", "total_leave_days",
			"status", "docstatus", "leave_approver", "posting_date", "description"]
		rows = frappe.get_all(
			"Leave Application",
			filters={"employee": ["in", self.ids], "docstatus": ["<", 2], "from_date": ["<=", self.end], "to_date": [">=", self.start]},
			fields=fields,
		)
		rows += frappe.get_all(
			"Leave Application", filters={"employee": ["in", self.ids], "docstatus": 0, "status": "Open"}, fields=fields
		)
		seen, out = set(), []
		for r in rows:
			if r.name not in seen:
				seen.add(r.name)
				out.append(r)
		return out

	@cached_property
	def leave_days(self):
		out = {}
		for la in self.leave_apps:
			if la.docstatus != 1 or la.status != "Approved":
				continue
			d = max(getdate(la.from_date), self.start)
			while d <= min(getdate(la.to_date), self.end):
				out[(la.employee, d)] = la
				d = add_days(d, 1)
		return out

	@cached_property
	def days(self):
		"""One record per employee per day of the period, up to today."""
		out = []
		last = min(self.end, self.today)
		for emp in self.employees.values():
			d = self.start
			if emp.date_of_joining and getdate(emp.date_of_joining) > d:
				d = getdate(emp.date_of_joining)
			while d <= last:
				out.append(self.day(emp.name, d))
				d = add_days(d, 1)
		return out

	def day(self, emp, d):
		e = self.employees[emp]
		att = self.attendance.get((emp, d))
		logs = self.checkins.get((emp, d), [])
		trips = self.trips_by_day.get((emp, d), [])
		ins = [x for x in logs if x.log_type != "OUT"]
		outs = [x for x in logs if x.log_type == "OUT"]
		is_today = d == self.today
		holiday = d in self.holidays.get(emp, ())
		leave = self.leave_days.get((emp, d))

		if att:
			status = att.status
		elif leave:
			status = "On Leave"
		elif logs:
			status = "Present"
		elif holiday:
			status = "Holiday"
		elif is_today:
			status = "Not Checked In"
		else:
			status = "Absent"

		first_in = ins[0].time if ins else (att.in_time if att else None)
		last_out = outs[-1].time if outs else (att.out_time if att else None)
		working = flt(att.working_hours) if att and flt(att.working_hours) else self._log_hours(ins, outs, is_today)
		# Hours are never split within a day: a field employee's whole working time is field hours,
		# an office employee's whole working time is office hours (trips still count for KM and sites).
		mode = self.work_type.get(emp, "Office") if status in PRESENT else ""
		if mode == "Field":
			working = max(working, sum(t.hours for t in trips))
		field = working if mode == "Field" else 0

		return frappe._dict(
			employee=emp,
			employee_name=e.employee_name,
			department=e.department,
			date=d,
			status=status,
			in_time=first_in,
			out_time=last_out,
			working_hours=round(working, 2),
			field_hours=round(field, 2),
			office_hours=round(working if mode == "Office" else 0, 2),
			km=round(sum(flt(t.total_distance_km) for t in trips), 1),
			sites=sum(len(self.stops_by_trip.get(t.name, [])) for t in trips),
			late=bool(att.late_entry) if att else bool(first_in and get_datetime(first_in).time() > LATE_AFTER),
			missing_punch=not is_today and (bool(ins) != bool(outs) or bool(att and att.in_time and not att.out_time)),
			missing=status == "Absent" and not att,
			mode=mode,
			attendance=att.name if att else None,
			leave_type=(att.leave_type if att else None) or (leave.leave_type if leave else None),
			is_today=is_today,
		)

	def _log_hours(self, ins, outs, is_today):
		if not ins:
			return 0
		start = ins[0].time
		end = outs[-1].time if outs and outs[-1].time > start else (self.now if is_today else None)
		return hours_between(start, end) if end else 0

	@cached_property
	def live(self):
		"""Right-now status of each employee: In Field / In Office / Checked Out / On Leave / Not Checked In."""
		ds = self.for_today
		out = {}
		for emp in ds.ids:
			rec = ds.day(emp, ds.today)
			logs = ds.checkins.get((emp, ds.today), [])
			trips = ds.trips_by_day.get((emp, ds.today), [])
			open_trip = next((t for t in trips if not t.end_time), None)
			if rec.status in ("On Leave", "Holiday", "Absent"):
				state = rec.status
			elif open_trip:
				state = "In Field"
			elif logs and logs[-1].log_type != "OUT":
				state = "In Field" if logs[-1].custom_work_mode == "Field" else "In Office"
			elif logs:
				state = "Checked Out"
			else:
				state = "Not Checked In"
			rec.live = state
			rec.open_trip = open_trip.name if open_trip else None
			rec.location = ds.latest_location.get(emp)
			rec.current_task = ds.current_task.get(emp)
			out[emp] = rec
		return out

	# ---- field / GPS ------------------------------------------------------

	@cached_property
	def trips(self):
		if not self.ids:
			return []
		rows = frappe.get_all(
			"Trip 2",
			filters={"employee": ["in", self.ids], "start_time": ["between", [day_start(self.start), day_end(self.end)]]},
			fields=["name", "employee", "vehicle", "start_time", "end_time", "total_distance_km", "total_duration_minutes"],
			order_by="start_time asc",
		)
		for t in rows:
			t.date = getdate(t.start_time)
			if t.end_time:
				t.hours = hours_between(t.start_time, t.end_time)
			elif t.date == self.today:
				t.hours = hours_between(t.start_time, self.now)
			else:
				t.hours = flt(t.total_duration_minutes) / 60.0
			t.employee_name = self.emp_name(t.employee)
		return rows

	@cached_property
	def trips_by_day(self):
		out = defaultdict(list)
		for t in self.trips:
			out[(t.employee, t.date)].append(t)
		return out

	@cached_property
	def stops(self):
		trips = {t.name: t for t in self.trips}
		if not trips:
			return []
		rows = frappe.get_all(
			"Trip Stop",
			filters={"trip": ["in", list(trips)], "stop_type": "halted"},
			fields=["name", "trip", "title", "address", "start_time", "end_time", "duration_minutes", "latitude", "longitude"],
			order_by="start_time asc",
		)
		for s in rows:
			s.employee = trips[s.trip].employee
			s.employee_name = trips[s.trip].employee_name
		return rows

	@cached_property
	def stops_by_trip(self):
		out = defaultdict(list)
		for s in self.stops:
			out[s.trip].append(s)
		return out

	@cached_property
	def pings(self):
		if not self.ids:
			return []
		return frappe.get_all(
			"Location Ping",
			filters={"employee": ["in", self.ids], "timestamp": ["between", [day_start(self.start), day_end(self.end)]]},
			fields=["name", "employee", "trip", "timestamp", "latitude", "longitude", "speed", "accuracy", "battery", "source"],
			order_by="timestamp asc",
			limit_page_length=50000,
		)

	@cached_property
	def latest_location(self):
		out = {}
		for emp in self.ids:
			ping = frappe.get_all(
				"Location Ping",
				filters={"employee": emp},
				fields=["name", "timestamp", "latitude", "longitude", "accuracy", "trip"],
				order_by="timestamp desc",
				limit_page_length=1,
			)
			if ping and ping[0].latitude:
				out[emp] = ping[0]
				continue
			log = frappe.get_all(
				"Employee Checkin",
				filters={"employee": emp, "latitude": ["!=", 0]},
				fields=["name", "time", "latitude", "longitude"],
				order_by="time desc",
				limit_page_length=1,
			)
			if log and log[0].latitude:
				log[0].timestamp = log[0].time
				out[emp] = log[0]
		return out

	@cached_property
	def gps_exceptions(self):
		out = []
		by_emp = defaultdict(list)
		for p in self.pings:
			by_emp[p.employee].append(p)

		def add(p, kind, detail):
			out.append(frappe._dict(
				_doctype="Location Ping", _name=p.name, employee=p.employee, employee_name=self.emp_name(p.employee),
				time=p.timestamp, exception=kind, detail=detail, latitude=p.latitude, longitude=p.longitude, trip=p.trip,
			))

		for pings in by_emp.values():
			prev = None
			for p in pings:
				if flt(p.accuracy) > GPS_MAX_ACCURACY_M:
					add(p, "Low GPS accuracy", f"Accuracy ±{int(flt(p.accuracy))} m")
				if flt(p.speed) * 3.6 > GPS_MAX_SPEED_KMH:
					add(p, "Unrealistic speed", f"{int(flt(p.speed) * 3.6)} km/h")
				if p.source == "manual":
					add(p, "Manual location", "Location entered manually")
				if prev and prev.trip and prev.trip == p.trip:
					gap = (get_datetime(p.timestamp) - get_datetime(prev.timestamp)).total_seconds() / 60
					if gap > GPS_MAX_GAP_MINUTES:
						add(p, "GPS signal gap", f"No location for {int(gap)} min")
				prev = p
		out.sort(key=lambda r: r.time, reverse=True)
		return out

	def movement(self, emp):
		"""Today's GPS path for the map."""
		return [[p.latitude, p.longitude] for p in self.for_today.pings if p.employee == emp and p.latitude]

	# ---- tasks ------------------------------------------------------------

	@cached_property
	def all_tasks(self):
		if not self.ids:
			return []
		filters = [["custom_assigned_to", "in", self.ids], ["is_template", "=", 0], ["status", "not in", ["Cancelled", "Template"]]]
		if self.project:
			filters.append(["project", "=", self.project])
		if self.category:
			filters.append(["custom_work_category", "=", self.category])
		rows = frappe.get_all(
			"Task",
			filters=filters,
			or_filters=[["status", "!=", "Completed"], ["completed_on", ">=", self.start]],
			fields=["name", "subject", "status", "priority", "project", "exp_start_date", "exp_end_date", "completed_on",
				"custom_assigned_to", "custom_work_category", "custom_site", "progress", "creation", "issue",
				"custom_service_request"],
			order_by="exp_end_date asc",
		)
		titles = {}
		projects = {r.project for r in rows if r.project}
		if projects:
			titles = dict(frappe.get_all("Project", filters={"name": ["in", list(projects)]}, fields=["name", "project_name"], as_list=True))

		for t in rows:
			t.employee = t.custom_assigned_to
			t.employee_name = self.emp_name(t.employee)
			t.project_name = titles.get(t.project) or t.project
			t.category = t.custom_work_category or ("Project" if t.project else "Maintenance")
			t.bucket = "Completed" if t.status == "Completed" else ("In Progress" if t.status in ("Working", "Pending Review") else "Pending")
			t.started = get_datetime(t.exp_start_date or t.creation)
			t.due = get_datetime(t.exp_end_date) if t.exp_end_date else None
			done = getdate(t.completed_on) if t.completed_on else self.today
			t.is_open = t.bucket in OPEN_TASK
			t.delayed = bool(t.is_open and t.due and t.due < self.now)
			t.completed_late = bool(t.bucket == "Completed" and t.due and done > t.due.date())
			t.on_time = t.bucket == "Completed" and not t.completed_late
			t.age_days = max(((self.today if t.is_open else done) - t.started.date()).days, 0)
			sla_due = t.started + datetime.timedelta(hours=SLA_HOURS.get(t.priority, 72))
			t.sla_breached = bool((t.is_open and self.now > sla_due) or (not t.is_open and done > sla_due.date()))
			t.long_pending = t.is_open and t.age_days > LONG_PENDING_DAYS
		return rows

	@cached_property
	def tasks(self):
		"""Tasks active in the period: started by its end and not completed before its start."""
		end = day_end(self.end)
		return [t for t in self.all_tasks if t.started <= end]

	@cached_property
	def current_task(self):
		"""The task each employee is most likely on now: in progress first, then the earliest due open task."""
		out = {}
		for t in sorted(self.all_tasks, key=lambda t: (t.bucket != "In Progress", t.due or datetime.datetime.max)):
			if t.is_open and t.employee not in out:
				out[t.employee] = t
		return out

	# ---- leave ------------------------------------------------------------

	@cached_property
	def leave_balances(self):
		if not self.ids:
			return []
		allocations = frappe.get_all(
			"Leave Allocation",
			filters={"employee": ["in", self.ids], "docstatus": 1, "from_date": ["<=", self.today], "to_date": [">=", self.today]},
			fields=["employee", "leave_type", "from_date", "to_date", "total_leaves_allocated"],
		)
		if not allocations:
			return []
		apps = frappe.get_all(
			"Leave Application",
			filters={"employee": ["in", self.ids], "docstatus": ["<", 2], "status": ["in", ["Approved", "Open"]],
				"from_date": [">=", min(a.from_date for a in allocations)]},
			fields=["employee", "leave_type", "from_date", "total_leave_days", "status", "docstatus"],
		)
		out = []
		for a in allocations:
			mine = [x for x in apps if x.employee == a.employee and x.leave_type == a.leave_type
				and getdate(a.from_date) <= getdate(x.from_date) <= getdate(a.to_date)]
			taken = sum(flt(x.total_leave_days) for x in mine if x.docstatus == 1 and x.status == "Approved")
			pending = sum(flt(x.total_leave_days) for x in mine if x.docstatus == 0 and x.status == "Open")
			out.append(frappe._dict(
				_doctype="Employee", _name=a.employee, employee=a.employee, employee_name=self.emp_name(a.employee),
				leave_type=a.leave_type, allocated=flt(a.total_leaves_allocated), taken=taken, pending=pending,
				balance=flt(a.total_leaves_allocated) - taken,
			))
		out.sort(key=lambda r: (r.employee_name, r.leave_type))
		return out

	@cached_property
	def regularizations(self):
		if not self.ids:
			return []
		fields = ["name", "employee", "employee_name", "from_date", "to_date", "reason", "explanation", "docstatus", "creation"]
		rows = frappe.get_all("Attendance Request", filters={"employee": ["in", self.ids], "docstatus": 0}, fields=fields)
		rows += frappe.get_all(
			"Attendance Request",
			filters={"employee": ["in", self.ids], "docstatus": 1, "from_date": ["<=", self.end], "to_date": [">=", self.start]},
			fields=fields,
		)
		for r in rows:
			r.state = "Pending" if r.docstatus == 0 else "Approved"
		return sorted(rows, key=lambda r: r.from_date, reverse=True)

	# ---- petrol claims ----------------------------------------------------

	CLAIM_FIELDS = ["name", "employee", "employee_name", "posting_date", "approval_status", "status", "docstatus",
		"total_claimed_amount", "total_sanctioned_amount", "custom_claim_from", "custom_claim_to", "custom_claimed_km",
		"custom_gps_km", "custom_eligible_km", "custom_km_source", "custom_rate_per_km", "expense_approver"]

	def _claims(self, filters):
		if not self.ids:
			return []
		rows = frappe.get_all(
			"Expense Claim",
			filters=[["employee", "in", self.ids], ["docstatus", "<", 2], ["Expense Claim Detail", "expense_type", "=", PETROL], *filters],
			fields=self.CLAIM_FIELDS,
			order_by="posting_date desc",
		)
		seen, out = set(), []
		for c in rows:
			if c.name in seen:
				continue
			seen.add(c.name)
			c.state = "Rejected" if c.approval_status == "Rejected" else ("Approved" if c.approval_status == "Approved" else "Pending")
			c.excessive = c.custom_km_source == "Manual" or flt(c.custom_claimed_km) > flt(c.custom_gps_km) * EXCESS_KM_TOLERANCE
			c.extra_km = round(max(flt(c.custom_claimed_km) - flt(c.custom_gps_km), 0), 1)
			c.team = self.team_label(c.employee)
			out.append(c)
		return out

	@cached_property
	def claims(self):
		return self._claims([["posting_date", "between", [self.start, self.end]]])

	@cached_property
	def pending_claims(self):
		return self._claims([["docstatus", "=", 0], ["approval_status", "=", "Draft"]])

	# ---- approvals --------------------------------------------------------

	@cached_property
	def approvals(self):
		out = []
		for la in self.leave_apps:
			if la.docstatus == 0 and la.status == "Open":
				out.append(frappe._dict(
					_doctype="Leave Application", _name=la.name, employee=la.employee, employee_name=la.employee_name,
					request="Leave", detail=f"{la.leave_type} · {flt(la.total_leave_days):g} day(s)",
					date=la.from_date, amount=None, raised_on=la.posting_date,
				))
		for c in self.pending_claims:
			out.append(frappe._dict(
				_doctype="Expense Claim", _name=c.name, employee=c.employee, employee_name=c.employee_name,
				request="Petrol Claim", detail=f"{flt(c.custom_claimed_km):g} km claimed · {flt(c.custom_gps_km):g} km GPS",
				date=c.custom_claim_from or c.posting_date, amount=c.total_claimed_amount, raised_on=c.posting_date,
			))
		for r in self.regularizations:
			if r.docstatus == 0:
				out.append(frappe._dict(
					_doctype="Attendance Request", _name=r.name, employee=r.employee, employee_name=r.employee_name,
					request="Regularization", detail=f"{r.reason}: {r.explanation or ''}".strip(" :"),
					date=r.from_date, amount=None, raised_on=getdate(r.creation),
				))
		out.sort(key=lambda r: getdate(r.raised_on or r.date))
		for r in out:
			r.waiting_days = (self.today - getdate(r.raised_on or r.date)).days
		return out

	# ---- performance ------------------------------------------------------

	def team_label(self, emp):
		e = self.employees.get(emp)
		if not e:
			return "-"
		if e.reports_to:
			return self.emp_name(e.reports_to) if e.reports_to in self.employees else frappe.db.get_value("Employee", e.reports_to, "employee_name")
		return e.employee_name if any(x.reports_to == emp for x in self.employees.values()) else "Unassigned"

	@cached_property
	def performance(self):
		days, tasks = defaultdict(list), defaultdict(list)
		for d in self.days:
			days[d.employee].append(d)
		for t in self.tasks:
			tasks[t.employee].append(t)

		out = []
		for emp in self.ids:
			e = self.employees[emp]
			row = summarize(days[emp], tasks[emp], self.today, self.now)
			row.update(
				_doctype="Employee", _name=emp, employee=emp, employee_name=e.employee_name, designation=e.designation,
				department=e.department, team=self.team_label(emp),
			)
			out.append(row)
		return out

	def group_performance(self, key):
		groups = defaultdict(list)
		for row in self.performance:
			groups[row[key] or "Unassigned"].append(row)
		out = []
		for label, rows in sorted(groups.items()):
			agg = frappe._dict(label=label, employees=len(rows))
			for f in ("assigned", "completed", "on_time", "working_hours", "field_hours", "office_hours", "km", "present", "expected_days", "expected_hours"):
				agg[f] = round(sum(flt(r[f]) for r in rows), 2)
			finish(agg)
			out.append(agg)
		return out

	@cached_property
	def low_performers(self):
		return [r for r in self.performance if r.score is not None and r.score < LOW_SCORE]

	# ---- exceptions -------------------------------------------------------

	@cached_property
	def exceptions(self):
		out = []

		def add(category, severity, title, detail, employee_name, when, doctype, name):
			out.append(frappe._dict(
				category=category, severity=severity, title=title, detail=detail, employee_name=employee_name,
				when=when, _doctype=doctype, _name=name,
			))

		for t in self.all_tasks:
			if t.delayed:
				add("overdue", "High", t.subject, f"Due {frappe.format(t.due, 'Datetime')} · {t.priority}", t.employee_name, t.due, "Task", t.name)
			if t.is_open and t.sla_breached:
				add("sla", "High" if t.priority in ("Urgent", "High") else "Medium", t.subject,
					f"{t.priority} priority · SLA {SLA_HOURS.get(t.priority, 72)} h · open {t.age_days} day(s)", t.employee_name, t.started, "Task", t.name)
			if t.long_pending:
				add("long_pending", "Medium", t.subject, f"Open for {t.age_days} days", t.employee_name, t.started, "Task", t.name)
		for d in self.days:
			if d.missing:
				add("missing_attendance", "High", "No attendance", f"{frappe.format(d.date, 'Date')}: no check-in, attendance or leave",
					d.employee_name, d.date, "Employee", d.employee)
			elif d.missing_punch:
				add("missing_attendance", "Medium", "Missing punch", f"{frappe.format(d.date, 'Date')}: check-in without check-out",
					d.employee_name, d.date, "Attendance" if d.attendance else "Employee", d.attendance or d.employee)
		for g in self.gps_exceptions:
			add("gps", "Medium", g.exception, g.detail, g.employee_name, g.time, g._doctype, g._name)
		seen = set()
		for c in self.claims + self.pending_claims:
			if c.excessive and c.name not in seen:
				seen.add(c.name)
				src = "Manual KM" if c.custom_km_source == "Manual" else "Excess KM"
				add("excess_km", "High" if c.state == "Pending" else "Low", src,
					f"Claimed {flt(c.custom_claimed_km):g} km vs GPS {flt(c.custom_gps_km):g} km (+{c.extra_km:g}) · {c.state}",
					c.employee_name, c.posting_date, "Expense Claim", c.name)
		for a in self.approvals:
			add("approvals", "High" if a.waiting_days > 2 else "Low", f"{a.request} awaiting approval",
				f"{a.detail} · waiting {a.waiting_days} day(s)", a.employee_name, a.raised_on, a._doctype, a._name)
		for p in self.low_performers:
			add("low_productivity", "Medium", "Low productivity", f"Score {p.score} · completion {fmt_pct(p.completion_pct)} · hours {p.working_hours:g}/{p.expected_hours:g}",
				p.employee_name, None, "Employee", p.employee)
		return out

	# ---- trends -----------------------------------------------------------

	def daily_trend(self):
		by_date = defaultdict(lambda: defaultdict(int))
		for d in self.days:
			b = by_date[d.date]
			if d.status in PRESENT:
				b["present"] += 1
			elif d.status == "On Leave":
				b["leave"] += 1
			elif d.status in ("Absent", "Not Checked In"):
				b["absent"] += 1
			if d.late:
				b["late"] += 1
			b["hours"] += d.working_hours
			b["km"] += d.km
		return [(dt, by_date[dt]) for dt in sorted(by_date)]

	def monthly_attendance(self, months=6):
		if not self.ids:
			return []
		year, month = self.today.year, self.today.month - (months - 1)
		while month <= 0:
			month += 12
			year -= 1
		start = datetime.date(year, month, 1)
		rows = frappe.get_all(
			"Attendance",
			filters={"employee": ["in", self.ids], "docstatus": 1, "attendance_date": [">=", start]},
			fields=["attendance_date", "status"],
		)
		by_month = defaultdict(lambda: [0, 0])
		for r in rows:
			key = getdate(r.attendance_date).strftime("%Y-%m")
			if r.status == "On Leave":
				continue
			by_month[key][1] += 1
			if r.status in PRESENT:
				by_month[key][0] += 0.5 if r.status == "Half Day" else 1
		return [(k, pct(v[0], v[1])) for k, v in sorted(by_month.items())]


def summarize(days, tasks, today, now):
	"""Attendance, hours and task numbers for one employee over the period."""
	worked = [d for d in days if d.status != "Holiday"]
	leave = sum(1 for d in worked if d.status == "On Leave")
	present = sum(0.5 if d.status == "Half Day" else 1 for d in worked if d.status in PRESENT)
	expected_days = max(len(worked) - leave, 0)

	# Today only counts the hours that could have been worked so far.
	expected_hours = 0.0
	for d in worked:
		if d.status == "On Leave":
			continue
		if d.is_today:
			since = hours_between(datetime.datetime.combine(today, OFFICE_START), now)
			expected_hours += min(STANDARD_HOURS, since)
		else:
			expected_hours += STANDARD_HOURS

	completed = [t for t in tasks if t.bucket == "Completed"]
	row = frappe._dict(
		assigned=len(tasks),
		completed=len(completed),
		in_progress=sum(1 for t in tasks if t.bucket == "In Progress"),
		pending=sum(1 for t in tasks if t.bucket == "Pending"),
		delayed=sum(1 for t in tasks if t.delayed),
		on_time=sum(1 for t in completed if t.on_time),
		working_hours=round(sum(d.working_hours for d in days), 2),
		field_hours=round(sum(d.field_hours for d in days), 2),
		office_hours=round(sum(d.office_hours for d in days), 2),
		km=round(sum(d.km for d in days), 1),
		present=present,
		absent=sum(1 for d in worked if d.status == "Absent"),
		leave=leave,
		late=sum(1 for d in days if d.late),
		missing_punch=sum(1 for d in days if d.missing_punch),
		expected_days=expected_days,
		expected_hours=round(expected_hours, 1),
	)
	finish(row)
	return row


def finish(row):
	row.completion_pct = pct(row.completed, row.assigned)
	row.on_time_pct = pct(row.on_time, row.completed)
	row.attendance_pct = pct(row.present, row.expected_days)
	row.productivity_pct = pct(row.working_hours, row.expected_hours)
	parts = [(min(row[k], 100), w) for k, w in SCORE_WEIGHTS if row[k] is not None]
	row.score = round(sum(v * w for v, w in parts) / sum(w for _, w in parts)) if parts else None


def fmt_pct(v):
	return "-" if v is None else f"{v:g}%"


def age_bucket(days):
	for lo, hi, label in AGE_BUCKETS:
		if days >= lo and (hi is None or days <= hi):
			return label
	return AGE_BUCKETS[-1][2]
