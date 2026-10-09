# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""HTTP API of the Workforce Dashboards page (/app/workforce-dashboard).

Every call re-checks the user's roles and employee scope on the server, so the
browser only decides what to ask for, never what it is allowed to see or change.
"""

import datetime
from io import BytesIO

import frappe
import xlsxwriter
from frappe import _
from frappe.desk.form.assign_to import _add as add_assignment
from frappe.desk.form.assign_to import clear as clear_assignments
from frappe.desk.form.assign_to import close_all_assignments
from frappe.utils import flt, get_fullname, getdate, now_datetime, nowdate
from frappe.utils.xlsxutils import make_xlsx

from emp_tracking.emp_tracking.page.workforce_dashboard.access import (
	DASHBOARDS,
	allowed_dashboards,
	can_approve,
	check_dashboard,
	get_scope,
	landing_dashboard,
	roles_of,
)
from emp_tracking.emp_tracking.page.workforce_dashboard.boards import BUILDERS, drill
from emp_tracking.emp_tracking.page.workforce_dashboard.metrics import PERIODS, Dataset

# Dashboards that open on today's picture; the rest default to a 30-day window.
TODAY_FIRST = ("employee", "team", "field", "exceptions")

# How the detail panel shows each record: the field that names its employee, and the fields to list.
DETAIL = {
	"Task": {
		"employee": "custom_assigned_to",
		"title": "subject",
		"status": "status",
		"fields": [
			("name", "Task", "text"),
			("custom_work_category", "Type", "text"),
			("project", "Project", "text"),
			("custom_site", "Site / Location", "text"),
			("priority", "Priority", "status"),
			("exp_start_date", "Expected Start", "datetime"),
			("exp_end_date", "Due", "datetime"),
			("completed_on", "Completed On", "date"),
			("progress", "Progress", "pct"),
			("custom_service_request", "Service Request", "text"),
			("description", "Description", "html"),
		],
	},
	"Leave Application": {
		"employee": "employee",
		"title": "leave_type",
		"status": "status",
		"fields": [
			("name", "Application", "text"),
			("leave_type", "Leave Type", "text"),
			("from_date", "From", "date"),
			("to_date", "To", "date"),
			("total_leave_days", "Days", "float"),
			("leave_balance", "Balance Before", "float"),
			("posting_date", "Applied On", "date"),
			("leave_approver_name", "Approver", "text"),
			("description", "Reason", "text"),
		],
	},
	"Expense Claim": {
		"employee": "employee",
		"title": None,
		"status": "approval_status",
		"fields": [
			("name", "Claim", "text"),
			("posting_date", "Posted", "date"),
			("custom_claim_from", "Period From", "date"),
			("custom_claim_to", "Period To", "date"),
			("custom_claimed_km", "Claimed KM", "km"),
			("custom_gps_km", "GPS KM", "km"),
			("custom_eligible_km", "Eligible KM", "km"),
			("custom_km_source", "KM Source", "text"),
			("custom_rate_per_km", "Rate / KM", "currency"),
			("total_claimed_amount", "Claimed Amount", "currency"),
			("total_sanctioned_amount", "Sanctioned Amount", "currency"),
			("expense_approver", "Approver", "text"),
			("remark", "Remark", "text"),
		],
	},
	"Attendance Request": {
		"employee": "employee",
		"title": None,
		"status": None,
		"fields": [
			("name", "Request", "text"),
			("from_date", "From", "date"),
			("to_date", "To", "date"),
			("reason", "Reason", "text"),
			("explanation", "Explanation", "text"),
		],
	},
	"Attendance": {
		"employee": "employee",
		"title": None,
		"status": "status",
		"fields": [
			("name", "Attendance", "text"),
			("attendance_date", "Date", "date"),
			("in_time", "In", "datetime"),
			("out_time", "Out", "datetime"),
			("working_hours", "Working Hours", "hours"),
			("late_entry", "Late Entry", "check"),
			("early_exit", "Early Exit", "check"),
			("leave_type", "Leave Type", "text"),
		],
	},
	"Employee": {
		"employee": "name",
		"title": "employee_name",
		"status": "status",
		"fields": [
			("name", "Employee ID", "text"),
			("designation", "Designation", "text"),
			("department", "Department", "text"),
			("reports_to", "Reports To", "text"),
			("cell_number", "Mobile", "text"),
			("company_email", "Email", "text"),
			("date_of_joining", "Joined", "date"),
		],
	},
	"Location Ping": {
		"employee": "employee",
		"title": None,
		"status": "source",
		"fields": [
			("timestamp", "Time", "datetime"),
			("latitude", "Latitude", "text"),
			("longitude", "Longitude", "text"),
			("accuracy", "Accuracy (m)", "float"),
			("speed", "Speed (m/s)", "float"),
			("battery", "Battery %", "int"),
			("trip", "Trip", "text"),
		],
	},
	"Trip 2": {
		"employee": "employee",
		"title": None,
		"status": None,
		"fields": [
			("name", "Trip", "text"),
			("vehicle", "Vehicle", "text"),
			("start_time", "Start", "datetime"),
			("end_time", "End", "datetime"),
			("total_distance_km", "Distance", "km"),
			("total_duration_minutes", "Duration (min)", "float"),
			("total_halt_minutes", "Halt (min)", "float"),
			("notes", "Notes", "text"),
		],
	},
	"Trip Stop": {
		"employee": None,
		"title": "title",
		"status": "stop_type",
		"fields": [
			("trip", "Trip", "text"),
			("address", "Address", "text"),
			("start_time", "Arrived", "datetime"),
			("end_time", "Left", "datetime"),
			("duration_minutes", "Minutes", "float"),
		],
	},
}

ACTION_LABELS = {
	"start": ("Start Work", "default"),
	"complete": ("Mark Completed", "primary"),
	"reassign": ("Reassign", "default"),
	"extend": ("Extend Due Date", "default"),
	"remind": ("Send Reminder", "default"),
	"approve": ("Approve", "primary"),
	"reject": ("Reject", "danger"),
}


# ---- page boot -------------------------------------------------------------


@frappe.whitelist()
def get_boot():
	roles = roles_of()
	level, own, scope = get_scope()
	employees = frappe.get_all(
		"Employee",
		filters={"name": ["in", scope]},
		fields=["name", "employee_name", "department", "reports_to"],
		order_by="employee_name asc",
	) if scope else []
	leads = {e.reports_to for e in employees if e.reports_to}
	projects = frappe.get_all(
		"Task",
		filters={"custom_assigned_to": ["in", scope], "project": ["is", "set"]},
		pluck="project",
		distinct=True,
		limit_page_length=200,
	) if scope and custom_fields_ready() else []
	project_names = dict(frappe.get_all("Project", filters={"name": ["in", projects]}, fields=["name", "project_name"], as_list=True)) if projects else {}

	return {
		"user": get_fullname(),
		"dashboards": [{"key": k, "label": _(DASHBOARDS[k]["label"])} for k in allowed_dashboards(roles)],
		"landing": landing_dashboard(roles),
		"scope": level,
		"own_employee": own,
		"periods": PERIODS,
		"today_first": TODAY_FIRST,
		"ready": custom_fields_ready(),
		"employees": [{"value": e.name, "label": f"{e.employee_name} ({e.name})"} for e in employees],
		"teams": [{"value": e.name, "label": e.employee_name} for e in employees if e.name in leads],
		"departments": sorted({e.department for e in employees if e.department}),
		"projects": [{"value": p, "label": project_names.get(p) or p} for p in projects],
	}


def custom_fields_ready():
	return bool(frappe.db.exists("Custom Field", {"dt": "Task", "fieldname": "custom_assigned_to"}))


# ---- dashboards ------------------------------------------------------------


def dataset_for(dashboard, filters):
	check_dashboard(dashboard, roles_of())
	if not custom_fields_ready():
		frappe.throw(_("EVision Dashboards are not installed yet. Run the setup described in the README first."))

	f = frappe._dict(frappe.parse_json(filters) if isinstance(filters, str) else (filters or {}))
	if dashboard == "employee":
		# One person only: pick the requested employee if visible, else the user's own record.
		_level, own, scope = get_scope()
		if f.employee not in scope:
			f.employee = own or (sorted(scope)[0] if scope else None)
		f.team = f.department = None
		if not f.employee:
			f.employee = "__none__"
	return Dataset(f)


@frappe.whitelist()
def get_dashboard(dashboard: str, filters: str | dict | None = None):
	ds = dataset_for(dashboard, filters)
	data = BUILDERS[dashboard](ds)
	data["meta"] = meta(ds)
	return data


@frappe.whitelist()
def get_drilldown(dashboard: str, key: str, filters: str | dict | None = None):
	ds = dataset_for(dashboard, filters)
	title, spec, rows = drill(ds, key)
	keys = [k for k, _l, _f in spec] + ["_doctype", "_name", "_drill", "employee"]
	return {
		"title": _(title),
		"columns": [{"key": k, "label": _(label), "fmt": fmt} for k, label, fmt in spec],
		"rows": [{k: r.get(k) for k in keys} for r in rows],
		"meta": meta(ds),
	}


def meta(ds):
	return {
		"period": ds.period,
		"from_date": ds.start,
		"to_date": ds.end,
		"employees": len(ds.ids),
		"scope": ds.level,
		"updated_at": now_datetime(),
	}


# ---- record detail + actions -----------------------------------------------


def load_record(doctype, name):
	if doctype not in DETAIL:
		frappe.throw(_("Details are not available for {0}").format(doctype))
	doc = frappe.get_doc(doctype, name)
	field = DETAIL[doctype]["employee"]
	employee = doc.get(field) if field else frappe.db.get_value("Trip 2", doc.trip, "employee")
	_level, own, scope = get_scope()
	if employee not in scope:
		frappe.throw(_("You are not permitted to view this record"), frappe.PermissionError)
	return doc, employee, own


def available_actions(doc, employee, own, roles):
	dt = doc.doctype
	mine = employee == own
	manager = can_approve(dt, roles)
	actions = []

	if dt == "Task" and doc.status not in ("Completed", "Cancelled", "Template"):
		if manager or mine:
			if doc.status in ("Open", "Overdue"):
				actions.append("start")
			actions.append("complete")
		if manager:
			actions += ["reassign", "extend", "remind"]
	elif dt == "Leave Application" and doc.docstatus == 0 and doc.status == "Open" and manager and not mine:
		actions += ["approve", "reject"]
	elif dt == "Expense Claim" and doc.docstatus == 0 and doc.approval_status == "Draft" and manager and not mine:
		actions += ["approve", "reject"]
	elif dt == "Attendance Request" and doc.docstatus == 0 and manager and not mine:
		actions.append("approve")
	return actions


@frappe.whitelist()
def get_detail(doctype: str, name: str):
	doc, employee, own = load_record(doctype, name)
	spec = DETAIL[doctype]
	roles = roles_of()

	status = doc.get(spec["status"]) if spec["status"] else None
	if doctype == "Attendance Request":
		status = "Pending" if doc.docstatus == 0 else ("Approved" if doc.docstatus == 1 else "Cancelled")
	if doctype == "Expense Claim":
		status = "Pending" if status == "Draft" else status

	out = {
		"doctype": doctype,
		"name": doc.name,
		"title": doc.get(spec["title"]) if spec["title"] else f"{_(doctype)} {doc.name}",
		"status": status,
		"fields": [{"label": _(label), "value": doc.get(f), "fmt": fmt} for f, label, fmt in spec["fields"] if doc.get(f) not in (None, "")],
		"employee": employee_card(employee),
		"related": related(doc),
		"location": location_of(doc, employee),
		"can_open": frappe.has_permission(doctype, "read", doc),
		"actions": [],
	}

	for action in available_actions(doc, employee, own, roles):
		label, style = ACTION_LABELS[action]
		item = {"action": action, "label": _(label), "style": style}
		if action == "reassign":
			_l, _o, scope = get_scope()
			item["input"] = "select"
			item["options"] = [
				{"value": e.name, "label": e.employee_name}
				for e in frappe.get_all("Employee", filters={"name": ["in", scope]}, fields=["name", "employee_name"], order_by="employee_name")
				if e.name != employee
			]
		elif action == "extend":
			item["input"] = "date"
		elif action == "reject":
			item["input"] = "text"
		out["actions"].append(item)
	return out


def employee_card(employee):
	if not employee:
		return None
	e = frappe.db.get_value(
		"Employee",
		employee,
		["name", "employee_name", "designation", "department", "cell_number", "reports_to", "image", "user_id"],
		as_dict=True,
	)
	if not e:
		return None
	e.reports_to_name = frappe.db.get_value("Employee", e.reports_to, "employee_name") if e.reports_to else None
	return e


def related(doc):
	"""Linked records worth seeing before acting: the project, the service request, today's picture."""
	out = []
	if doc.doctype == "Task":
		if doc.project:
			p = frappe.db.get_value("Project", doc.project, ["name", "project_name", "status", "percent_complete", "expected_end_date"], as_dict=True)
			if p:
				out.append({"title": _("Project"), "doctype": "Project", "name": p.name, "fields": [
					{"label": _("Project"), "value": p.project_name, "fmt": "text"},
					{"label": _("Status"), "value": p.status, "fmt": "status"},
					{"label": _("Complete"), "value": flt(p.percent_complete, 1), "fmt": "pct"},
					{"label": _("Expected End"), "value": p.expected_end_date, "fmt": "date"},
				]})
		sr = doc.get("custom_service_request")
		if sr and frappe.db.exists("Complaint Information", sr):
			c = frappe.get_doc("Complaint Information", sr)
			out.append({"title": _("Service Request"), "doctype": "Complaint Information", "name": sr, "fields": [
				{"label": label, "value": c.get(f), "fmt": "text"}
				for f, label in (("workflow_state", _("State")), ("operatorcustomer", _("Customer")), ("complaint_type", _("Type")), ("linkid", _("Link ID")), ("area", _("Area")))
				if c.get(f)
			]})
		if doc.get("issue"):
			out.append({"title": _("Issue"), "doctype": "Issue", "name": doc.issue, "fields": [
				{"label": _("Subject"), "value": frappe.db.get_value("Issue", doc.issue, "subject"), "fmt": "text"},
			]})
	if doc.doctype == "Employee":
		ds = Dataset({"period": "Today", "employee": doc.name})
		if ds.ids:
			rec = ds.live.get(doc.name)
			open_tasks = [t for t in ds.all_tasks if t.is_open]
			out.append({"title": _("Today"), "fields": [
				{"label": _("Status"), "value": rec.live, "fmt": "status"},
				{"label": _("Checked In"), "value": rec.in_time, "fmt": "time"},
				{"label": _("Working Hours"), "value": rec.working_hours, "fmt": "hours"},
				{"label": _("Field KM"), "value": rec.km, "fmt": "km"},
				{"label": _("Current Task"), "value": rec.current_task.subject if rec.current_task else None, "fmt": "text"},
				{"label": _("Open Tasks"), "value": len(open_tasks), "fmt": "int"},
				{"label": _("Delayed Tasks"), "value": sum(1 for t in open_tasks if t.delayed), "fmt": "int"},
			]})
	return out


