# ---------------------------------------------------------------------------------------------
# Import of the NOC Master Data sheet (complaints April 2025 onwards) into Complaint Information
#
# How this file works
#   Run by hand on the server, not from a patch (the 10 MB sheet is not kept in the app):
#     bench --site <site> execute emp_tracking.noc_complaint_import.preview --kwargs "{'path': '/tmp/noc.xlsx'}"
#     bench --site <site> execute emp_tracking.noc_complaint_import.run --kwargs "{'path': '/tmp/noc.xlsx'}"
#   1. Reads the "MAIN DATA" sheet (one row per complaint; columns by header name).
#   2. Each row becomes one Complaint Information. Its sheet "NO" is kept in noc_sheet_no, so a
#      row already imported is skipped and running it again adds nothing twice.
#   3. Values are translated to the doctype's options (operator, link type, link status, RFO,
#      RFO type); people (TL, Splicer, Rider, Splicer 1, Rider 1) are matched to Employee by
#      name, and MAINTAIN BY to Maintenance Team / Maintenance Vendor. What cannot be matched is
#      written into the remarks, never dropped silently.
#   4. Area: the sheet has none, so it is read from the link name (place names such as BANER,
#      WANWADI). Known spellings map to the existing Area records (e.g. Wanwadi -> Wanowarie);
#      places not in the Area list are created as new Areas (area_code "NOC-<NAME>", not a PIN).
#   5. These are finished, historical complaints: the live-entry rules in the controller (Airtel
#      INC No. required, RFO before closing, link/site checks) are skipped with
#      flags.ignore_validate, but MTTR / SLA / aging are still worked out by the controller's own
#      set_times_and_sla(). The workflow cannot insert straight into "Closed", so each complaint
#      is inserted in the first state and then set to Closed directly.
#
# Change log
#   2026-10-27  Created (user asked to add the sheet's complaints so the Employee Performance
#               page shows calls per splicer / area with their times).
#   2026-11-26  UNIQUE CUT also goes into the new Unique Cut field (NOC reports count cuts by it);
#               it stays in the complaint details too.
# ---------------------------------------------------------------------------------------------

import re
from datetime import datetime

import frappe

COMPLAINT = "Complaint Information"
SHEET = "MAIN DATA"
DATA_LIMIT = 140  # Data fields hold at most 140 characters
EMPTY = {"", "NA", "N/A", "OTHER", "NONE", "-", "#VALUE!", "#N/A"}

OPERATORS = {"AIRTEL": "Airtel", "VI": "Vodafone", "VODAFONE": "Vodafone", "RAILTEL": "Railtel", "JIO": "Jio",
	"SUMASHILP": "Sumashilp", "GAZON": "Gazon", "GBPS": "GBPS", "POWERGRID": "Powergrid", "HATHWAY": "Hathway"}
# Transport is counted as Backbone by the client (see patches/transport_is_backbone.py)
LINK_TYPES = {"FTTH": "FTTH", "BACKBONE": "Backbone", "SMALLCELL": "Small Cell", "SMALL CELL": "Small Cell",
	"ILL": "ILL", "LMC": "LMC", "TRANSPORT": "Backbone"}
LINK_STATUS = {"AUTO RESTORE": "AUTO RESTORED", "TERMINATION CLOSED": "TERMINATION CLOSE", "CORE THROW": "CORE THROUGH",
	"RESTORE BY AIRTEL TEAM": "RESTORED BY AIRTEL TEAM", "JOINTLY VISIT": "JOINT VISIT"}
RFO = {"OWN FIBER ISSUE": "Own Fiber Issue", "COMPANY FIBER ISSUE": "Company Fiber Issue",
	"NOT BELONGS TO EVISION": "Not Belongs to EVisions", "NOT BELONGS TO EVISIONS": "Not Belongs to EVisions", "NA": "NA"}
