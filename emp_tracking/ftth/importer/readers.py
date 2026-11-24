# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt
"""Read the email export files (zip / xlsx / kmz) into plain Python records.

Recognised sheet layouts (detected from the header row, wherever the sheet sits):
  * Master Data       - old 49-column per-WO tracking sheet
  * Monthly FTTH      - "Sep 2026 FTTH" style cumulative register
  * Mail Approval     - feeder approvals from Planning
  * Airtel Format     - site lists (Site Name / GIS / partner / fiber length)
  * Node details      - Site Name / GIS / B Location
  * Link register     - Link ID / Company / Link Type / A - End / B - End
  * Billing (HOTO)    - Link ID / HOTO NO / HOTO Date
No frappe imports here: `run.py` writes the records into the database.

Change log
  2026-10-29  Billing rows without a Link ID are kept in `wo_billing` (run.py puts them on the
              work order with the same building name and GIS) instead of being dropped.
"""

import os
import re
import xml.etree.ElementTree as ET
import zipfile

from emp_tracking.ftth.logic import (
	as_text_number,
	classify_issue,
	clean,
	excel_date,
	fiber_type,
	line_length_m,
	norm,
	parse_wo_number,
	same,
	split_route_name,
	to_float,
	yes,
)

MAX_ZIP_DEPTH = 5
STOP_AFTER_EMPTY_ROWS = 200
MONTHS = {m: i for i, m in enumerate(
	["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

# ------------------------------------------------------------------ header maps (normalised header -> key)
MASTER = {
	"company": "company", "months": "months", "woreceivedmode": "mode", "woreceiveddate": "wo_recv",
	"wo": "wo", "wodate": "wo_date", "hphomepasss": "hp", "hphomepass": "hp", "hp": "hp",
	"endlocationname": "end", "endlocationlatlong": "end_ll", "ibdteam": "ibd", "ibdteamno": "ibd_no",
	"custname": "cust", "custcontactno": "cust_no", "gis": "gis", "area": "area",
	"companyenggname": "engg", "companyenggno": "engg_no",
	"surveystartlocationreceivedbyplanning": "bend",
	"surveystartlocationreceivedbyplanninglatlong": "bend_ll",
	"surveydistancereceivedbyplanning": "d_plan", "manager": "manager", "team": "team",
	"areamanager": "am", "areamanagerno": "am_no", "surveyaenddonebyareamanager": "a_end_sv",
	"surveybenddonebyareamanager": "b_end_sv", "surveydistancedonebyareamanager": "d_survey",
	"bendissueordistanceissue": "bissue", "newbendlocation": "new_bend",
	"surveydistancefromnewbend": "d_newb", "mailsendtoplanningsnapanddate": "mail_dt",
	"approvaldateandsnapbyplanningordeploymentteam": "appr_dt", "fiberteam": "fiber_team",
	"fiberidsnap": "fiber_id", "fiberreadingaendsnap": "fib_a", "fiberreadingbendsnap": "fib_b",
	"totalroutetentativevideo": "video", "splicingteamrequiredno": "splice_team",
	"splicername": "splicer", "assistancetsplicername": "asst", "assistantsplicername": "asst",
	"powersnaporotdrsnaporpigtalsnaporsplicingcompletedsnapaend": "snap_a",
	"powersnaporotdrsnaporpigtalsnaporsplicingcompletedsnapbend": "snap_b",
	"finaldistance": "d_final", "distancesharedtoairtel": "d_shared", "kmz": "kmz",
	"rfsstatusanddate": "rfs", "evisionslinkid": "evis",
}
MONTHLY = {
	"linkid": "link_id", "city": "city", "company": "company", "months": "months",
	"comunicationmode": "mode", "communicationmode": "mode", "comunicationdate": "comm_date",
	"communicationdate": "comm_date", "wo": "wo", "wodate": "wo_date", "hp": "hp", "uniqueid": "unique_id",
	"endlocationlatlong": "end_ll", "endlocationname": "end", "gis": "gis", "area": "area",
	"companyengg": "engg", "surveystartlocation": "bend", "surveydistance": "d_plan",
	"startlocationpermissionstatus": "start_perm", "startlocationname": "start_name", "sitelatlong": "bend_ll",
	"distanace": "d_final", "distance": "d_final", "fibertype": "fiber_type", "evision": "evis_dist",
	"team": "vendor", "vendorname": "vendor", "areamanager": "am", "mailortelegramdat": "mail_note",
	"siteapproveddate": "approved", "workcompleteddate": "completed", "hodate": "ho", "fiberroute": "fiber_route",
	"splicer1": "splicer1", "rider1": "rider1", "splicer2": "splicer2", "rider2": "rider2", "remark": "remark",
	"suggestionforfuture": "suggestion", "spervisoravilable": "site_status", "supervisoravailable": "site_status",
	"manger": "manager", "manager": "manager", "reworkrequireddate": "rework",
}
APPROVAL = {
	"maildate": "mail_dt", "approvedate": "appr_dt", "uniqueid": "unique_id", "clustername": "cluster",
	"woorder": "wo", "wohp": "hp", "buildingnamepointa": "end", "feederbpointlocation": "bend",
	"feederdistance": "d_feeder", "nameofpartner": "partner", "rsu": "rsu", "area": "area", "pincode": "pincode",
	"approvedlength": "approved_length", "requiredlength": "required_length", "kmzyesno": "kmz",
	"reasonfordevotion": "reason", "reasonfordeviation": "reason", "nearestodfjc": "nearest_odf",
	"feedertypeb2bmixpole": "feeder_type",
}
SITES = {
	"sitename": "site_name", "gis": "gis", "blocation": "b_location", "area": "area", "engineer": "engineer",
	"ip1partner": "partner", "priority": "priority", "ip1fiberlenght12f24f": "fiber_length",
	"ip1fiberlength12f24f": "fiber_length", "ip1fibertype12f24f": "fiber_type",
	"ip1fiberroutestartpoint": "route_start", "ip1fiberrouteendpoint": "route_end",
}
LINKS = {
	"date": "link_date", "linkid": "link_id", "company": "company", "linktype": "link_type",
	"vendorname": "vendor", "supervisor": "supervisor", "aend": "a_end", "bend": "b_end", "area": "area",
	"distance": "distance", "installationdate": "installation_date",
}
BILLING = {
	"year": "year", "sectionname": "section_name", "giscode": "gis", "sitersfmonth": "site_rfs_month",
	"sitersmonth": "site_rfs_month", "siterfsmonth": "site_rfs_month", "currentlayingfibertype": "fiber_type",
	"hotodate": "hoto_date", "hotono": "hoto_no", "linkid": "link_id",
}


# keys that keep their Excel type (numbers / dates); everything else is read as text
RAW_KEYS = {
	"wo_recv", "wo_date", "hp", "d_plan", "d_survey", "d_newb", "d_final", "d_shared", "fib_a", "fib_b",
	"mail_dt", "appr_dt", "rfs", "months", "comm_date", "approved", "completed", "ho", "rework",
	"approved_length", "required_length", "d_feeder", "fiber_length", "link_date", "distance",
	"installation_date", "hoto_date", "site_rfs_month", "splice_team", "evis_dist",
}


def detect(header_norm):
	h = set(header_norm)
	if {"hotono", "linkid"} <= h:
		return "billing", BILLING
	if {"linkid", "aend", "bend"} <= h and ("linktype" in h or "installationdate" in h):
		return "links", LINKS
	if "woorder" in h and ("approvedlength" in h or "requiredlength" in h):
		return "approval", APPROVAL
	if {"suggestionforfuture", "endlocationlatlong"} <= h or {"comunicationmode", "endlocationlatlong"} <= h:
		return "monthly", MONTHLY
	if sum(1 for x in h if x in MASTER) >= 8 and "wo" in h:
		return "master", MASTER
	if {"sitename", "gis"} <= h:
		return "sites", SITES
	return None, None


class ImportData:
	def __init__(self):
		self.work_orders = {}  # key -> dict with FTTH Work Order fieldnames
		self.approvals = []  # [(keys, fields)] - applied to work orders
		self.gis = {}
		self.ibd_teams = set()
		self.fiber_teams = set()
		self.staff = {}  # name -> {"staff_type", "contact_no"}
		self.settings = {}
		self.routes = []
		self.points = []
		self.sites = {}
		self.links = {}  # link_id -> dict
		self.hotos = {}  # link_id -> [dict]
		self.wo_billing = []  # 2026-10-29: billing rows without a Link ID -> matched to work orders by name
		self.issues = []
		self.files_read = 0
		self.sheets = []  # (label, kind, rows)
		self._bad_cells = {}

	def issue(self, wo_id, ref, text):
		self.issues.append((wo_id or "", ref or "", text))

	def bad_cell(self, column, value):
		k = column
		self._bad_cells.setdefault(k, [0, value])[0] += 1

	def finish(self):
		for column, (count, example) in self._bad_cells.items():
			self.issue("", f"column '{column}'", f"{count} cells were not valid values and were ignored (e.g. '{str(example)[:40]}') - columns may be shifted in the sheet")


# ------------------------------------------------------------------ unpack
def collect_files(path, workdir):
	out, counter = [], [0]

	def unzip(zip_path, label, depth):
		if depth > MAX_ZIP_DEPTH:
			return
		counter[0] += 1
		dest = os.path.join(workdir, f"z{counter[0]}")
		os.makedirs(dest)
		with zipfile.ZipFile(zip_path) as z:
			for m in z.infolist():
				name = m.filename.replace("\\", "/")
				if m.is_dir() or name.startswith("/") or ".." in name.split("/"):
					continue  # zip-slip guard
				base = os.path.basename(name)
				if base.startswith(("~$", "._")) or "__MACOSX" in name:
					continue
				z.extract(m, dest)
		walk(dest, label, depth + 1)

	def handle(p, label, depth):
		low = p.lower()
		lab = f"{label} › {os.path.basename(p)}" if label else os.path.basename(p)
		if low.endswith(".zip"):
			unzip(p, lab, depth)
		elif low.endswith((".xlsx", ".xlsm")):
			out.append(("xlsx", p, lab))
		elif low.endswith((".kmz", ".kml")):
			out.append(("kmz", p, lab))
		elif low.endswith((".xlsb", ".xls")):
			out.append(("unsupported", p, lab))

	def walk(d, label, depth):
		for root, _dirs, files in os.walk(d):
			for f in sorted(files):
				handle(os.path.join(root, f), label, depth)

	if os.path.isdir(path):
		walk(path, "", 0)
	else:
		handle(path, "", 0)
	return out


def file_order(label):
	"""Sort monthly sheets oldest -> newest so newer values win; others keep name order."""
	name = label.lower().split("›")[-1]
	y = re.search(r"20\d\d", name)
	m = next((v for k, v in MONTHS.items() if re.search(rf"\b{k}", name)), 0)
	return (int(y.group(0)) if y else 0, m, name)


def read_all(path, workdir):
	data = ImportData()
	files = collect_files(path, workdir)
	for kind, p, label in sorted(files, key=lambda f: (f[0] != "xlsx", file_order(f[2]))):
		data.files_read += 1
		if kind == "xlsx":
			read_xlsx(p, label, data)
		elif kind == "kmz":
			read_kmz(p, label, data)
		else:
			data.issue("", label, "Excel binary (.xlsb/.xls) files can't be read - open in Excel and Save As .xlsx")
	apply_approvals(data)
	data.finish()
	return data


# ------------------------------------------------------------------ excel
def iter_sheet(ws):
	"""Yield (header_index, header, rows-iterator) for a worksheet, streaming."""
	rows = ws.iter_rows(values_only=True)
	buffered = []
	for _ in range(10):
		try:
			buffered.append(next(rows))
		except StopIteration:
			break
	for i, r in enumerate(buffered):
		hdr = [norm(c) for c in (r or [])]
		kind, mapping = detect(hdr)
		if kind:
			def body(start=i + 1):
				empty = 0
				for row in buffered[start:]:
					yield row
				for row in rows:
					if not row or all(c in (None, "") for c in row):
						empty += 1
						if empty >= STOP_AFTER_EMPTY_ROWS:
							return
						continue
					empty = 0
					yield row
			return kind, mapping, r, body()
	return None, None, None, None


def read_xlsx(path, label, data):
	import openpyxl  # installed with frappe

	try:
		wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
	except Exception as e:
		data.issue("", label, f"Could not open workbook: {e}")
		return
	for ws in wb.worksheets:
		kind, mapping, header, body = iter_sheet(ws)
		if not kind:
			continue
		idx = {}
		for j, h in enumerate(header):
			k = mapping.get(norm(h))
			if k and k not in idx:
				idx[k] = j
		sheet_label = f"{label} › {ws.title}"
		n = 0
		for row in body:
			def g(k, row=row):
				j = idx.get(k)
				v = clean(row[j]) if j is not None and j < len(row) else None
				if v is not None and k not in RAW_KEYS and not isinstance(v, str):
					v = as_text_number(v)
				return v
			reader = {"master": _master_row, "monthly": _monthly_row, "approval": _approval_row,
					  "sites": _site_row, "links": _link_row, "billing": _billing_row}[kind]
			if reader(g, sheet_label, data):
				n += 1
		data.sheets.append((sheet_label, kind, n))
	wb.close()


# ------------------------------------------------------------------ helpers
def _date(v, data=None, column=None):
	if v in (None, ""):
		return None
	d = excel_date(v)
	if d is None and data is not None and column:
		data.bad_cell(column, v)
	return d


def _num(v, data=None, column=None):
	if v in (None, "", "`"):
		return None
	f = to_float(v)
	if f is None and data is not None and column:
		data.bad_cell(column, v)
	return f


def _ll(v):
	"""Keep only things that look like 'lat, long'."""
	return v if v and re.search(r"-?\d{1,2}\.\d+\D+-?\d{2,3}\.\d+", str(v)) else None


def wo_key(rec):
	if rec.get("wo_id"):
		return f"wo:{rec['wo_id']}"
	if rec.get("unique_id"):
		return f"uid:{rec['unique_id'].upper()}"
	return f"site:{norm(rec.get('end_location'))}|{norm(rec.get('gis'))}"


def merge_wo(data, rec):
	"""Later files win for non-empty values (monthly sheets are processed oldest -> newest)."""
	key = wo_key(rec)
	if not rec.get("end_location"):
		return False
	cur = data.work_orders.get(key)
	if cur is None:
		data.work_orders[key] = rec
	else:
		for k, v in rec.items():
			if v not in (None, "", 0) or k not in cur:
				cur[k] = v
	return True


STAFF_RANK = ["Manager", "Area Manager", "Supervisor", "Airtel Engineer", "Splicer", "Assistant Splicer", "Rider", "Other"]


def add_staff(data, name, kind, contact=None):
	"""One person list for everyone; first role seen wins, numbers are filled when known."""
	name = clean(name)
	if not name or len(name) < 3 or re.search(r"\d", name):
		return None
	cur = data.staff.setdefault(name, {"staff_type": kind, "contact_no": None})
	if STAFF_RANK.index(kind) < STAFF_RANK.index(cur["staff_type"]):
		cur["staff_type"] = kind  # e.g. someone seen as Supervisor in the link register is an Area Manager
	if contact and not cur["contact_no"]:
		cur["contact_no"] = contact
	return name


def _masters(data, gis_row, ibd=None, fiber_team=None, splicers=()):
	gis = gis_row.get("gis_code")
	add_staff(data, gis_row.get("area_manager"), "Area Manager", gis_row.get("area_manager_no"))
	add_staff(data, gis_row.get("manager"), "Manager")
	add_staff(data, gis_row.get("company_engineer"), "Airtel Engineer", gis_row.get("company_engineer_no"))
	if gis and gis not in data.gis:
		data.gis[gis] = {k: v for k, v in gis_row.items() if v}
	elif gis:
		for k, v in gis_row.items():
			if v and not data.gis[gis].get(k):
				data.gis[gis][k] = v
	if ibd:
		data.ibd_teams.add(ibd)
	if fiber_team:
		data.fiber_teams.add(fiber_team)
	for name, kind in splicers:
		add_staff(data, name, kind)


def _clean_gis(v):
	v = clean(v)
	if not v:
		return None
	v = re.sub(r"[^A-Za-z0-9]", "", str(v)).upper()
	return v if 2 <= len(v) <= 8 else None


# ------------------------------------------------------------------ old master sheet
def _master_row(g, label, data):
	wo = g("wo")
	if not wo:
		return False
	info = parse_wo_number(wo)
	wid = info["wo_id"]
	end = g("end")
	rec = {
		"wo_number": wo, "wo_id": wid, "wo_received_date": _date(g("wo_recv"), data, "WO received date"),
		"gis": _clean_gis(g("gis")), "hp": int(_num(g("hp")) or 0) or None, "end_location": end,
		"end_lat_long": _ll(g("end_ll")), "b_end": g("bend"), "b_end_lat_long": _ll(g("bend_ll")),
		"fiber_team": g("fiber_team"), "fiber_id": as_text_number(g("fiber_id")),
		"fiber_reading_a": _num(g("fib_a")), "fiber_reading_b": _num(g("fib_b")),
		"splicer": g("splicer"), "assistant_splicer": g("asst"),
		"route_video_done": yes(g("video")), "kmz_done": yes(g("kmz")),
		"mail_to_planning_date": _date(g("mail_dt")), "approval_date": _date(g("appr_dt")),
		"rfs_date": _date(g("rfs"), data, "RFS Status and Date"), "evisions_link_id": as_text_number(g("evis")),
		"b_end_issue": yes(g("bissue")), "imported_from": label,
		"communication_mode": g("mode"),
	}
	ibd = g("ibd")
	if ibd and "/" in ibd:
		data.issue(wid, end, "IBD Team cell contained a WO number instead of a team name - left blank, please fill")
		ibd = None
	elif ibd and re.match(r"(?i)^hi\s+", ibd):
		ibd = re.sub(r"(?i)^hi\s+", "", ibd)
		data.issue(wid, end, "IBD Team had a typing error ('Hi …') - corrected")
	rec["ibd_team"] = ibd
	rec["splicing_snaps_done"] = 1 if (yes(g("snap_a")) and yes(g("snap_b"))) else 0
	if g("a_end_sv") and not same(g("a_end_sv"), end):
		data.issue(wid, end, f"Survey A End '{g('a_end_sv')}' differs from End Location - kept End Location")
	bsv = g("b_end_sv")
	if g("new_bend"):
		rec["new_b_end"] = g("new_bend")
	elif bsv and not same(bsv, rec["b_end"]):
		rec["new_b_end"] = bsv
		if not rec["b_end_issue"]:
			data.issue(wid, end, f"B End changed in survey ('{rec['b_end']}' → '{bsv}') but 'B End Issue' says No - moved to New B End")
	dp = _num(g("d_plan"))
	ds = _num(g("d_newb")) or _num(g("d_survey"))
	df, dsh = _num(g("d_final")), _num(g("d_shared"))
	s_eff = ds if ds is not None else dp
	f_eff = df if df is not None else s_eff
	rec["planning_distance"] = dp
	rec["survey_distance"] = ds if ds is not None and ds != dp else None
	rec["final_distance"] = df if df is not None and df != s_eff else None
	rec["distance_shared"] = dsh if dsh is not None and dsh != f_eff else None
	merge_wo(data, rec)
	_masters(
		data,
		{"gis_code": rec["gis"], "area": g("area"), "company_engineer": g("engg"),
		 "company_engineer_no": as_text_number(g("engg_no")), "manager": g("manager"), "team": g("team"),
		 "area_manager": g("am"), "area_manager_no": as_text_number(g("am_no"))},
		ibd, rec["fiber_team"], ((rec["splicer"], "Splicer"), (rec["assistant_splicer"], "Assistant Splicer")),
	)
	for key, val in (("company", g("company")), ("wo_received_mode", g("mode")),
					 ("customer_name", g("cust")), ("customer_contact_no", as_text_number(g("cust_no"))),
					 ("ibd_contact_no", as_text_number(g("ibd_no"))),
					 ("splicing_team_size", int(_num(g("splice_team")) or 0) or None)):
		if val:
			data.settings.setdefault(key, val)
	return True


# ------------------------------------------------------------------ monthly FTTH register
def _txt(v):
	return None if v is None else str(v)


def _name(v):
	"""A person's name - reject numbers / coordinates that slid into the column."""
	v = _txt(v)
	return v if v and not re.search(r"\d", v) else None


def _monthly_row(g0, label, data):
	def g(k):
		v = g0(k)
		return v if k in ("comm_date", "approved", "completed", "ho", "rework", "hp", "d_plan", "d_final") else _txt(v)

	end = g("end")
	if not end:
		return False
	wo = g("wo")
	info = parse_wo_number(wo) if wo and "/" in str(wo) else {"wo_id": None}
	uid = g("unique_id")
	uid = uid if uid and re.match(r"(?i)^(ROM)?PUN\d+$", str(uid)) else None
	mode = g("mode")
	mode = "Mail" if mode and "mail" in mode.lower() else (mode if mode in ("Telegram", "WhatsApp", "Phone") else ("Other" if mode else None))
	remark, suggestion = g("remark"), g("suggestion")
	site_status = g("site_status")
	site_status = site_status if site_status in ("Clear Site", "Issue Site") else None
	d_plan, d_final = _num(g("d_plan"), data, "Survey Distance"), _num(g("d_final"), data, "Distanace")
	rec = {
		"wo_number": wo if info["wo_id"] else None, "wo_id": info["wo_id"], "unique_id": uid,
		"city": g("city") if g("city") and len(str(g("city"))) < 30 and not re.search(r"\d", str(g("city"))) else None,
		"communication_mode": mode, "wo_received_date": _date(g("comm_date"), data, "Comunication date"),
		"hp": int(_num(g("hp"), data, "HP") or 0) or None,
		"end_location": end, "end_lat_long": _ll(g("end_ll")), "gis": _clean_gis(g("gis")),
		"b_end": g("start_name") or g("bend"), "b_end_lat_long": _ll(g("bend_ll")),
		"planning_distance": d_plan,
		"final_distance": d_final if d_final and d_final != d_plan else None,
		"fiber_type": fiber_type(g("fiber_type")), "ibd_team": _name(g("vendor")) or g("vendor"),
		"approval_date": _date(g("approved"), data, "Site Approved Date"),
		"work_completed_date": _date(g("completed"), data, "Work Completed Date"),
		"ho_date": _date(g("ho"), data, "HO Date"),
		"rework_required_date": _date(g("rework"), data, "Re-work Required Date"),
		"splicer": _name(g("splicer1")),
		"splicer_2": _name(g("splicer2")),
		"rider_1": _name(g("rider1")),
		"rider_2": _name(g("rider2")),
		"site_status": site_status, "issue_type": classify_issue(suggestion, remark),
		"issue_detail": "\n".join(x for x in (remark, g("mail_note"), g("start_perm")) if x) or None,
		"next_action": (suggestion or "")[:255] or None,
		"evisions_link_id": as_text_number(g("link_id")) if g("link_id") and re.fullmatch(r"\d{6,}", str(as_text_number(g("link_id")))) else None,
		"imported_from": label,
	}
	merge_wo(data, rec)
	_masters(
		data,
		{"gis_code": rec["gis"], "area": g("area"), "company_engineer": g("engg"), "manager": g("manager"),
		 "area_manager": g("am")},
		rec["ibd_team"], None, ((rec["splicer"], "Splicer"), (rec["splicer_2"], "Splicer"),
								(rec["rider_1"], "Rider"), (rec["rider_2"], "Rider")),
	)
	if g("company"):
		data.settings.setdefault("company", g("company"))
	return True


# ------------------------------------------------------------------ mail approval
def _approval_row(g, label, data):
	wo = g("wo")
	info = parse_wo_number(wo) if wo else {"wo_id": None}
	uid = g("unique_id")
	if not (info["wo_id"] or uid):
		return False
	ap = {
		"mail_to_planning_date": _date(g("mail_dt"), data, "Mail Date"),
		"approval_date": _date(g("appr_dt"), data, "Approve Date"),
		"approved_length": _num(g("approved_length")), "required_length": _num(g("required_length")),
		"deviation_reason": g("reason"), "nearest_odf": g("nearest_odf"), "rsu": _clean_gis(g("rsu")),
		"pincode": as_text_number(g("pincode")), "approval_kmz": yes(g("kmz")),
		"feeder_type": next((t for t in ("B2B", "Mix", "Pole", "UG", "OH") if t.lower() in str(g("feeder_type") or "").lower()), None),
		"_end": g("end"), "_wo": wo if info["wo_id"] else None, "_uid": uid, "_label": label,
	}
	keys = ([f"wo:{info['wo_id']}"] if info["wo_id"] else []) + ([f"uid:{uid.upper()}"] if uid else [])
	data.approvals.append((keys, {k: v for k, v in ap.items() if v not in (None, "")}))
	return True


def apply_approvals(data):
	"""Copy approvals onto work orders read in the same import; the rest are applied in the DB."""
	by_uid = {f"uid:{r['unique_id'].upper()}": k for k, r in data.work_orders.items() if r.get("unique_id")}
	left = []
	for keys, ap in data.approvals:  # later sheets come later -> their values win
		target = next((k if k in data.work_orders else by_uid.get(k) for k in keys
					   if k in data.work_orders or k in by_uid), None)
		if target:
			rec = data.work_orders[target]
			for k, v in ap.items():
				if not k.startswith("_"):
					rec[k] = v
		else:
			left.append((keys, ap))
	# keep one entry per key set (the latest)
	latest = {}
	for keys, ap in left:
		latest[tuple(keys)] = (keys, ap)
	data.approvals = list(latest.values())


# ------------------------------------------------------------------ site lists
def _site_row(g, label, data):
	name = g("site_name")
	if not name:
		return False
	gis = _clean_gis(g("gis"))
	key = f"{norm(name)}|{norm(gis)}"
	rec = {"site_name": name, "gis": gis, "b_location": g("b_location"), "area": g("area"),
		   "engineer": g("engineer"), "partner": g("partner"), "priority": as_text_number(g("priority")),
		   "fiber_length": _num(g("fiber_length")), "fiber_type": fiber_type(g("fiber_type")),
		   "route_start": g("route_start"), "route_end": g("route_end"), "source_file": label}
	cur = data.sites.setdefault(key, rec)
	for k, v in rec.items():
		if v and not cur.get(k):
			cur[k] = v
	if gis:
		_masters(data, {"gis_code": gis, "area": g("area"), "company_engineer": g("engineer")})
	return True


# ------------------------------------------------------------------ link register + billing
def _link_id(v):
	s = as_text_number(v)
	return s if s and re.fullmatch(r"\d{6,12}", s) else None


def _link_row(g, label, data):
	lid = _link_id(g("link_id"))
	if not lid:
		return False
	rec = {"link_id": lid, "link_date": _date(g("link_date")), "company": g("company"), "link_type": g("link_type"),
		   "vendor": g("vendor"), "supervisor": add_staff(data, g("supervisor"), "Supervisor"), "a_end": g("a_end"), "b_end": g("b_end"),
		   "area": g("area"), "distance": _num(g("distance")),
		   "installation_date": _date(g("installation_date")), "source_file": label}
	cur = data.links.setdefault(lid, rec)
	for k, v in rec.items():
		if v and not cur.get(k):
			cur[k] = v
	return True


def _billing_row(g, label, data):
	lid = _link_id(g("link_id"))
	h = {"hoto_no": g("hoto_no"), "hoto_date": _date(g("hoto_date")), "year": as_text_number(g("year")),
		 "section_name": g("section_name"), "gis": _clean_gis(g("gis")),
		 "site_rfs_month": _date(g("site_rfs_month")), "fiber_type": g("fiber_type")}
	if not lid:
		# 2026-10-29: recent billing rows have no Link ID yet; keep them for the work order itself
		if not h["section_name"] or not (h["hoto_no"] or h["hoto_date"]):
			return False
		data.wo_billing.append(h)
		return True
	rows = data.hotos.setdefault(lid, [])
	if not any(r["hoto_no"] == h["hoto_no"] and r["hoto_date"] == h["hoto_date"] for r in rows):
		rows.append(h)
	if h["gis"]:
		_masters(data, {"gis_code": h["gis"]})
	return True


# ------------------------------------------------------------------ kmz
def read_kmz(path, label, data):
	try:
		if path.lower().endswith(".kml"):
			with open(path, "rb") as f:
				xml = f.read()
		else:
			with zipfile.ZipFile(path) as z:
				name = next(n for n in z.namelist() if n.lower().endswith(".kml"))
				xml = z.read(name)
		root = ET.fromstring(xml)
	except Exception as e:
		data.issue("", label, f"Could not read KMZ: {e}")
		return

	def tag(e):
		return e.tag.split("}")[-1]

	def text(e, t):
		c = next((c for c in e if tag(c) == t), None)
		return clean(c.text) if c is not None and c.text else None

	def coords(e):
		for c in e.iter():
			if tag(c) == "coordinates" and c.text:
				pts = []
				for tok in c.text.split():
					p = tok.split(",")
					if len(p) >= 2:
						try:
							pts.append((float(p[0]), float(p[1])))
						except ValueError:
							pass
				return pts
		return []

	seen_r, seen_p = set(), set()

	def walk(e, folder):
		for c in e:
			t = tag(c)
			if t in ("Folder", "Document"):
				walk(c, text(c, "name") if t == "Folder" else folder)
			elif t == "Placemark":
				name = (text(c, "name") or "(no name)")[:255]
				for geom in c.iter():
					gt = tag(geom)
					if gt == "LineString":
						pts = coords(geom)
						if len(pts) >= 2:
							length = round(line_length_m(pts), 1)
							key = f"{norm(name)}|{round(length)}"[:255]
							if key not in seen_r:
								seen_r.add(key)
								a, b = split_route_name(name)
								data.routes.append({
									"route_name": name, "a_end": (a or "")[:255], "b_end": (b or "")[:255],
									"length_m": length, "node_folder": (folder or "")[:140],
									"source_file": label[:255], "coords": pts, "dedupe_key": key,
								})
						break
					if gt == "Point":
						pts = coords(geom)
						if pts:
							lon, lat = pts[0]
							key = f"{norm(name)}|{lat:.5f}|{lon:.5f}"[:255]
							if key not in seen_p:
								seen_p.add(key)
								data.points.append({
									"point_name": name, "latitude": round(lat, 7), "longitude": round(lon, 7),
									"node_folder": (folder or "")[:140], "source_file": label[:255], "dedupe_key": key,
								})
						break

	walk(root, None)