def location_of(doc, employee):
	lat, lng = doc.get("latitude"), doc.get("longitude")
	if doc.doctype == "Employee":
		loc = Dataset({"period": "Today", "employee": employee}).latest_location.get(employee)
		if loc:
			lat, lng = loc.latitude, loc.longitude
	if doc.doctype == "Trip 2":
		lat, lng = doc.get("end_latitude"), doc.get("end_longitude")
	if flt(lat) and flt(lng):
		return {"lat": flt(lat), "lng": flt(lng)}
	return None


@frappe.whitelist(methods=["POST"])
def take_action(doctype: str, name: str, action: str, value: str | None = None):
	doc, employee, own = load_record(doctype, name)
	if action not in available_actions(doc, employee, own, roles_of()):
		frappe.throw(_("You cannot {0} this {1} now").format(_(ACTION_LABELS.get(action, (action,))[0]).lower(), _(doctype)), frappe.PermissionError)

	by = get_fullname()
	if doctype == "Task":
		message = task_action(doc, action, value, employee)
	elif doctype == "Leave Application":
		doc.status = "Approved" if action == "approve" else "Rejected"
		doc.flags.ignore_permissions = True
		doc.submit()
		message = _("Leave {0}").format(_(doc.status).lower())
	elif doctype == "Expense Claim":
		if action == "approve":
			claimed, eligible = flt(doc.get("custom_claimed_km")), flt(doc.get("custom_eligible_km"))
			ratio = min(eligible / claimed, 1) if claimed and eligible else 1
			for row in doc.expenses:
				row.sanctioned_amount = flt(flt(row.amount) * ratio, 2)
			doc.approval_status = "Approved"
		else:
			for row in doc.expenses:
				row.sanctioned_amount = 0
			doc.approval_status = "Rejected"
		doc.save(ignore_permissions=True)
		message = _("Claim {0}").format(_(doc.approval_status).lower())
	elif doctype == "Attendance Request":
		doc.flags.ignore_permissions = True
		doc.submit()
		message = _("Regularization approved and attendance marked")

	note = _("{0} by {1} from EVision Dashboard").format(message, by)
	if value and action == "reject":
		note += ": " + frappe.utils.escape_html(value)
	doc.add_comment("Comment", note)
	return {"message": message}