# Sheet spellings of RFO Type -> the doctype's option (after the leading "12:" number is removed)
RFO_TYPES = {
	"PMC TREE CUTING ACTIVITY": "PMC TREE CUTTING ACTIVITY", "SINGLE CORE": "SINGLE CORE ISSUE",
	"CLOSER CORE CUT": "CORE CUT IN CLOSURE", "PMC ACTIVIYT": "PMC ACTIVITY",
	"FIBER CUT DUE TO CONSTRUCTIONS WORK": "FIBER CUT DUE TO CONSTRUCTION WORK", "LOW RX": "LOW RX/ DEGRADE",
	"LOW RX ISSUE": "LOW RX/ DEGRADE", "LOW RX/DEGRADE": "LOW RX/ DEGRADE",
	"NOT BELONGS TO EVISION": "FIBER DOES NOT BELONG TO EVISIONS", "CLOSER DISTURB": "CLOSURE DISTURBED",
	"ROAD WINDING WORK": "ROAD WIDENING WORK", "FIBER CUT IN AIR(DAMMAGE)": "FIBER CUT/ DAMAGE IN AIR",
	"FIBER CUT DUE TO VIHCLE": "FIBER CUT DUE TO VEHICLE", "POWEER ISSUE": "POWER ISSUE", "FIBER DAMMAGE": "FIBER DAMAGE",
	"FIBER CUT DUE TO KITE(MANJA)": "FIBER CUT DUE TO KITE (MANJA)", "PMC POLE REMOVED ACTIVITY": "PMC POLE REMOVAL ACTIVITY",
	"HOLDING REMOVED ACTIVIYT": "HOARDING REMOVAL ACTIVITY", "PATCH COD ISSUE AT NOD END": "PATCH CORD ISSUE AT NODE END",
	"CORE THROW WORK": "CORE THROUGH WORK", "METROW WORK": "METRO WORK", "CUT DUE TO FASTIVEL": "FIBER CUT DUE TO FESTIVAL",
	"SHIFTING WORK": "FIBER SHIFTING WORK", "SWAPPING CLOSER DISTURB": "SWAPPING CLOSURE DISTURBED",
	"ODF CORE": "ODF CORE CUT", "CUT OVER ACTIVITY": "CUTOVER ACTIVITY", "RESTORE BY AIRTEL TEAM": "RESTORED BY AIRTEL TEAM",
	"ODF ISSUE/CORE CUT": "ODF ISSUE",
}
# Sheet spellings of people -> their Employee's employee_name (checked against HR-EMP records
# on 2026-10-27; Deepak Lad is HR-EMP-00054 "Deepak", as in Staff Monthly Performance)
EMPLOYEE_ALIASES = {"DEEPAK LAD": "Deepak", "SANKET KOTAKAR": "Sanket Kotkar", "ADITYA MANJRE": "Aditya Manjare",
	"SHEKHAR CHARHATE": "Sherkhar Charhate", "KULDEEP": "Kuldeep Kamathe", "AKSHAY CHAVAN": "Akshay Chavhan",
	"DHAMMADIP JONDHALE": "Dhammadeep Jondhale", "RAM KEDAR KUNTE": "Rameshwar Kedarkunte",
	"RAMESHWAR KEDAR KUNTE": "Rameshwar Kedarkunte", "DILIP PAWAR": "Dilip Pawaar", "AKASH PARDESI": "Akash Pardeshi"}

# Sheet vendor spellings that differ from the Maintenance Vendor name
VENDORS = {"SHIV ENTERPRISES KIRKATWADI": "Shiv Enterprise Kirkatwadi", "VENDORE SHITOLE": "VENDOR SHITOLE",
	"SPINE TELICOM/HYPERBAND": "Spine Teleinfra / Hyperband"}

