# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Employee Attendance Detail (Script Report)
#
# How this file works
#   Month grid like the biometric "Monthly Status Report (Detailed Work Duration)": for every
#   employee six rows (Status, In Time, Out Time, Duration, Late By, Early By) and one column per
#   day, plus month totals on the Status row.
#   - Status / In / Out come from submitted Attendance (In Time / Out Time are filled by HRMS auto
#     attendance and by the Oct-2026 biometric import). When an Attendance has no times, the
#     day's Employee Checkins are used (first punch = in, last punch = out).
#   - Days without Attendance: WO / H from the employee's Holiday List (or the company default),
#     otherwise "-" (not marked). Future days stay blank.
#   - Late By / Early By are measured against the shift: the Attendance's shift, else the
#     employee's Default Shift, else the "Shift Start / Shift End" filters (default 09:30-18:29
#     with 15 min late / 10 min early grace: the biometric machine's "FS" shift).
#   - Holiday List without dates for the month: its "Weekly Off" day is shown as WO.
#   Read-only: nothing is written.
#
# Change log
#   2026-11-23  Created (user: view the biometric-style data employee wise in Frappe).
#   2026-11-23  Coloured Excel download; same day made simpler (3 rows per employee, red late/early times).
#   2026-11-23  Excel download laid out like the biometric sheet (user screenshot): Employee line +
#               summary, 6-row block, A red / WO blue / off-day columns yellow.
# ---------------------------------------------------------------------------------------------

import calendar
from datetime import date, datetime, timedelta

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, getdate, today

MONTHS = list(calendar.month_name)[1:]
DETAIL_ROWS = ["Status", "In Time", "Out Time", "Duration", "Late By", "Early By"]
STATUS_CODE = {"Present": "P", "Absent": "A", "Half Day": "½P", "On Leave": "L", "Work From Home": "WFH"}


# Date: 2026-11-23
def execute(filters=None):
	f = frappe._dict(filters or {})
	year = int(f.year or getdate().year)
	month = MONTHS.index(f.month) + 1 if f.month in MONTHS else getdate().month
	start = date(year, month, 1)
	end = date(year, month, calendar.monthrange(year, month)[1])
	days = [start + timedelta(days=i) for i in range((end - start).days + 1)]

	employees = get_employees(f, start)
	if not employees:
		return get_columns(days), []
	emp_ids = [e.name for e in employees]

	attendance = get_attendance(emp_ids, start, end)
	punches = get_checkins(emp_ids, start, end)
	holidays = get_holidays(employees, start, end)
	shifts = get_shift_times()
	# Defaults copy the biometric machine's "FS" shift: 09:30-18:29, late only after 15 min,
	# early only when leaving more than 10 min before the end (checked against the Oct-2026 report).
	default_shift = (to_td(f.shift_start or "09:30:00"), to_td(f.shift_end or "18:29:00"))
	late_grace = timedelta(minutes=int(f.late_grace if f.late_grace not in (None, "") else 15))
	early_grace = timedelta(minutes=int(f.early_grace if f.early_grace not in (None, "") else 10))

	data = []
	for e in employees:
		rows = {r: {"employee": "", "detail": _(r), "row_type": r} for r in DETAIL_ROWS}
		rows["Status"]["employee"] = f"{e.employee_name} ({e.name})"
		rows["Status"]["employee_id"] = e.name
		totals = {"P": 0, "½P": 0, "A": 0, "L": 0, "WO": 0, "hours": 0.0, "late_days": 0, "early_days": 0}
		# Day columns that are a weekly off / holiday for this employee (whatever the status), used by
		# the Excel download to shade the whole column yellow like the biometric sheet. Not a column.
		rows["Status"]["_off_days"] = []
		rows["Status"]["employee_name"] = e.employee_name

		for d in days:
			key = d.strftime("d%d")
			att = attendance.get((e.name, d))
			hol = holidays.get(e.holiday_list or e.company_holiday_list, {}).get(d)
			code = ""
			if hol is not None:
				rows["Status"]["_off_days"].append(key)
			if att:
				code = STATUS_CODE.get(att.status, att.status)
				# Worked on a weekly off / holiday, like the biometric "WOP"
				if hol is not None and code in ("P", "½P"):
					code = "WOP" if code == "P" else "WO½P"
			elif hol is not None:
				code = "WO" if hol else "H"
			elif str(d) <= today():
				code = "-"
			rows["Status"][key] = code
			for c in ("P", "½P", "A", "L"):
				if code == c:
					totals[c] += 1
			if code.startswith("WO") or code == "H":
				totals["WO"] += 1

			# In / out: Attendance times first, else first and last checkin of the day
			t_in = att.in_time if att else None
			t_out = att.out_time if att else None
			if not t_in and (e.name, d) in punches:
				logs = punches[(e.name, d)]
				t_in = logs[0]
				t_out = logs[-1] if len(logs) > 1 else None
			if not t_in:
				continue
			t_in, t_out = get_datetime(t_in), get_datetime(t_out) if t_out else None
			rows["In Time"][key] = t_in.strftime("%H:%M")
			if t_out:
				rows["Out Time"][key] = t_out.strftime("%H:%M")
				worked = t_out - t_in
				rows["Duration"][key] = hm(worked)
				totals["hours"] += worked.total_seconds() / 3600

			shift_name = att.shift if (att and att.shift in shifts) else e.default_shift
			s_start, s_end, s_late, s_early = shifts.get(shift_name) or (*default_shift, None, None)
			shift_in = datetime.combine(d, datetime.min.time()) + s_start
			shift_out = datetime.combine(d, datetime.min.time()) + s_end
			if s_end <= s_start:  # night shift ends the next day
				shift_out += timedelta(days=1)
			# Grace: the Shift Type's own grace when it has one, else the report filters.
			# Like the machine, Late By counts from the shift start once the grace is crossed.
			if not code.startswith("WO") and code != "H":
				if t_in - shift_in > (s_late or late_grace):
					rows["Late By"][key] = hm(t_in - shift_in)
					totals["late_days"] += 1
				if t_out and shift_out - t_out > (s_early or early_grace):
					rows["Early By"][key] = hm(shift_out - t_out)
					totals["early_days"] += 1

		rows["Status"].update({
			"present": totals["P"] + totals["½P"] * 0.5,
			"absent": totals["A"] + totals["½P"] * 0.5,
			"leave": totals["L"],
			"weekly_off": totals["WO"],
			"work_hours": hm(timedelta(hours=totals["hours"])),
			"late_days": totals["late_days"],
			"_early_days": totals["early_days"],  # Excel summary line only
		})
		data.extend(rows[r] for r in DETAIL_ROWS)

	return get_columns(days), data


