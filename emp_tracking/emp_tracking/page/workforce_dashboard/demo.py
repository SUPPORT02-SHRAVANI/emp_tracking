# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""Dummy data for trying the Workforce Dashboards: 4 employees and 30 days of history.

	bench --site newsite.local execute emp_tracking.emp_tracking.page.workforce_dashboard.demo.create
	bench --site newsite.local execute emp_tracking.emp_tracking.page.workforce_dashboard.demo.delete

Everything is built through the standard HRMS / ERPNext doctypes (with their validations),
so the dashboards read it exactly as they would read real data. Every demo login uses the
@demo.local domain, which is also how `delete` finds what to remove.
"""

import datetime
import math
import random

import frappe
from frappe.desk.form.assign_to import _add as add_assignment
from frappe.utils import add_days, getdate, now_datetime
from frappe.utils.password import update_password

from emp_tracking.emp_tracking.page.workforce_dashboard.metrics import PETROL
from emp_tracking.emp_tracking.page.workforce_dashboard.setup import apply_access

DOMAIN = "demo.local"
PASSWORD = "Demo@1234"
HOLIDAY_LIST = "Workforce Demo Holidays"
RATE_PER_KM = 3.5
DAYS_BACK = 30
SEED = 42

# Two employees work in the field every day, the lead goes out on Wednesdays, the coordinator stays in office.
EMPLOYEES = [
	{"key": "amit", "first_name": "Amit", "last_name": "Sharma", "gender": "Male", "designation": "Team Lead", "work_type": "Office",
		"department": "Field Operations", "field_days": (2,), "base": "Kurla Office", "late_odds": 0.1,
		"roles": ["Employee", "Team Lead", "Leave Approver", "Expense Approver", "Projects User"]},
	{"key": "priya", "first_name": "Priya", "last_name": "Patil", "gender": "Female", "designation": "Field Engineer", "work_type": "Field",
		"department": "Field Operations", "field_days": (0, 1, 2, 3, 4, 5), "base": "Kurla Office", "late_odds": 0.15,
		"roles": ["Employee"], "reports_to": "amit"},
	{"key": "rohan", "first_name": "Rohan", "last_name": "Desai", "gender": "Male", "designation": "Field Engineer", "work_type": "Field",
		"department": "Field Operations", "field_days": (0, 1, 2, 3, 4, 5), "base": "Vashi Hub", "late_odds": 0.25,
		"roles": ["Employee"], "reports_to": "amit"},
	{"key": "sneha", "first_name": "Sneha", "last_name": "Kulkarni", "gender": "Female", "designation": "Office Coordinator", "work_type": "Office",
		"department": "Operations Support", "field_days": (), "base": "Kurla Office", "late_odds": 0.35,
		"roles": ["Employee"], "reports_to": "amit"},
]
# Logins without an Employee record.
OTHER_USERS = [
	{"key": "hr", "first_name": "Kavita", "last_name": "Joshi", "roles": ["HR Manager", "HR User", "Leave Approver"]},
	{"key": "finance", "first_name": "Rahul", "last_name": "Mehta", "roles": ["Finance Manager", "Accounts User", "Expense Approver"]},
	{"key": "management", "first_name": "Sanjay", "last_name": "Kapoor", "roles": ["Management", "Projects User"]},
]

PLACES = {
	"Kurla Office": (19.0700, 72.8800),
	"Vashi Hub": (19.0745, 72.9978),
	"Andheri POP": (19.1197, 72.8468),
	"Powai Cluster B": (19.1176, 72.9060),
	"Vikhroli East": (19.1110, 72.9280),
	"LBS Road Ch. 12": (19.0900, 72.9000),
	"Ghatkopar Ring": (19.0860, 72.9081),
	"Kurla West": (19.0726, 72.8826),
	"Chembur Exchange": (19.0522, 72.9005),
	"Vashi Sector 17": (19.0771, 72.9986),
	"Nerul Site 4": (19.0330, 73.0297),
	"CBD Belapur": (19.0235, 73.0400),
	"Airoli Site 2": (19.1590, 72.9986),
	"Sanpada": (19.0618, 73.0133),
	"Kharghar Sec 20": (19.0330, 73.0700),
	"Ghansoli Node": (19.1222, 73.0068),
}
SITES = {
	"Kurla Office": ["Andheri POP", "Powai Cluster B", "Vikhroli East", "LBS Road Ch. 12", "Ghatkopar Ring", "Kurla West", "Chembur Exchange"],
	"Vashi Hub": ["Vashi Sector 17", "Nerul Site 4", "CBD Belapur", "Airoli Site 2", "Sanpada", "Kharghar Sec 20", "Ghansoli Node"],
}

PROJECTS = {"ftth": "FTTH Rollout - Phase 2", "tower": "Tower Upgrade - Navi Mumbai"}

# (employee, subject, category, project, site, priority, start offset days, due offset days, outcome)
TASKS = [
	("priya", "Splice fibre at Andheri POP", "Maintenance", None, "Andheri POP", "High", -20, -18, "on_time"),
	("priya", "ONT installation - Powai cluster", "Project", "ftth", "Powai Cluster B", "Medium", -15, -10, "late"),
	("priya", "Route survey - Vikhroli", "Project", "ftth", "Vikhroli East", "Medium", -6, -2, "overdue"),
	("priya", "Fibre cut restoration - LBS Road", "Maintenance", None, "LBS Road Ch. 12", "Urgent", 0, 0, "working"),
	("priya", "OTDR testing - Ghatkopar ring", "Maintenance", None, "Ghatkopar Ring", "Low", -3, 2, "open"),
	("priya", "Splice closure audit - Kurla", "Maintenance", None, "Kurla West", "Medium", -9, -7, "on_time"),
	("rohan", "Tower power backup check - Vashi", "Maintenance", None, "Vashi Sector 17", "High", -12, -10, "late"),
	("rohan", "Antenna alignment - Nerul", "Project", "tower", "Nerul Site 4", "Medium", -14, -4, "overdue"),
	("rohan", "Battery bank replacement - Belapur", "Project", "tower", "CBD Belapur", "High", -5, 1, "working"),
	("rohan", "Preventive maintenance - Airoli", "Maintenance", None, "Airoli Site 2", "Medium", -2, 3, "open"),
	("rohan", "Fibre patch - Sanpada", "Maintenance", None, "Sanpada", "Urgent", -1, -0.5, "overdue"),
	("rohan", "Site survey - Kharghar", "Project", "tower", "Kharghar Sec 20", "Low", -25, -20, "on_time"),
	("sneha", "Update asset register for September", "Project", "ftth", "Head Office", "Medium", -10, -5, "on_time"),
	("sneha", "Vendor invoice reconciliation", "Maintenance", None, "Head Office", "High", -4, -1, "overdue"),
	("sneha", "Prepare weekly MIS report", "Project", "ftth", "Head Office", "Medium", -1, 1, "working"),
	("sneha", "Schedule PM visits for October", "Maintenance", None, "Head Office", "Low", -2, 4, "open"),
	("amit", "Review splice quality reports", "Project", "ftth", "Head Office", "Medium", -8, -6, "on_time"),
	("amit", "Vendor coordination - Navi Mumbai", "Project", "tower", "Vashi", "High", -3, 2, "working"),
	("amit", "Team safety audit", "Maintenance", None, "Field Ops", "Medium", -16, -12, "late"),
]


def email(key):
	return f"{key}@{DOMAIN}"


@frappe.whitelist(methods=["POST"])
def create(reset=0):
	frappe.only_for("System Manager")
	if frappe.db.exists("Employee", {"user_id": email("priya")}):
		if not int(reset):
			return "Demo data already exists. Run demo.delete first, or create with reset=1."
		delete()

	frappe.flags.mute_emails = True
	builder = DemoBuilder()
	builder.run()
	apply_access()
	frappe.db.commit()  # nosemgrep: also runs from the browser, nothing else commits for us
	frappe.flags.mute_emails = False
	return builder.report()


class DemoBuilder:
	def __init__(self):
		self.rng = random.Random(SEED)
		self.today = getdate()
		self.now = now_datetime()
		self.company = default_company()
		self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
		self.emp = {}
		self.trips = []  # (employee key, date, km)
		self.counts = {}
		self.errors = []

	# ---- helpers ----------------------------------------------------------

	def save(self, label, doc, submit=False):
		"""Insert (and submit) one document; on failure note it and carry on with the rest."""
		frappe.db.savepoint("demo_doc")
		try:
			doc.flags.ignore_permissions = True
			doc.insert()
			if submit:
				doc.submit()
			self.counts[label] = self.counts.get(label, 0) + 1
			return doc
		except Exception as e:
			frappe.db.rollback(save_point="demo_doc")
			frappe.clear_messages()
			self.errors.append(f"{label}: {e}")
			return None

	def at(self, d, h, m=0):
		return datetime.datetime.combine(d, datetime.time(h, m))

	def report(self):
		lines = ["Demo data created:"] + [f"  {k}: {v}" for k, v in sorted(self.counts.items())]
		lines += ["", "Logins (password: " + PASSWORD + "):"]
		lines += [f"  {email(e['key'])}  - {e['designation']}" for e in EMPLOYEES]
		lines += [f"  {email(u['key'])}  - {', '.join(u['roles'][:1])}" for u in OTHER_USERS]
		if self.errors:
			lines += ["", f"Skipped {len(self.errors)} record(s):"] + [f"  {x}" for x in self.errors[:30]]
		return "\n".join(lines)

	# ---- steps ------------------------------------------------------------

	def run(self):
		self.masters()
		self.people()
		self.plan_days()
		self.leaves()
		self.attendance_and_field()
		self.regularizations()
		self.tasks()
		self.claims()

	def masters(self):
		for g in ("Male", "Female"):
			if not frappe.db.exists("Gender", g):
				frappe.get_doc({"doctype": "Gender", "gender": g}).insert(ignore_permissions=True)
		for d in {e["designation"] for e in EMPLOYEES}:
			if not frappe.db.exists("Designation", d):
				frappe.get_doc({"doctype": "Designation", "designation_name": d}).insert(ignore_permissions=True)

		self.departments = {}
		for name in {e["department"] for e in EMPLOYEES}:
			existing = frappe.db.get_value("Department", {"department_name": name, "company": self.company})
			self.departments[name] = existing or frappe.get_doc(
				{"doctype": "Department", "department_name": name, "company": self.company}
			).insert(ignore_permissions=True).name

		if not frappe.db.exists("Holiday List", HOLIDAY_LIST):
			year = self.today.year
			hl = frappe.get_doc({
				"doctype": "Holiday List",
				"holiday_list_name": HOLIDAY_LIST,
				"from_date": datetime.date(year, 1, 1),
				"to_date": datetime.date(year, 12, 31),
			})
			d = datetime.date(year, 1, 1)
			while d.year == year:
				if d.weekday() == 6:
					hl.append("holidays", {"holiday_date": d, "description": "Sunday", "weekly_off": 1})
				d += datetime.timedelta(days=1)
			for day, label in ((datetime.date(year, 9, 14), "Ganesh Chaturthi"), (datetime.date(year, 10, 2), "Gandhi Jayanti")):
				if day.weekday() != 6:
					hl.append("holidays", {"holiday_date": day, "description": label})
			hl.insert(ignore_permissions=True)
		self.holidays = set(frappe.get_all("Holiday", filters={"parent": HOLIDAY_LIST}, pluck="holiday_date", parent_doctype="Holiday List"))
		self.holidays = {getdate(d) for d in self.holidays}

		for lt, days in (("Casual Leave", 12), ("Sick Leave", 8)):
			if not frappe.db.exists("Leave Type", lt):
				frappe.get_doc({"doctype": "Leave Type", "leave_type_name": lt, "max_leaves_allowed": days}).insert(ignore_permissions=True)

		account = frappe.db.get_value(
			"Account", {"company": self.company, "is_group": 0, "root_type": "Expense", "account_name": ["like", "%Travel%"]}
		) or frappe.db.get_value("Account", {"company": self.company, "is_group": 0, "root_type": "Expense"})
		ect = frappe.get_doc("Expense Claim Type", PETROL) if frappe.db.exists("Expense Claim Type", PETROL) else frappe.get_doc(
			{"doctype": "Expense Claim Type", "expense_type": PETROL, "description": "Fuel reimbursement for field travel, paid per KM"}
		)
		if account and not any(a.company == self.company for a in ect.get("accounts", [])):
			ect.append("accounts", {"company": self.company, "default_account": account})
		ect.save(ignore_permissions=True) if not ect.is_new() else ect.insert(ignore_permissions=True)

		self.projects = {}
		for key, title in PROJECTS.items():
			existing = frappe.db.get_value("Project", {"project_name": title})
			self.projects[key] = existing or frappe.get_doc({
				"doctype": "Project",
				"project_name": title,
				"company": self.company,
				"status": "Open",
				"expected_start_date": add_days(self.today, -90),
				"expected_end_date": add_days(self.today, 120),
			}).insert(ignore_permissions=True).name

	def people(self):
		for u in OTHER_USERS:
			make_user(email(u["key"]), u["first_name"], u["last_name"], u["roles"])

		for i, p in enumerate(EMPLOYEES):
			make_user(email(p["key"]), p["first_name"], p["last_name"], p["roles"])
			doc = frappe.get_doc({
				"doctype": "Employee",
				"first_name": p["first_name"],
				"last_name": p["last_name"],
				"gender": p["gender"],
				"date_of_birth": datetime.date(1990 + i, 3 + i, 10 + i),
				"date_of_joining": datetime.date(self.today.year - 2, 4, 1),
				"status": "Active",
				"company": self.company,
				"department": self.departments[p["department"]],
				"designation": p["designation"],
				"custom_work_type": p["work_type"],
				"user_id": email(p["key"]),
				"holiday_list": HOLIDAY_LIST,
				"cell_number": f"98200 1100{i + 1}",
				"company_email": email(p["key"]),
				# The lead must see the whole team's records in the desk too, so no self-only restriction.
				"create_user_permission": 0 if p["key"] == "amit" else 1,
			})
			doc.insert(ignore_permissions=True)
			self.emp[p["key"]] = doc.name
			self.counts["Employee"] = self.counts.get("Employee", 0) + 1

		for p in EMPLOYEES:
			lead = p.get("reports_to")
			approver = email(lead) if lead else email("hr")
			values = {"reports_to": self.emp[lead] if lead else None, "leave_approver": approver,
				"expense_approver": email(lead) if lead else email("finance")}
			frappe.db.set_value("Employee", self.emp[p["key"]], values)

		for key in self.emp:
			for lt, days in (("Casual Leave", 12), ("Sick Leave", 8)):
				self.save("Leave Allocation", frappe.get_doc({
					"doctype": "Leave Allocation",
					"employee": self.emp[key],
					"leave_type": lt,
					"company": self.company,
					"from_date": datetime.date(self.today.year, 1, 1),
					"to_date": datetime.date(self.today.year, 12, 31),
					"new_leaves_allocated": days,
				}), submit=True)

		for key in ("amit", "priya", "rohan"):
			self.save("Vehicles", frappe.get_doc({
				"doctype": "Vehicles",
				"employee": self.emp[key],
				"vehicle_number": {"amit": "MH-01-EF-9012", "priya": "MH-02-AB-1234", "rohan": "MH-43-CD-5678"}[key],
				"mileage_kmpl": 45,
				"fuel_price_per_liter": 105,
			}))
		self.vehicles = dict(frappe.get_all("Vehicles", filters={"employee": ["in", list(self.emp.values())]}, fields=["employee", "name"], as_list=True))

	def plan_days(self):
		"""Decide what each person did each day; special days create the exceptions the dashboards should catch."""
		days = [add_days(self.today, -n) for n in range(DAYS_BACK, 0, -1)]
		self.workdays = [d for d in days if d not in self.holidays]
		wd = list(reversed(self.workdays))  # wd[0] = most recent working day before today
		self.wd = wd

		self.plan = {}
		for p in EMPLOYEES:
			plan = {d: ("field" if d.weekday() in p["field_days"] else "office") for d in self.workdays}
			self.plan[p["key"]] = plan

		self.plan["rohan"][wd[2]] = "missing_punch"
		self.plan["rohan"][wd[5]] = "leave"
		self.plan["rohan"][wd[6]] = "leave"
		self.plan["rohan"][wd[9]] = "missing"
		self.plan["priya"][wd[8]] = "regularized"
		self.plan["priya"][wd[12]] = "absent"

	def leaves(self):
		wd = self.wd

		def apply(key, leave_type, start, end, status, reason, approver_key="amit"):
			doc = frappe.get_doc({
				"doctype": "Leave Application",
				"employee": self.emp[key],
				"leave_type": leave_type,
				"from_date": start,
				"to_date": end,
				"posting_date": min(add_days(start, -2), self.today),
				"status": status,
				"description": reason,
				"leave_approver": email(approver_key),
				"company": self.company,
			})
			self.save(f"Leave Application ({status})", doc, submit=status != "Open")

		apply("rohan", "Casual Leave", min(wd[5], wd[6]), max(wd[5], wd[6]), "Approved", "Family function")
		apply("sneha", "Casual Leave", wd[15], wd[15], "Rejected", "Personal work")
		if self.today not in self.holidays:
			apply("sneha", "Sick Leave", self.today, self.today, "Approved", "Fever")
		apply("priya", "Casual Leave", next_workday(add_days(self.today, 5), self.holidays), next_workday(add_days(self.today, 5), self.holidays), "Open", "Sister's wedding")
		apply("amit", "Casual Leave", next_workday(add_days(self.today, 10), self.holidays), next_workday(add_days(self.today, 11), self.holidays), "Open", "Vacation", approver_key="hr")

	def attendance_and_field(self):
		for p in EMPLOYEES:
			key = p["key"]
			for d in self.workdays:
				kind = self.plan[key][d]
				if kind in ("leave", "missing", "regularized"):
					continue
				if kind == "absent":
					self.save("Attendance", frappe.get_doc({
						"doctype": "Attendance", "employee": self.emp[key], "attendance_date": d, "status": "Absent", "company": self.company,
					}), submit=True)
					continue
				self.work_day(p, d, kind)
			self.today_activity(p)

	def work_day(self, p, d, kind):
		key, rng = p["key"], self.rng
		base = PLACES[p["base"]]
		field = kind == "field" or (kind == "missing_punch" and d.weekday() in p["field_days"])
		mode = "Field" if field else "Office"

		late = rng.random() < p["late_odds"]
		in_t = self.at(d, 9, rng.randint(46, 59)) if late else self.at(d, 9, rng.randint(0, 28))
		out_t = self.at(d, 18, rng.randint(0, 45)) if not field else self.at(d, 18, rng.randint(20, 59))

		self.checkin(key, in_t, "IN", mode, base)
		if kind != "missing_punch":
			self.checkin(key, out_t, "OUT", mode, base)
			self.save("Attendance", frappe.get_doc({
				"doctype": "Attendance",
				"employee": self.emp[key],
				"attendance_date": d,
				"status": "Present",
				"company": self.company,
				"in_time": in_t,
				"out_time": out_t,
				"working_hours": round((out_t - in_t).total_seconds() / 3600, 2),
				"late_entry": 1 if in_t.time() > datetime.time(9, 45) else 0,
			}), submit=True)

		if field:
			sites = SITES[p["base"]]
			first = in_t + datetime.timedelta(minutes=rng.randint(30, 50))
			end1 = self.trip(p, first, rng.sample(sites, 2), gap=(key == "rohan" and d == self.wd[3]),
				speed_spike=(key == "priya" and d == self.wd[4]), manual=(key == "rohan" and d == self.wd[7]))
			if p["key"] != "amit":
				second = max(end1, self.at(d, 14, 0)) + datetime.timedelta(minutes=rng.randint(15, 40))
				self.trip(p, second, rng.sample(sites, 2))

	def today_activity(self, p):
		"""Live picture for today: the coordinator is on sick leave, the others are checked in, field staff mid-trip."""
		key, d = p["key"], self.today
		if d in self.holidays or key == "sneha":
			return
		start = min(self.at(d, 9, {"amit": 12, "priya": 5, "rohan": 52}[key]), self.now - datetime.timedelta(hours=4))
		if start.date() != d:
			start = self.at(d, 0, 30)
		base = PLACES[p["base"]]
		field = key != "amit"
		self.checkin(key, start, "IN", "Field" if field else "Office", base)
		if field:
			sites = SITES[p["base"]]
			end1 = self.trip(p, start + datetime.timedelta(minutes=35), self.rng.sample(sites, 2), cut_off=self.now)
			if end1 and end1 < self.now - datetime.timedelta(minutes=30):
				# Keep the second trip running right now, so the live map shows someone on the move.
				second = max(end1 + datetime.timedelta(minutes=20), self.now - datetime.timedelta(minutes=75))
				self.trip(p, second, self.rng.sample(sites, 2), cut_off=self.now)

	def checkin(self, key, when, log_type, mode, place):
		self.save("Employee Checkin", frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": self.emp[key],
			"time": when,
			"log_type": log_type,
			"custom_work_mode": mode,
			"device_id": "Mobile App",
			"latitude": place[0] + self.rng.uniform(-0.0005, 0.0005),
			"longitude": place[1] + self.rng.uniform(-0.0005, 0.0005),
			"skip_auto_attendance": 1,
		}))

	def trip(self, p, start, site_names, gap=False, speed_spike=False, manual=False, cut_off=None):
		"""Base -> site -> site -> base, with GPS pings every 15 minutes. Returns the trip end time."""
		rng, key = self.rng, p["key"]
		base = PLACES[p["base"]]
		stops = [(n, PLACES[n]) for n in site_names]

		# Build the timeline: travel legs at ~25 km/h on roads 1.35x longer than straight lines, then halts.
		legs, t, here, km = [], start, base, 0.0
		for name, place in stops + [(p["base"], base)]:
			dist = haversine(here, place) * 1.35
			travel = datetime.timedelta(minutes=max(10, dist / 25 * 60))
			legs.append(("move", t, t + travel, here, place, dist))
			t += travel
			km += dist
			here = place
			if name != p["base"]:
				halt = datetime.timedelta(minutes=rng.randint(25, 55))
				legs.append(("halt", t, t + halt, place, place, 0, name))
				t += halt
		end = t
		open_trip = bool(cut_off and end > cut_off)
		if open_trip:
			if start >= cut_off:
				return None
			covered = sum(l[5] * min(1, max(0, (cut_off - l[1]) / (l[2] - l[1]))) for l in legs if l[0] == "move")
			km, end = covered, None

		trip = self.save("Trip 2", frappe.get_doc({
			"doctype": "Trip 2",
			"employee": self.emp[key],
			"vehicle": self.vehicles.get(self.emp[key]),
			"start_time": start,
			"end_time": end,
			"end_latitude": base[0] if end else None,
			"end_longitude": base[1] if end else None,
			"total_distance_km": round(km, 1),
			"total_duration_minutes": round(((end or cut_off) - start).total_seconds() / 60, 1),
			"total_halt_minutes": sum((l[2] - l[1]).total_seconds() / 60 for l in legs if l[0] == "halt"),
			"fuel_used_liters": round(km / 45, 2),
			"fuel_cost": round(km / 45 * 105, 2),
			"notes": "Demo trip: " + ", ".join(site_names),
		}))
		if not trip:
			return end
		if end:
			self.trips.append((key, start.date(), round(km, 1)))

		for leg in legs:
			if leg[0] != "halt" or (cut_off and leg[1] > cut_off):
				continue
			self.save("Trip Stop", frappe.get_doc({
				"doctype": "Trip Stop",
				"trip": trip.name,
				"stop_type": "halted",
				"title": leg[6],
				"address": f"{leg[6]}, Mumbai",
				"start_time": leg[1],
				"end_time": leg[2] if not cut_off or leg[2] <= cut_off else None,
				"duration_minutes": round((leg[2] - leg[1]).total_seconds() / 60, 1),
				"latitude": leg[3][0],
				"longitude": leg[3][1],
			}))

		# GPS pings
		last = cut_off - datetime.timedelta(minutes=5) if open_trip else (end or start)
		t, battery, n = start, rng.randint(70, 100), 0
		total = (last - start).total_seconds() or 1
		while t <= last:
			frac = (t - start).total_seconds() / total
			n += 1
			if gap and 0.35 < frac < 0.75:
				t += datetime.timedelta(minutes=15)
				continue
			pos, moving = position(legs, t)
			accuracy = rng.uniform(150, 350) if rng.random() < 0.015 else rng.uniform(4, 25)
			speed = rng.uniform(4, 11) if moving else rng.uniform(0, 0.5)
			if speed_spike and n == 4:
				speed = 41
			self.save("Location Ping", frappe.get_doc({
				"doctype": "Location Ping",
				"employee": self.emp[key],
				"trip": trip.name,
				"timestamp": t,
				"latitude": pos[0] + rng.uniform(-0.0003, 0.0003),
				"longitude": pos[1] + rng.uniform(-0.0003, 0.0003),
				"speed": round(speed, 2),
				"accuracy": round(accuracy, 1),
				"battery": max(battery - n, 15),
				"source": "manual" if (manual and n == 3) else "background",
			}))
			t += datetime.timedelta(minutes=15)
		return end

	def regularizations(self):
		for key, d, explanation, submit in (
			("priya", self.wd[8], "Went straight to client site, the mobile app could not get GPS", True),
			("rohan", self.wd[2], "Forgot to punch out after late site work at Nerul", False),
		):
			self.save("Attendance Request", frappe.get_doc({
				"doctype": "Attendance Request",
				"employee": self.emp[key],
				"company": self.company,
				"from_date": d,
				"to_date": d,
				"reason": "On Duty",
				"explanation": explanation,
			}), submit=submit)

	def tasks(self):
		base_start, base_due = datetime.time(10, 0), datetime.time(18, 0)
		for key, subject, category, project, site, priority, start_off, due_off, outcome in TASKS:
			start = datetime.datetime.combine(self.today, base_start) + datetime.timedelta(days=start_off)
			due = datetime.datetime.combine(self.today, base_due) + datetime.timedelta(days=due_off)
			doc = frappe.get_doc({
				"doctype": "Task",
				"subject": subject,
				"project": self.projects.get(project) if project else None,
				"priority": priority,
				"company": self.company,
				"custom_assigned_to": self.emp[key],
				"custom_work_category": category,
				"custom_site": site,
				"exp_start_date": start,
				"exp_end_date": due,
				"description": f"<p>{subject}. Site: {site}.</p>",
			})
			if outcome in ("on_time", "late"):
				done = due.date() - datetime.timedelta(days=1) if outcome == "on_time" else due.date() + datetime.timedelta(days=2)
				doc.update({"status": "Completed", "completed_on": min(max(done, start.date()), self.today),
					"act_start_date": start.date(), "act_end_date": min(max(done, start.date()), self.today),
					"completed_by": email(key), "progress": 100})
			elif outcome == "working":
				doc.update({"status": "Working", "act_start_date": start.date(), "progress": 40})
			elif outcome == "overdue":
				doc.update({"status": "Overdue", "progress": 20})
			else:
				doc.status = "Open"
			if self.save("Task", doc) and doc.status != "Completed":
				add_assignment({"assign_to": [email(key)], "doctype": "Task", "name": doc.name, "description": subject}, ignore_permissions=True)

	def claims(self):
		"""Weekly petrol claims for the last four complete weeks."""
		monday = add_days(self.today, -self.today.weekday())
		for weeks_ago in (4, 3, 2, 1):
			start = add_days(monday, -7 * weeks_ago)
			end = add_days(start, 5)
			for key in ("priya", "rohan", "amit"):
				gps = round(sum(km for k, d, km in self.trips if k == key and start <= d <= end), 1)
				if not gps:
					continue
				state = {
					("priya", 4): "Approved", ("rohan", 4): "Approved", ("priya", 3): "Approved", ("rohan", 3): "Rejected",
					("priya", 2): "Approved", ("rohan", 2): "Draft", ("amit", 2): "Approved",
				}.get((key, weeks_ago), "Draft" if key != "amit" else "Approved")
				manual = key == "rohan" and weeks_ago == 2
				claimed = round(gps * 1.28) if manual else round(gps + self.rng.uniform(0, 3), 1)
				eligible = round(min(claimed, gps * 1.10), 1)
				posting = min(add_days(end, 1), self.today)
				self.save(f"Petrol Claim ({state})", frappe.get_doc({
					"doctype": "Expense Claim",
					"employee": self.emp[key],
					"company": self.company,
					"posting_date": posting,
					"currency": self.currency,
					"exchange_rate": 1,
					"expense_approver": email("finance") if key == "amit" else email("amit"),
					"approval_status": state,
					"custom_claim_from": start,
					"custom_claim_to": end,
					"custom_km_source": "Manual" if manual else "GPS",
					"custom_claimed_km": claimed,
					"custom_gps_km": gps,
					"custom_eligible_km": eligible,
					"custom_rate_per_km": RATE_PER_KM,
					"remark": "Odometer reading entered manually, GPS was off for two days" if manual else "Weekly petrol claim",
					"expenses": [{
						"expense_date": end,
						"expense_type": PETROL,
						"description": f"Petrol for {claimed:g} km field travel ({frappe.format(start, 'Date')} - {frappe.format(end, 'Date')})",
						"amount": round(claimed * RATE_PER_KM, 2),
						"sanctioned_amount": round(eligible * RATE_PER_KM, 2) if state == "Approved" else 0,
					}],
				}))


# ---- helpers ---------------------------------------------------------------


def default_company():
	company = (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.db.get_value("Company", {}, "name")
	)
	if not company:
		frappe.throw("Create a Company first (finish the ERPNext setup wizard), then run the demo again.")
	return company


def make_user(mail, first, last, roles):
	if frappe.db.exists("User", mail):
		user = frappe.get_doc("User", mail)
	else:
		user = frappe.get_doc({
			"doctype": "User",
			"email": mail,
			"first_name": first,
			"last_name": last,
			"user_type": "System User",
			"send_welcome_email": 0,
			"enabled": 1,
		})
		user.flags.ignore_permissions = True
		user.insert()
	user.add_roles(*[r for r in roles if frappe.db.exists("Role", r)])
	update_password(mail, PASSWORD)


def next_workday(d, holidays):
	while d in holidays or d.weekday() == 6:
		d = add_days(d, 1)
	return d


def haversine(a, b):
	lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
	h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
	return 6371 * 2 * math.asin(math.sqrt(h))


def position(legs, t):
	"""Where the trip is at time t, and whether it is moving."""
	for leg in legs:
		kind, start, end, a, b = leg[:5]
		if start <= t <= end:
			if kind == "halt":
				return a, False
			f = (t - start).total_seconds() / max((end - start).total_seconds(), 1)
			return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f), True
	return legs[-1][4], False


@frappe.whitelist(methods=["POST"])
def delete():
	"""Remove everything `create` made (all records of @demo.local employees and the demo logins)."""
	frappe.only_for("System Manager")
	users = frappe.get_all("User", filters={"name": ["like", f"%@{DOMAIN}"]}, pluck="name")
	emps = frappe.get_all("Employee", filters={"user_id": ["in", users]}, pluck="name") if users else []

	if emps:
		claims = frappe.get_all("Expense Claim", filters={"employee": ["in", emps]}, pluck="name")
		if claims:
			frappe.db.delete("Expense Claim Detail", {"parent": ["in", claims]})
		trips = frappe.get_all("Trip 2", filters={"employee": ["in", emps]}, pluck="name")
		if trips:
			frappe.db.delete("Trip Stop", {"trip": ["in", trips]})
		tasks = frappe.get_all("Task", filters={"custom_assigned_to": ["in", emps]}, pluck="name")
		if tasks:
			frappe.db.delete("ToDo", {"reference_type": "Task", "reference_name": ["in", tasks]})
			frappe.db.delete("Task", {"name": ["in", tasks]})
		for dt in ("Expense Claim", "Attendance Request", "Leave Application", "Attendance", "Leave Allocation",
				"Leave Ledger Entry", "Employee Checkin", "Location Ping", "Trip 2", "Vehicles"):
			frappe.db.delete(dt, {"employee": ["in", emps]})
		frappe.db.set_value("Employee", {"name": ["in", emps]}, "reports_to", None)
		frappe.db.delete("Employee", {"name": ["in", emps]})

	for title in PROJECTS.values():
		if not frappe.db.exists("Task", {"project": ("in", frappe.get_all("Project", {"project_name": title}, pluck="name"))}):
			frappe.db.delete("Project", {"project_name": title})
	for user in users:
		frappe.db.delete("User Permission", {"user": user})
		frappe.delete_doc("User", user, force=True, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: also runs from the browser, nothing else commits for us
	return f"Removed demo data for {len(emps)} employee(s) and {len(users)} login(s)."