# Place names in link names -> Area. A value that is an existing Area links to it; any other value
# is created as a new Area. Several spellings may point to one place. Longest match wins.
PLACES = {
	# existing Area records (post-office names)
	"WAKAD": "Wakad", "DHANORI": "Dhanori", "HADAPSAR": "Hadapsar", "KATRAJ": "Katraj", "THERGAON": "Thergaon",
	"KOTHRUD": "Kothrud", "VISHRANTWADI": "Vishrantwadi", "WARJE": "Warje", "AKURDI": "Akurdi", "KALEWADI": "Kalewadi",
	"PUNAWALE": "Punawale", "YERWADA": "Yerwada", "YERAWADA": "Yerwada", "LOHEGAON": "Lohogaon", "LOHGAON": "Lohogaon",
	"LOHAGAON": "Lohogaon", "BIBWEWADI": "Bibvewadi", "BIBVEWADI": "Bibvewadi", "BIBEWADI": "Bibvewadi",
	"MUNDHWA": "Mundhva", "MUNDHVA": "Mundhva", "WADGAON SHERI": "Vadgaon Sheri", "VADGAON SHERI": "Vadgaon Sheri",
	"WADGAON BUDRUK": "Vadgaon Budruk", "VADGAON BUDRUK": "Vadgaon Budruk", "SHIVAJI NAGAR": "Shivajinagar (Pune)",
	"SHIVAJINAGAR": "Shivajinagar (Pune)", "MODEL COLONY": "Model Colony", "MARKET YARD": "Market Yard (Pune)",
	"KARVE NAGAR": "Karvenagar", "KARVENAGAR": "Karvenagar", "DHANKAWADI": "Dhankawadi", "DHANAKWADI": "Dhankawadi",
	"TATHAWADE": "Thathawade", "THATHAWADE": "Thathawade", "TALAWADE": "Talwade", "TALWADE": "Talwade",
	"SWARGATE": "Swargate", "MANGALWAR PETH": "Mangalwar Peth (Pune)", "ANAND NAGAR": "Anandnagar (Pune)",
	"MOHAMMAD WADI": "Mohamadwadi", "MOHAMMED WADI": "Mohamadwadi", "MOHAMADWADI": "Mohamadwadi",
	"WANWADI": "Wanowarie", "WANOWRIE": "Wanowarie", "KHADKI": "Khadki", "DAPODI": "Dapodi", "SANGVI": "Sangavi",
	"BHOSARI": "Bhosarigoan", "KASARWADI": "Kasarwadi", "DIGHI": "Dighi Camp", "AUNDH": "Aundh T.S.",
	"PARVATI": "Parvati", "KONDHWA": "Kondhwa BK", "KONDHWA BUDRUK": "Kondhwa BK", "KONDHWA KHURD": "Khondhwa KH",
	"SAHAKAR NAGAR": "Sahakar Nagar", "SAHKAR NAGAR": "Sahakar Nagar",
	# places that are not in the Area list yet (created on import)
	"BANER": "Baner", "CHAKAN": "Chakan", "RAVET": "Ravet", "BAVDHAN": "Bavdhan", "MOSHI": "Moshi",
	"HANDEWADI": "Handewadi", "PIMPLE SAUDAGAR": "Pimple Saudagar", "HINJEWADI": "Hinjewadi", "HINJAWADI": "Hinjewadi",
	"KHARADI": "Kharadi", "DHAYARI": "Dhayari", "DHAYRI": "Dhayari", "DHYARI": "Dhayari", "PASHAN": "Pashan",
	"KIWALE": "Kiwale", "AMBEGAON": "Ambegaon", "BALEWADI": "Balewadi", "MAHALUNGE": "Mahalunge",
	"KESHAV NAGAR": "Keshav Nagar", "UNDRI": "Undri", "NARHE": "Narhe", "VIMAN NAGAR": "Viman Nagar", "BOPODI": "Bopodi",
	"GHORPADI": "Ghorpadi", "YEWALEWADI": "Yewalewadi", "SALUNKE VIHAR": "Salunke Vihar", "KOREGAON PARK": "Koregaon Park",
	"PIMPLE GURAV": "Pimple Gurav", "BHUGAON": "Bhugaon", "GULTEKADI": "Gultekadi", "PHURSUNGI": "Phursungi",
	"ALANDI": "Alandi", "AALANDI": "Alandi", "HINGANE": "Hingne Khurd", "HINGNE": "Hingne Khurd", "MANJARI": "Manjari",
	"MANJRI": "Manjari", "PISOLI": "Pisoli", "SINHGAD ROAD": "Sinhgad Road", "PIMPLE NILAKH": "Pimple Nilakh",
	"FATIMA NAGAR": "Fatima Nagar", "NIGDI": "Nigdi", "LULLA NAGAR": "Lulla Nagar", "LULLANAGAR": "Lulla Nagar",
	"SHIVANE": "Shivane", "LONI KALBHOR": "Loni Kalbhor", "RAHATANI": "Rahatani", "WAKADEWADI": "Wakadewadi",
	"ERANDWANE": "Erandwane", "MAGARPATTA": "Magarpatta", "TINGARE NAGAR": "Tingare Nagar", "CHIKHALI": "Chikhali",
	"CHARHOLI": "Charholi", "CHANDAN NAGAR": "Chandan Nagar", "SANGAMWADI": "Sangamwadi", "SOMATNE": "Somatne",
	"LONAVALA": "Lonavala", "LONAVLA": "Lonavala", "WAGHOLI": "Wagholi", "TALEGAON": "Talegaon", "KESNAND": "Kesnand",
	"CHINCHWAD": "Chinchwad", "PIMPRI": "Pimpri", "CAMP": "Camp", "KATRAJ KONDHWA": "Katraj",
}
NEW_AREA_CODE_PREFIX = "NOC-"