def get_columns(days):
	cols = [
		{"fieldname": "employee", "label": _("Employee"), "fieldtype": "Data", "width": 210},
		{"fieldname": "detail", "label": _("Details"), "fieldtype": "Data", "width": 80},
	]
	for d in days:
		cols.append({"fieldname": d.strftime("d%d"), "label": f"{d.day} {d.strftime('%a')[:2]}", "fieldtype": "Data", "width": 58})
	cols += [
		{"fieldname": "present", "label": _("Present"), "fieldtype": "Float", "precision": 1, "width": 75},
		{"fieldname": "absent", "label": _("Absent"), "fieldtype": "Float", "precision": 1, "width": 75},
		{"fieldname": "leave", "label": _("Leave"), "fieldtype": "Int", "width": 60},
		{"fieldname": "weekly_off", "label": _("Weekly Off"), "fieldtype": "Int", "width": 85},
		{"fieldname": "work_hours", "label": _("Work Hrs"), "fieldtype": "Data", "width": 80},
		{"fieldname": "late_days", "label": _("Late Days"), "fieldtype": "Int", "width": 80},
	]
	return cols


def get_employees(f, start):
	cond = {"status": ["!=", "Inactive"]}
	for k in ("company", "department", "branch"):
		if f.get(k):
			cond[k] = f.get(k)
	if f.employee:
		cond["name"] = f.employee
	emps = frappe.get_all("Employee", filters=cond, order_by="employee_name",
		fields=["name", "employee_name", "company", "holiday_list", "default_shift", "relieving_date", "status"])
	# Left employees are shown only for months they were still working in
	emps = [e for e in emps if e.status != "Left" or (e.relieving_date and getdate(e.relieving_date) >= start)]
	company_hl = {c: frappe.get_cached_value("Company", c, "default_holiday_list") for c in {e.company for e in emps}}
	for e in emps:
		e.company_holiday_list = company_hl.get(e.company)
	return emps


def get_attendance(emp_ids, start, end):
	rows = frappe.get_all("Attendance",
		filters={"employee": ["in", emp_ids], "attendance_date": ["between", [start, end]], "docstatus": 1},
		fields=["employee", "attendance_date", "status", "in_time", "out_time", "shift"])
	return {(r.employee, getdate(r.attendance_date)): r for r in rows}


