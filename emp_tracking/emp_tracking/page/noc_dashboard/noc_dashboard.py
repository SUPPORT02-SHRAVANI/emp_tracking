# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import math

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	formatdate,
	get_datetime,
	get_first_day,
	get_last_day,
	getdate,
	now_datetime,
	time_diff_in_seconds,
)

# Dashboard status buckets, in display order, and the workflow states that fall in each.
STATUS_BUCKETS = {
	"NEED TO ASSIGN": ("New", "NOC Verification", "Assigned to Area Manager", "Rejected"),
	"WIP": ("Assigned to Maintenance Team", "Accepted", "In Progress", "Restoration"),
}
CLOSED_STATES = ("Fiber Restored", "Awaiting Operator Confirmation", "Resolved", "Closed")
MTTR_LIMIT_HOURS = 4
OTHER = "OTHER"

FIELDS = [
	"name",
	"workflow_state",
	"operatorcustomer",
	"complaint_type",
	"linkid",
	"area",
	"mapped_vendor",
	"rider",
	"splicer",
	"complaint_date_and_time",
	"modified",
]


@frappe.whitelist()
def get_dashboard_data(closed_date=None):
	closed_date = getdate(closed_date)
	now = now_datetime()

	open_rows = frappe.get_list(
		"Complaint Information",
		filters={"workflow_state": ["not in", CLOSED_STATES]},
		fields=FIELDS,
		limit_page_length=0,
	)
	# No closing date is stored on the complaint, so the day it was last changed stands in for it.
	closed_rows = frappe.get_list(
		"Complaint Information",
		filters={
			"workflow_state": ["in", CLOSED_STATES],
			"modified": ["between", [closed_date, closed_date]],
		},
		fields=FIELDS,
		limit_page_length=0,
	)

	employees = {r.rider for r in open_rows + closed_rows} | {r.splicer for r in open_rows + closed_rows}
	employees.discard(None)
	names = dict(
		frappe.get_all(
			"Employee", filters={"name": ["in", list(employees)]}, fields=["name", "employee_name"], as_list=True
		)
	) if employees else {}

	for row in open_rows + closed_rows:
		row.bucket = bucket_of(row.workflow_state)
		# Several complaints on one LINKID are the same fibre cut.
		row.cut = row.linkid or row.name
		row.owner_group = (row.mapped_vendor or row.area or OTHER).upper()
		worker = row.splicer or row.rider
		row.worker = (names.get(worker) or worker or OTHER).upper()
		row.age = max(time_diff_in_seconds(now, get_datetime(row.complaint_date_and_time)), 0)

	overdue = [r for r in open_rows if r.age > MTTR_LIMIT_HOURS * 3600]
	wip = [r for r in open_rows if r.bucket == "WIP"]

	return {
		"closed_date": str(closed_date),
		"mttr_limit_hours": MTTR_LIMIT_HOURS,
		"status": status_summary(open_rows),
		"status_description": grouped(open_rows, "bucket", "owner_group"),
		"company": company_summary(open_rows),
		"working": flat(wip, "worker"),
		"closed": flat(closed_rows, "worker"),
		"overdue": grouped(overdue, "bucket", "owner_group", with_age=True),
	}


def bucket_of(state):
	for bucket, states in STATUS_BUCKETS.items():
		if state in states:
			return bucket
	return (state or _("No Status")).upper()


def bucket_order(rows):
	"""Known buckets first in their fixed order, then any state the workflow gains later."""
	seen = {r.bucket for r in rows}
	known = [b for b in STATUS_BUCKETS if b in seen]
	return known + sorted(seen - set(known))


def cuts(rows):
	return len({r.cut for r in rows})