# Date: 2026-10-27
def clean(value):
	"""Text of a cell with spaces squeezed, or "" for an empty / placeholder cell."""
	text = re.sub(r"\s+", " ", str(value if value is not None else "")).strip()
	return "" if text.upper() in EMPTY else text


# Date: 2026-10-27
def as_datetime(value):
	"""A sheet date-time cell as datetime, or None for text / empty cells."""
	return value if isinstance(value, datetime) else None


# Date: 2026-10-27
def norm(text):
	"""Upper-case words separated by single spaces, padded so ' WORD ' matches whole words only."""
	return " " + re.sub(r"[^A-Z0-9]+", " ", str(text or "").upper()).strip() + " "


# Date: 2026-10-27
def read_rows(path):
	"""The sheet rows as dicts keyed by the (trimmed) header text."""
	import openpyxl

	wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
	rows = wb[SHEET].iter_rows(values_only=True)
	header = [str(h or "").strip().upper() for h in next(rows)]
	return [dict(zip(header, r)) for r in rows if r and r[0]]


# Date: 2026-10-27
class Lookups:
	"""Masters the rows are matched against, loaded once."""

	def __init__(self):
		self.employees = {}
		for e in frappe.get_all("Employee", fields=["name", "employee_name"]):
			if e.employee_name:
				self.employees.setdefault(norm(e.employee_name).strip(), e.name)
		for alias, employee_name in EMPLOYEE_ALIASES.items():
			found = self.employees.get(norm(employee_name).strip())
			if found:
				self.employees.setdefault(norm(alias).strip(), found)
		self.teams = {norm(t).strip(): t for t in frappe.get_all("Maintenance Team", pluck="name")}
		self.vendors = {norm(v).strip(): v for v in frappe.get_all("Maintenance Vendor", pluck="name")}
		self.areas = set(frappe.get_all("Area", pluck="name"))
		# Longest place first, so "AMBEGAON BUDRUK" style names beat their shorter parts
		self.places = sorted(((norm(k), v) for k, v in PLACES.items()), key=lambda kv: -len(kv[0]))
		meta = frappe.get_meta(COMPLAINT)
		self.options = {f: set((meta.get_field(f).options or "").split("\n")) for f in ("link_status", "rfo_type")}

	def employee(self, name):
		return self.employees.get(norm(name).strip()) if clean(name) else None

	def area(self, link_name):
		text = norm(link_name)
		return next((area for key, area in self.places if key in text), None)

	def maintainer(self, name):
		"""(Maintenance Team, Maintenance Vendor) for MAINTAIN BY."""
		key = norm(name).strip()
		if not key:
			return None, None
		if key in self.teams:
			return self.teams[key], None
		vendor = VENDORS.get(key) or self.vendors.get(key)
		return None, vendor if vendor and frappe.db.exists("Maintenance Vendor", vendor) else None


# Date: 2026-10-27
def rfo_type(value, options):
	"""Sheet RFO Type ("12:HOLDING REMOVED ACTIVIYT") -> doctype option, or None if unknown."""
	text = re.sub(r"\s+", " ", re.sub(r"^\s*\d+\s*[:.]?\s*", "", str(value or ""))).strip().upper()
	if not text:
		return None
	text = RFO_TYPES.get(text, text)
	return text if text in options else None