def get_checkins(emp_ids, start, end):
	rows = frappe.get_all("Employee Checkin",
		filters={"employee": ["in", emp_ids], "time": ["between", [f"{start} 00:00:00", f"{end} 23:59:59"]]},
		fields=["employee", "time"], order_by="time")
	out = {}
	for r in rows:
		out.setdefault((r.employee, getdate(r.time)), []).append(r.time)
	return out


def get_holidays(employees, start, end):
	"""{holiday_list: {date: weekly_off (1/0)}}"""
	lists = {e.holiday_list or e.company_holiday_list for e in employees} - {None, ""}
	out = {}
	for hl in lists:
		out[hl] = {getdate(h.holiday_date): h.weekly_off for h in frappe.get_all("Holiday",
			filters={"parent": hl, "holiday_date": ["between", [start, end]]}, fields=["holiday_date", "weekly_off"])}
		# Fallback (2026-11-23): "RKBG Holiday List 2026" has Weekly Off = Sunday but its Sunday dates were
		# never added. When a month has no holidays at all, show the list's weekly-off day as WO here
		# (display only; the Holiday List itself is not changed).
		if not out[hl]:
			wday = frappe.get_cached_value("Holiday List", hl, "weekly_off")
			if wday in calendar.day_name:
				idx = list(calendar.day_name).index(wday)
				out[hl] = {start + timedelta(days=i): 1 for i in range((end - start).days + 1)
					if (start + timedelta(days=i)).weekday() == idx}
	return out


def get_shift_times():
	"""{shift: (start, end, late grace or None, early grace or None)}"""
	out = {}
	for s in frappe.get_all("Shift Type", fields=["name", "start_time", "end_time", "enable_late_entry_marking",
		"late_entry_grace_period", "enable_early_exit_marking", "early_exit_grace_period"]):
		late = timedelta(minutes=s.late_entry_grace_period) if s.enable_late_entry_marking and s.late_entry_grace_period else None
		early = timedelta(minutes=s.early_exit_grace_period) if s.enable_early_exit_marking and s.early_exit_grace_period else None
		out[s.name] = (to_td(s.start_time), to_td(s.end_time), late, early)
	return out


# ---------------------------------------------------------------------------------------------
# Coloured Excel download (2026-11-23, user: "when I export I want proper table colours").
# Frappe's standard Export writes plain values only, so the report's "Download Excel (Coloured)"
# button calls this method and builds the file with openpyxl (already part of Frappe).
# Layout copies the biometric "Monthly Status Report (Detailed Work Duration)" sheet (user sent
# a screenshot, same day): title, one "Days" header row, then per employee an
# "Employee: code : Name" line with the month summary, and a block of Status / InTime /
# OutTime / Duration / Late By / Early By rows with dotted inner lines and a thick outer border.
# Colours as on the sheet: A = red, WO = blue on the Status row; the employee's weekly-off /
# holiday columns are yellow in the rows below.
# ---------------------------------------------------------------------------------------------
XL_RED, XL_BLUE, XL_YELLOW = "FF0000", "5BC8F5", "FFFF00"
XL_LABELS = {"Status": "Status", "In Time": "InTime", "Out Time": "OutTime", "Duration": "Duration",
	"Late By": "Late By", "Early By": "Early By"}