def task_action(doc, action, value, employee):
	if action == "start":
		doc.status = "Working"
		doc.save(ignore_permissions=True)
		return _("Task started")

	if action == "complete":
		close_all_assignments("Task", doc.name, ignore_permissions=True)
		doc.status = "Completed"
		doc.completed_on = nowdate()
		doc.completed_by = frappe.session.user
		doc.save(ignore_permissions=True)
		return _("Task completed")

	if action == "reassign":
		_level, _own, scope = get_scope()
		if value not in scope or value == employee:
			frappe.throw(_("Pick another employee from your team"))
		clear_assignments("Task", doc.name, ignore_permissions=True)
		doc.custom_assigned_to = value
		doc.save(ignore_permissions=True)
		user = frappe.db.get_value("Employee", value, "user_id")
		if user:
			add_assignment({"assign_to": [user], "doctype": "Task", "name": doc.name, "description": doc.subject}, ignore_permissions=True)
		return _("Task reassigned to {0}").format(frappe.db.get_value("Employee", value, "employee_name"))

	if action == "extend":
		if not value or getdate(value) < getdate():
			frappe.throw(_("Pick a due date from today onwards"))
		doc.exp_end_date = datetime.datetime.combine(getdate(value), datetime.time(18, 0))
		if doc.status == "Overdue":
			doc.status = "Working" if doc.act_start_date else "Open"
		doc.save(ignore_permissions=True)
		return _("Due date moved to {0}").format(frappe.format(getdate(value), "Date"))

	if action == "remind":
		user = frappe.db.get_value("Employee", employee, "user_id")
		if not user:
			frappe.throw(_("This employee has no user login to notify"))
		frappe.get_doc({
			"doctype": "Notification Log",
			"for_user": user,
			"from_user": frappe.session.user,
			"type": "Alert",
			"document_type": "Task",
			"document_name": doc.name,
			"subject": _("Reminder from {0}: {1}").format(get_fullname(), doc.subject),
		}).insert(ignore_permissions=True)
		return _("Reminder sent")