def status_summary(rows):
	out = []
	for bucket in bucket_order(rows):
		members = [r for r in rows if r.bucket == bucket]
		out.append(
			{
				"label": bucket,
				"unique_cut": cuts(members),
				"sr_received": len(members),
				# lets the dashboard tile open the complaint list filtered to this bucket
				"states": sorted({r.workflow_state for r in members if r.workflow_state}),
			}
		)
	return {"rows": out, "unique_cut": sum(r["unique_cut"] for r in out), "sr_received": len(rows)}


def grouped(rows, group_key, child_key, with_age=False):
	"""Two-level pivot: group -> children, each with a unique-cut count (and oldest age)."""
	out, total = [], 0
	for group in bucket_order(rows) if group_key == "bucket" else sorted({r[group_key] for r in rows}):
		members = [r for r in rows if r[group_key] == group]
		children = []
		for child in sorted({r[child_key] for r in members}):
			sub = [r for r in members if r[child_key] == child]
			entry = {"label": child, "unique_cut": cuts(sub)}
			if with_age:
				entry["age"] = max(r.age for r in sub)
			children.append(entry)
		group_total = sum(c["unique_cut"] for c in children)
		total += group_total
		out.append({"label": group, "unique_cut": group_total, "children": children})
	return {"rows": out, "unique_cut": total}


def company_summary(rows):
	"""Operator -> complaint type rows against status-bucket columns."""
	columns = bucket_order(rows)

	def counts(members):
		by_bucket = {c: cuts([r for r in members if r.bucket == c]) for c in columns}
		return {"by_bucket": by_bucket, "total": sum(by_bucket.values())}

	out = []
	for operator in sorted({r.operatorcustomer or OTHER for r in rows}):
		members = [r for r in rows if (r.operatorcustomer or OTHER) == operator]
		children = []
		for ctype in sorted({r.complaint_type or OTHER for r in members}):
			sub = [r for r in members if (r.complaint_type or OTHER) == ctype]
			children.append({"label": ctype.upper(), **counts(sub)})
		by_bucket = {c: sum(ch["by_bucket"][c] for ch in children) for c in columns}
		out.append(
			{"label": operator.upper(), "by_bucket": by_bucket, "total": sum(by_bucket.values()), "children": children}
		)
	by_bucket = {c: sum(o["by_bucket"][c] for o in out) for c in columns}
	return {"columns": columns, "rows": out, "by_bucket": by_bucket, "total": sum(by_bucket.values())}


def flat(rows, key):
	out = [
		{"label": label, "unique_cut": cuts([r for r in rows if r[key] == label])}
		for label in sorted({r[key] for r in rows})
	]
	return {"rows": out, "unique_cut": sum(r["unique_cut"] for r in out)}


# ---- Employee / area supervisor monthly sheet --------------------------------------------

SHEET_ROLES = ("NOC Head", "Area Manager", "System Manager")
LOCATION_TYPES = ("field", "home", "office", "other")
DEFAULT_RADIUS_M = 200
# A gap longer than this between two pings means the phone was not reporting; it is not counted.
MAX_PING_GAP_SECONDS = 15 * 60


@frappe.whitelist()
def get_employee_sheet(employee, month=None):
	"""One row per day of the month: hours by location type and complaint counts for an employee."""
	frappe.only_for(SHEET_ROLES)
	start = get_first_day(getdate(month))
	end = get_last_day(start)
	days = {add_days(start, i): new_day() for i in range((end - start).days + 1)}

	add_location_hours(days, employee, start, end)
	add_complaint_counts(days, employee, start, end)

	rows = []
	for day, values in days.items():
		restored = values.pop("restore_seconds")
		values["mttr"] = sum(restored) / len(restored) if restored else 0
		rows.append({"date": str(day), **values})

	total = {key: sum(r[key] for r in rows) for key in (*LOCATION_TYPES, "complaints", "restored", "in_sla", "out_sla")}
	total["mttr"] = sum(r["mttr"] * r["restored"] for r in rows) / total["restored"] if total["restored"] else 0
	return {
		"employee_name": frappe.db.get_value("Employee", employee, "employee_name") or employee,
		"month": formatdate(start, "MMMM yyyy"),
		"rows": rows,
		"total": total,
	}