# Date: 2026-10-27
def build(row, lk):
	"""One sheet row -> (field values, notes on what could not be matched)."""
	notes = []
	link_name = clean(row.get("LINK NAME"))
	operator_text = clean(row.get("COMPANY")).upper()
	operator = OPERATORS.get(operator_text, "Other")
	if operator == "Other" and operator_text:
		notes.append(f"Operator: {operator_text}")
	tt = clean(row.get("COMPANY TT"))
	maint = clean(row.get("MAINTAIN BY"))
	team, vendor = lk.maintainer(maint)
	if maint and not (team or vendor):
		notes.append(f"Maintained by: {maint}")

	people = {}
	for field, column in (("splicer", "SPLICER"), ("rider", "RIDER"), ("second_splicer", "SPLICER 1"), ("second_rider", "RIDER 1")):
		name = clean(row.get(column))
		people[field] = lk.employee(name)
		if name and not people[field]:
			notes.append(f"{column.title()}: {name}")

	status = clean(row.get("LINK STATUS")).upper()
	status = LINK_STATUS.get(status, status)
	if status and status not in lk.options["link_status"]:
		notes.append(f"Link status: {status}")
		status = None
	r_type = rfo_type(row.get("RFO TYPE"), lk.options["rfo_type"])
	if clean(row.get("RFO TYPE")) and not r_type:
		notes.append(f"RFO type: {clean(row.get('RFO TYPE'))}")

	details = [link_name, f"Company TT: {tt}" if tt else "", f"Unique cut: {clean(row.get('UNIQUE CUT'))}"
		if clean(row.get("UNIQUE CUT")) else ""]
	remarks = [clean(row.get("REMARK")), clean(row.get("RFO DISCRUPTION /LOCATION"))]
	tl = clean(row.get("TL"))
	values = {
		"noc_sheet_no": int(row["NO"]),
		"complaint_code": clean(row.get("COMPLAINT CODE"))[:DATA_LIMIT] or None,
		# 2026-11-26: blank -> the controller uses the Complaint Code (set_unique_cut)
		"unique_cut": clean(row.get("UNIQUE CUT"))[:DATA_LIMIT] or None,
		"request_type": "Termination" if str(row.get("TYPE (TERMINATION?)") or "").strip().upper().startswith("YE") else "Complaint",
		"operatorcustomer": operator,
		"complaint_type": LINK_TYPES.get(clean(row.get("LINK TYPE")).upper()),
		# Only Airtel gives incident numbers; several INC numbers can be in one cell
		"incident_number": tt[:DATA_LIMIT] if operator == "Airtel" and tt else None,
		"complaint_date_and_time": as_datetime(row.get("SR RECEIVED")),
		"complaint_details": "\n".join(d for d in details if d) or None,
		"link_as_reported": link_name[:DATA_LIMIT] or None,
		"area": lk.area(link_name),
		"maintenance_team": team,
		"mapped_vendor": vendor,
		"team_leader_name": tl.title() if tl else None,
		"call_assigned_on": as_datetime(row.get("ASSINGED CALL")),
		"evision_closed_on": as_datetime(row.get("TEAM SR CLOSED")),
		"company_closed_on": as_datetime(row.get("COMPANY SR CLOSE")),
		"link_status": status or None,
		"rfo": RFO.get(clean(row.get("RFO")).upper()) or None,
		"rfo_type": r_type,
		"registered_by": clean(row.get("NOC EXECUTIVE")).title() or None,
		"closed_by": clean(row.get("NOC EXECUTIVE TT CLOSE")).title() or None,
		"delay_reason": clean(row.get("DEALY RESONE FOR TEAM ALIGN")) or None,
		"closure_remarks": "\n".join(r for r in remarks if r) or None,
		**people,
	}
	# A few rows have no (or a text) SR RECEIVED; the team-assigned time is the closest known time
	if not values["complaint_date_and_time"] and values["call_assigned_on"]:
		values["complaint_date_and_time"] = values["call_assigned_on"]
		notes.append("SR RECEIVED empty in sheet, Assigned Call time used")
	if notes:
		values["assignment_remarks"] = "Not matched from NOC sheet: " + "; ".join(notes)
	return values, notes