# ---- export ----------------------------------------------------------------


@frappe.whitelist()
def export_excel(dashboard: str, filters: str | dict | None = None, key: str | None = None):
	ds = dataset_for(dashboard, filters)
	sheets = []
	if key:
		title, spec, rows = drill(ds, key)
		sheets.append((title, [{"key": k, "label": label} for k, label, _f in spec], rows))
	else:
		data = BUILDERS[dashboard](ds)
		sheets.append((
			"Summary",
			[{"key": "label", "label": _("Metric")}, {"key": "value", "label": _("Value")}, {"key": "hint", "label": _("Detail")}],
			data.get("kpis", []),
		))
		for s in data.get("sections", []):
			if s["type"] == "table":
				sheets.append((s["title"], s["columns"], s["rows"]))
			elif s["type"] in ("bars", "stats"):
				sheets.append((s["title"], [{"key": "label", "label": _("Name")}, {"key": "value", "label": _("Value")}], s["items"]))

	buf = BytesIO()
	wb = xlsxwriter.Workbook(buf, {"constant_memory": True, "default_date_format": "dd-mm-yyyy hh:mm"})
	used = set()
	header = [
		[_("EVision Dashboard"), _(DASHBOARDS[dashboard]["label"])],
		[_("Period"), f"{ds.period}: {frappe.format(ds.start, 'Date')} - {frappe.format(ds.end, 'Date')}"],
		[_("Generated"), f"{frappe.format(now_datetime(), 'Datetime')} by {get_fullname()}"],
		[],
	]
	for title, columns, rows in sheets:
		name = unique_sheet_name(title, used)
		table = [[c["label"] for c in columns]] + [[cell(r.get(c["key"])) for c in columns] for r in rows]
		make_xlsx(header + table if name == "Summary" else table, name, wb=wb)
	wb.close()

	frappe.response["filename"] = f"{dashboard}-dashboard-{nowdate()}.xlsx"
	frappe.response["filecontent"] = buf.getvalue()
	frappe.response["type"] = "binary"


def unique_sheet_name(title, used):
	base = "".join(ch for ch in str(title) if ch not in "[]:*?/\\")[:28] or "Sheet"
	name, n = base, 2
	while name.lower() in used:
		name = f"{base[:26]} {n}"
		n += 1
	used.add(name.lower())
	return name


def cell(value):
	if value is None:
		return ""
	if isinstance(value, bool):
		return _("Yes") if value else _("No")
	if isinstance(value, datetime.timedelta):
		return str(value)
	if isinstance(value, (int, float, str, datetime.date, datetime.datetime)):
		return value
	return str(value)