def new_day():
	return {**dict.fromkeys(LOCATION_TYPES, 0), "complaints": 0, "restored": 0, "in_sla": 0, "out_sla": 0, "restore_seconds": []}


def add_location_hours(days, employee, start, end):
	pings = frappe.get_all(
		"Location Ping",
		filters={"employee": employee, "timestamp": ["between", [start, end]]},
		fields=["timestamp", "latitude", "longitude"],
		order_by="timestamp asc",
		limit_page_length=0,
	)
	if not pings:
		return

	home = frappe.get_all(
		"Employee Home Location",
		filters={"employee": employee},
		fields=["latitude", "longitude", "geofence_radius_meters as radius"],
	)
	offices = frappe.get_all("Shift Location", fields=["latitude", "longitude", "checkin_radius as radius"])
	# Sites of the complaints this employee was sent to.
	sites = frappe.get_all(
		"Complaint Information",
		or_filters={"rider": employee, "splicer": employee},
		fields=["latitude", "longitude", "operator_latitude", "operator_longitude"],
		limit_page_length=0,
	)
	fields = [{"latitude": s.latitude or s.operator_latitude, "longitude": s.longitude or s.operator_longitude} for s in sites]

	def location_type(ping):
		if near(ping, fields):
			return "field"
		if near(ping, home):
			return "home"
		if near(ping, offices):
			return "office"
		return "other"

	for ping, following in zip(pings, pings[1:]):
		gap = time_diff_in_seconds(following.timestamp, ping.timestamp)
		day = getdate(ping.timestamp)
		if 0 < gap <= MAX_PING_GAP_SECONDS and day == getdate(following.timestamp) and ping.latitude and ping.longitude:
			days[day][location_type(ping)] += gap


def near(ping, places):
	for place in places:
		if place.get("latitude") and place.get("longitude"):
			if distance_m(ping.latitude, ping.longitude, place["latitude"], place["longitude"]) <= (
				place.get("radius") or DEFAULT_RADIUS_M
			):
				return True
	return False


def distance_m(lat1, lon1, lat2, lon2):
	"""Haversine distance in metres."""
	p1, p2 = math.radians(lat1), math.radians(lat2)
	a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
	return 6371000 * 2 * math.asin(math.sqrt(a))


def add_complaint_counts(days, employee, start, end):
	# An area supervisor is counted on every complaint in their areas, a rider/splicer on their own.
	user = frappe.db.get_value("Employee", employee, "user_id")
	areas = frappe.get_all("Area", filters={"area_manager": user}, pluck="name") if user else []
	or_filters = {"rider": employee, "splicer": employee}
	if areas:
		or_filters["area"] = ["in", areas]
	fields = ["workflow_state", "complaint_date_and_time", "modified"]

	received = frappe.get_all(
		"Complaint Information",
		filters={"complaint_date_and_time": ["between", [start, end]]},
		or_filters=or_filters,
		fields=fields,
		limit_page_length=0,
	)
	for row in received:
		days[getdate(row.complaint_date_and_time)]["complaints"] += 1

	# No restore time is stored on the complaint, so the last change to a closed one stands in for it.
	restored = frappe.get_all(
		"Complaint Information",
		filters={"workflow_state": ["in", CLOSED_STATES], "modified": ["between", [start, end]]},
		or_filters=or_filters,
		fields=fields,
		limit_page_length=0,
	)
	for row in restored:
		day = days[getdate(row.modified)]
		seconds = max(time_diff_in_seconds(row.modified, get_datetime(row.complaint_date_and_time)), 0)
		day["restored"] += 1
		day["in_sla" if seconds <= MTTR_LIMIT_HOURS * 3600 else "out_sla"] += 1
		day["restore_seconds"].append(seconds)