# Date: 2026-10-27
def ensure_areas(rows, lk, create):
	"""Areas the rows need that do not exist yet; created (Active) when `create` is set."""
	needed = {lk.area(clean(r.get("LINK NAME"))) for r in rows} - {None} - lk.areas
	if create:
		for name in sorted(needed):
			frappe.get_doc({"doctype": "Area", "area_name": name, "status": "Active",
				"area_code": NEW_AREA_CODE_PREFIX + re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")}).insert(ignore_permissions=True)
			lk.areas.add(name)
	return sorted(needed)


# Date: 2026-10-27
@frappe.whitelist()
def preview(path):
	"""Counts only, nothing saved: rows, already imported, area / people matches, unmatched values."""
	frappe.only_for("System Manager")
	rows, lk = read_rows(path), Lookups()
	done = set(frappe.get_all(COMPLAINT, filters={"noc_sheet_no": ["is", "set"]}, pluck="noc_sheet_no"))
	unmatched, with_area, with_splicer = {}, 0, 0
	for row in rows:
		values, notes = build(row, lk)
		with_area += 1 if values["area"] else 0
		with_splicer += 1 if values["splicer"] else 0
		for n in notes:
			unmatched[n] = unmatched.get(n, 0) + 1
	return {
		"rows": len(rows), "already_imported": len(done), "with_area": with_area, "with_splicer": with_splicer,
		"new_areas": ensure_areas(rows, lk, create=False),
		"unmatched_top": sorted(unmatched.items(), key=lambda x: -x[1])[:40],
	}


# Date: 2026-10-27
@frappe.whitelist()
def run(path, limit=None):
	"""Import the sheet rows not imported yet; commits every 500 rows. Returns counts."""
	frappe.only_for("System Manager")
	from emp_tracking.emp_tracking.doctype.complaint_information.complaint_information import DONE_STATES

	# Historical data: no e-mails or notifications from these inserts
	frappe.flags.in_import = True
	frappe.flags.mute_emails = True
	rows, lk = read_rows(path), Lookups()
	created_areas = ensure_areas(rows, lk, create=True)
	frappe.db.commit()
	done = set(frappe.get_all(COMPLAINT, filters={"noc_sheet_no": ["is", "set"]}, pluck="noc_sheet_no"))
	inserted = skipped = failed = 0
	errors = []
	for row in rows:
		if int(row["NO"]) in done:
			skipped += 1
			continue
		if limit and inserted >= int(limit):
			break
		values, _notes = build(row, lk)
		if not values["complaint_date_and_time"]:
			failed += 1
			errors.append((row["NO"], "no SR RECEIVED date"))
			continue
		# A failing row is undone on its own; rows saved before it (not yet committed) stay
		frappe.db.savepoint("noc_row")
		try:
			doc = frappe.new_doc(COMPLAINT)
			doc.update(values)
			# MTTR / SLA / aging by the controller's own rule, as a finished complaint. Worked out
			# as "Resolved": the same aging rule as "Closed", without the live RFO-before-closing
			# check (some sheet rows have no RFO Type)
			doc.workflow_state = DONE_STATES[0]
			doc.set_times_and_sla()
			for field in ("delay_in_assigning", "evision_mttr", "company_mttr", "waiting_for_confirmation", "aging"):
				doc.set(field, doc.get(field) or 0)
			doc.workflow_state = None  # inserted in the workflow's first state, closed below
			doc.flags.ignore_validate = True
			doc.insert(ignore_permissions=True, ignore_mandatory=True)
			frappe.db.set_value(COMPLAINT, doc.name, "workflow_state", DONE_STATES[-1], update_modified=False)
			inserted += 1
		except Exception as e:
			frappe.db.rollback(save_point="noc_row")
			failed += 1
			errors.append((row["NO"], str(e)[:200]))
			continue
		if inserted % 500 == 0:
			frappe.db.commit()
	frappe.db.commit()
	return {"inserted": inserted, "skipped": skipped, "failed": failed, "created_areas": created_areas,
		"errors": errors[:50]}