@frappe.whitelist()
def download_xlsx(filters=None):
	"""Builds the biometric-style .xlsx of the current filters and sends it as a download."""
	from io import BytesIO

	from openpyxl import Workbook
	from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
	from openpyxl.utils import get_column_letter

	# Same roles as the report itself (Report > Roles)
	frappe.only_for(["System Manager", "HR Manager", "HR User"])
	f = frappe._dict(frappe.parse_json(filters) if isinstance(filters, str) else (filters or {}))
	columns, data = execute(f)
	days = [c for c in columns if c["fieldname"][:1] == "d" and c["fieldname"][1:].isdigit()]
	last = len(days) + 1  # column A = labels, B.. = days
	has_code = frappe.get_meta("Employee").has_field("custom_employee_code")

	wb = Workbook()
	ws = wb.active
	ws.title = f"{(f.month or '')[:3]} {f.year or ''}".strip() or "Attendance"
	ws.sheet_view.showGridLines = False
	dot = Side(style="dotted", color="000000")
	thick = Side(style="medium", color="000000")
	fill = lambda c: PatternFill("solid", start_color=c, end_color=c)
	base = Font(name="Arial", size=8)
	bold = Font(name="Arial", size=8, bold=True)

	def box(r1, r2, c1, c2, inner=dot):
		"""Dotted inner lines, thick outer border."""
		for r in range(r1, r2 + 1):
			for c in range(c1, c2 + 1):
				ws.cell(r, c).border = Border(
					left=thick if c == c1 else inner, right=thick if c == c2 else inner,
					top=thick if r == r1 else inner, bottom=thick if r == r2 else inner)

	# Title block
	ws.cell(1, 1, "Monthly Status Report (Detailed Work Duration)").font = Font(name="Arial", size=12, bold=True)
	if days:
		year = int(f.year or getdate().year)
		month = MONTHS.index(f.month) + 1 if f.month in MONTHS else getdate().month
		ws.cell(2, 1, f"{date(year, month, 1):%b %d %Y} To {date(year, month, len(days)):%b %d %Y}").font = base
	ws.cell(3, 1, "Company:").font = bold
	ws.cell(3, 2, f.company or "All").font = base
	ws.cell(3, last, f"Printed On : {datetime.now():%b %d %Y %H:%M}").font = base
	ws.cell(3, last).alignment = Alignment(horizontal="right")

	# Days header
	HR = 5
	ws.cell(HR, 1, "Days").font = bold
	for i, c in enumerate(days, 2):
		ws.cell(HR, i, c["label"]).font = base
	box(HR, HR, 1, last, inner=Side(style="thin", color="000000"))

	r = HR + 1
	per = len(DETAIL_ROWS)
	for start in range(0, len(data), per):
		block = {row["row_type"]: row for row in data[start:start + per]}
		st = block["Status"]
		off = set(st.get("_off_days") or [])
		code = frappe.db.get_value("Employee", st.get("employee_id"), "custom_employee_code") if has_code else None

		# "Employee:" line with the month summary
		r += 1
		ws.cell(r, 1, "Employee:").font = bold
		ws.cell(r, 2, f"{code or st.get('employee_id')} : {st.get('employee_name') or ''}").font = base
		summary = (f"Total Work Duration: {st.get('work_hours')} Hrs.  Present: {st.get('present'):g}  "
			f"Absent: {st.get('absent'):g}  WeeklyOff: {st.get('weekly_off')}  Leaves Taken: {st.get('leave')}  "
			f"Late By Days: {st.get('late_days')}  Early going By Days: {st.get('_early_days', 0)}")
		ws.cell(r, 8, summary).font = base
		ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
		ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=last)
		ws.cell(r, 8).alignment = Alignment(wrap_text=True, vertical="center")
		ws.row_dimensions[r].height = 24
		r += 1

		# Detail block
		top = r
		for rt in DETAIL_ROWS:
			row = block[rt]
			ws.cell(r, 1, XL_LABELS[rt]).font = base
			for i, c in enumerate(days, 2):
				fn = c["fieldname"]
				v = row.get(fn)
				cell = ws.cell(r, i, v if v not in (None, "", "-") else None)
				cell.font = base
				if rt == "Status":
					s = v or ""
					if s == "A":
						cell.fill = fill(XL_RED)
					elif s.startswith("WO") or s == "H":
						cell.fill = fill(XL_BLUE)
				elif fn in off:
					cell.fill = fill(XL_YELLOW)
			r += 1
		box(top, r - 1, 1, last)

	ws.column_dimensions["A"].width = 9
	for i in range(2, last + 1):
		ws.column_dimensions[get_column_letter(i)].width = 5.6
	ws.freeze_panes = ws.cell(HR + 1, 2)
	ws.page_setup.orientation = "landscape"
	ws.page_setup.fitToWidth = 1
	ws.page_setup.fitToHeight = 0
	ws.sheet_properties.pageSetUpPr.fitToPage = True
	ws.print_title_rows = f"{HR}:{HR}"

	buf = BytesIO()
	wb.save(buf)
	frappe.response["filename"] = f"Attendance {f.month} {f.year}.xlsx"
	frappe.response["filecontent"] = buf.getvalue()
	frappe.response["type"] = "binary"


def to_td(v):
	if isinstance(v, timedelta):
		return v
	h, m, *s = [int(x) for x in str(v).split(":")]
	return timedelta(hours=h, minutes=m, seconds=s[0] if s else 0)


def hm(td):
	mins = int(round(td.total_seconds() / 60))
	return f"{mins // 60}:{mins % 60:02d}"
