# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt
"""Pure business rules for FTTH work orders.

Change log
  2026-10-29  compute_warnings(): warn when a work order is RFS Done but has no KMZ route mapped.
  2026-10-29  compute_stage(): who has to act next, with the same stage names as emp_tracking's
              New Project (Survey by Area Manager -> ... -> Final Details by Project Head).
  2026-10-29  compute_stage(): after RFS the work order goes on like New Project:
              AT & HOTO by Project Head -> Billing by Accounts -> Closed ("RFS Done" stage removed).
  2026-10-29  hoto_values(): Billing tab values (HOTO No / Date / AT and signature status) from the
              Link Register's HOTO rows; final_amount() = base + GST.

Nothing in this module imports frappe, so it can be unit-tested anywhere and is
shared by the DocType controller and the zip importer.
"""

import datetime as dt
import json
import math
import re

STATUSES = ("New", "Survey", "On Hold", "Fiber Laid", "Splicing Done", "RFS Done", "Cancelled")

# Free-text remark -> standard issue type. First matching rule wins.
ISSUE_RULES = (
	("Cancelled", r"cancel|cancle|\bdro+p\b|not required"),
	("Completed", r"complet|\bdone\b|\brfs\b"),
	("Permission Issue A End", r"permission.{0,12}\ba\s*-?\s*end|\ba\s*end.{0,12}permission|site end permission"),
	("Permission Issue B End", r"permission.{0,12}\bb\s*-?\s*end|\bb\s*end.{0,12}permission"),
	("Permission Issue", r"permission"),
	("Mail Approval Required", r"mail approval"),
	("OLT Pending", r"\bolt\b"),
	("Site Location Not Received", r"location not rec"),
	("Details Not Received", r"details? not rec"),
	("B End Not Evisions", r"not belong"),
	("Wrong WO", r"wrong wo"),
	("Access Issue", r"access"),
	("WIP", r"\bwip\b|work in progress"),
	("Yet to Start", r"yet to start|\bpending\b"),
	("Local Issue", r"local"),
)
BLOCKING_ISSUES = {
	"Permission Issue A End", "Permission Issue B End", "Permission Issue", "Mail Approval Required",
	"OLT Pending", "Site Location Not Received", "Details Not Received", "B End Not Evisions",
	"Wrong WO", "Access Issue", "Local Issue", "Other",
}


def classify_issue(*texts):
	"""Pick a standard issue type from one or more remark texts (first text has priority)."""
	for text in texts:
		t = clean(str(text)) if text is not None else None
		if not t or t.lower() == "none":
			continue
		for label, pattern in ISSUE_RULES:
			if re.search(pattern, t, re.I):
				return label
		return "Other"
	return None


def fiber_type(value):
	"""'24' / '24F' / '24 F' -> '24F'"""
	m = re.search(r"(12|24|48|96)", str(value or ""))
	return f"{m.group(1)}F" if m else None


def excel_date(value):
	"""Date from a datetime, an Excel serial number (45431) or common text formats."""
	if isinstance(value, dt.datetime):
		return value.date()
	if isinstance(value, dt.date):
		return value
	if isinstance(value, (int, float)) and 30000 < value < 60000:
		return (dt.datetime(1899, 12, 30) + dt.timedelta(days=int(value))).date()
	if isinstance(value, str):
		v = value.strip()
		for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y", "%d %B %y", "%d %b %Y"):
			try:
				return dt.datetime.strptime(v, fmt).date()
			except ValueError:
				pass
	return None


# ------------------------------------------------------------------ text helpers
def clean(value):
	"""Collapse whitespace; treat '-', 'NA' etc. as empty."""
	if isinstance(value, str):
		value = re.sub(r"\s+", " ", value).strip()
		return None if value in ("", "-", "--", "—", "NA", "N/A", "na", "n/a") else value
	return value


def norm(value):
	"""Lower-case alphanumerics only - used for loose name matching and dedupe keys."""
	return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def same(a, b):
	return norm(a) == norm(b)


def as_text_number(value):
	"""Phone numbers / IDs read from Excel come back as 9075849272.0 - keep them as text."""
	if value is None:
		return None
	s = str(value).strip()
	if re.fullmatch(r"\d+\.0", s):
		s = s[:-2]
	return s or None


def to_float(value):
	if value in (None, "", "-"):
		return None
	try:
		return float(value)
	except (TypeError, ValueError):
		return None


def yes(value):
	return 1 if str(value or "").strip().lower() in ("yes", "y", "1", "true", "done", "ok") else 0


# ------------------------------------------------------------------ WO number
def parse_wo_number(wo_number):
	"""Read the parts Airtel puts inside the WO number.

	BAL-ANG-UASL-ROM-Maharashtra/PUNE/Capex/FTTH/B2C/New Rollout/Midrise/IBW/20022025/104922
	-> wo_id 104922, wo_date 2025-02-20, segment B2C, building_type Midrise
	"""
	out = {"wo_id": None, "wo_date": None, "segment": None, "building_type": None}
	if not wo_number:
		return out
	parts = [p.strip() for p in str(wo_number).strip().split("/")]
	parts = [p for p in parts if p]
	if len(parts) < 2:
		return out  # not a WO number ('-', a lat/long, a building name …)
	m = re.search(r"\d{4,}", parts[-1])
	if not m:
		return out
	out["wo_id"] = m.group(0)
	# date: the last 8-digit ddmmyyyy block before the id
	for p in reversed(parts[:-1]):
		if re.fullmatch(r"\d{8}", p):
			try:
				out["wo_date"] = dt.datetime.strptime(p, "%d%m%Y").date()
			except ValueError:
				pass
			break
	for p in parts:
		if p.upper() in ("B2C", "B2B"):
			out["segment"] = p.upper()
	# building type sits two places before the date (…/Midrise/IBW/<date>/<id>)
	if len(parts) >= 4 and re.fullmatch(r"\d{8}", parts[-2]):
		out["building_type"] = parts[-4]
	return out


# ------------------------------------------------------------------ lat / long
def parse_lat_long(text):
	"""'18.5210, 73.9083' / '18.5210 73.9083' / '18.5210,73.9083' -> (18.521, 73.9083)."""
	if text in (None, ""):
		return None, None
	nums = re.findall(r"-?\d+(?:\.\d+)?", str(text))
	if len(nums) < 2:
		return None, None
	lat, lon = float(nums[0]), float(nums[1])
	if not (-90 <= lat <= 90 and -180 <= lon <= 180):
		return None, None
	return lat, lon


# ------------------------------------------------------------------ geometry
def haversine_m(lon1, lat1, lon2, lat2):
	r = 6371000.0
	p1, p2 = math.radians(lat1), math.radians(lat2)
	dp, dl = p2 - p1, math.radians(lon2 - lon1)
	h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
	return 2 * r * math.asin(math.sqrt(h))


def line_length_m(coords):
	"""coords: [(lon, lat), ...]"""
	return sum(haversine_m(*coords[i], *coords[i + 1]) for i in range(len(coords) - 1))


def feature_collection(features):
	return json.dumps({"type": "FeatureCollection", "features": features})


def point_feature(lat, lon, name=None):
	return {"type": "Feature", "properties": {"name": name} if name else {},
			"geometry": {"type": "Point", "coordinates": [lon, lat]}}


def line_feature(coords, name=None):
	return {"type": "Feature", "properties": {"name": name} if name else {},
			"geometry": {"type": "LineString", "coordinates": [list(c) for c in coords]}}


def line_from_geojson(text):
	"""Return [(lon, lat), ...] of the first LineString in a GeoJSON string."""
	try:
		data = json.loads(text) if isinstance(text, str) else text
	except (TypeError, ValueError):
		return []
	if not data:
		return []
	feats = data.get("features") or ([data] if data.get("type") == "Feature" else [])
	for f in feats:
		g = f.get("geometry") or {}
		if g.get("type") == "LineString":
			return [tuple(c[:2]) for c in g.get("coordinates", [])]
	return []


def split_route_name(name):
	"""'Gera Grand to ODF GARDEN VIEW' -> ('Gera Grand', 'ODF GARDEN VIEW')"""
	parts = re.split(r"(?i)\s+to\s+", name or "", maxsplit=1)
	return (clean(parts[0]), clean(parts[1])) if len(parts) == 2 else (clean(name), None)


# ------------------------------------------------------------------ derived values
def effective_distances(planning, survey, final, shared):
	"""Blank means 'same as the previous stage'."""
	s = survey if survey not in (None, 0, "") else planning
	f = final if final not in (None, 0, "") else s
	sh = shared if shared not in (None, 0, "") else f
	return s, f, sh


def compute_status(d):
	issue = d.get("issue_type")
	if issue == "Cancelled":
		return "Cancelled"
	if d.get("rfs_date") or d.get("work_completed_date") or issue == "Completed":
		return "RFS Done"
	if d.get("splicing_snaps_done"):
		return "Splicing Done"
	if d.get("fiber_id"):
		return "Fiber Laid"
	if issue in BLOCKING_ISSUES:
		return "On Hold"
	if d.get("planning_distance"):
		return "Survey"
	return "New"


# 2026-10-29: stages a work order passes through; each names who has to act. Same list and wording
# as emp_tracking's New Project (after RFS: AT & HOTO, Billing, Closed).
STAGE_SURVEY = "Survey by Area Manager"
STAGE_B_END_APPROVAL = "B End Approval by Project Head"
STAGE_FIBER_TEAM = "Fiber Team Assignment by Area Manager"
STAGE_FIBER_WORK = "Fiber Work by Fiber Team"
STAGE_SPLICER = "Splicer Assignment by Area Manager"
STAGE_SPLICING = "Splicing by Splicing Team"
STAGE_FINAL = "Final Details by Project Head"
STAGE_AT_HOTO = "AT & HOTO by Project Head"
STAGE_BILLING = "Billing by Accounts"
STAGE_CLOSED = "Closed"
STAGE_CANCELLED = "Cancelled"
STAGES = (STAGE_SURVEY, STAGE_B_END_APPROVAL, STAGE_FIBER_TEAM, STAGE_FIBER_WORK, STAGE_SPLICER,
		  STAGE_SPLICING, STAGE_FINAL, STAGE_AT_HOTO, STAGE_BILLING, STAGE_CLOSED, STAGE_CANCELLED)
# Payment statuses that end the Billing stage (same as New Project's PAYMENT_DONE).
PAYMENT_DONE = ("Fully Received", "Cancelled/ Written Off")


# Date: 2026-10-29
def compute_stage(d):
	"""The first step of the work that is not done yet, i.e. who has to act now.
	A finished (RFS / completed) work order skips the fiber checks, so old imported rows without
	survey or splicing details go on to AT & HOTO / Billing / Closed, as New Project does after RFS."""
	issue = d.get("issue_type")
	if issue == "Cancelled":
		return STAGE_CANCELLED
	if d.get("rfs_date") or d.get("work_completed_date") or issue == "Completed":
		if not (d.get("at_status") == "Done" and d.get("hoto_date")):
			return STAGE_AT_HOTO
		if d.get("payment_status") not in PAYMENT_DONE:
			return STAGE_BILLING
		return STAGE_CLOSED
	if d.get("b_end_issue") and not d.get("approval_date"):
		return STAGE_B_END_APPROVAL
	if not d.get("survey_distance"):
		return STAGE_SURVEY
	if not d.get("fiber_team"):
		return STAGE_FIBER_TEAM
	if not (d.get("fiber_id") or (d.get("reading_a_snap") and d.get("reading_b_snap"))):
		return STAGE_FIBER_WORK
	if not d.get("splicer"):
		return STAGE_SPLICER
	if not (d.get("splicing_snaps_done") or (d.get("splicing_snap_a") and d.get("splicing_snap_b"))):
		return STAGE_SPLICING
	return STAGE_FINAL


# Date: 2026-10-29
def hoto_values(rows):
	"""Billing-tab values from a Link Register's HOTO rows (dicts with hoto_no, hoto_date, year,
	section_name), using the latest row. The billing sheet's "HOTO NO" column also holds statuses:
	  "HOTO 296"     -> HOTO No 296, AT Done, signature Done
	  "Sign Pending" -> AT Done, signature Pending (no HOTO No yet)
	  "AT Pending"   -> AT Pending
	Anything else (a name typed in the column) is kept as the HOTO No without a status."""
	rows = [r for r in rows or [] if r.get("hoto_no") or r.get("hoto_date")]
	if not rows:
		return {}
	last = max(rows, key=lambda r: str(r.get("hoto_date") or ""))
	text = " ".join(str(last.get("hoto_no") or "").split())
	out = {"hoto_date": last.get("hoto_date"), "billing_year": last.get("year"),
		   "billing_section_name": last.get("section_name")}
	low = text.lower()
	if low.startswith("hoto"):
		out.update(hoto_no=text, at_status="Done", hoto_signature_status="Done")
	elif "sign" in low and "pending" in low:
		out.update(at_status="Done", hoto_signature_status="Pending")
	elif low.startswith("at") and "pending" in low:
		out.update(at_status="Pending")
	elif text:
		out["hoto_no"] = text
	return {k: v for k, v in out.items() if v not in (None, "")}


# Date: 2026-10-29
def final_amount(base, gst):
	"""Billing Final Amount = Base Amount + GST Amount (None when both are empty)."""
	b, g = to_float(base), to_float(gst)
	return None if b is None and g is None else (b or 0) + (g or 0)


def compute_warnings(d, survey_diff_pct=50, kmz_diff_pct=30):
	"""d: dict of work-order values (after derived values are filled)."""
	w = []
	if not d.get("gis"):
		w.append("GIS missing.")
	if not d.get("ibd_team"):
		w.append("IBD Team / Vendor missing.")
	if not d.get("wo_number") or not d.get("wo_id"):
		w.append("No WO number yet.")
	elif not d.get("wo_date"):
		w.append("Cannot read the date inside the WO number.")
	if d.get("end_lat_long") and d.get("latitude") in (None, 0):
		w.append("End Lat/Long format is wrong.")
	if d.get("b_end_lat_long") and d.get("b_end_latitude") in (None, 0):
		w.append("B End Lat/Long format is wrong.")
	plan, s_eff = to_float(d.get("planning_distance")), to_float(d.get("eff_survey_distance"))
	if plan and s_eff and abs(s_eff - plan) > plan * survey_diff_pct / 100:
		w.append(f"Survey distance ({s_eff:g} m) differs from Planning ({plan:g} m) by more than {survey_diff_pct:g}%.")
	f_eff, sh_eff = to_float(d.get("eff_final_distance")), to_float(d.get("eff_shared_distance"))
	if f_eff and sh_eff and sh_eff > f_eff:
		w.append(f"Distance shared to Airtel ({sh_eff:g} m) is more than Final distance ({f_eff:g} m).")
	kmz = to_float(d.get("kmz_route_length"))
	if kmz and f_eff and abs(kmz - f_eff) > f_eff * kmz_diff_pct / 100:
		w.append(f"KMZ route length ({kmz:.0f} m) differs from Final distance ({f_eff:g} m) by more than {kmz_diff_pct:g}%.")
	if d.get("rfs_date") and d.get("fiber_id") and not d.get("kmz_done"):
		w.append("RFS done but KMZ not marked done.")
	# 2026-10-29: a site that is Ready For Service must have its fiber route mapped (a matched
	# KMZ Route), otherwise the Route Map shows no line and no distance.
	if (d.get("status") == "RFS Done" or d.get("rfs_date")) and not d.get("kmz_route"):
		w.append("RFS done but no KMZ route is mapped.")
	if d.get("b_end_issue") and not d.get("new_b_end"):
		w.append("B End issue ticked but New B End is empty.")
	rfs, recv = d.get("rfs_date"), d.get("wo_received_date")
	if isinstance(rfs, dt.date) and isinstance(recv, dt.date) and (rfs.year, rfs.month) < (recv.year, recv.month):
		w.append("RFS date is before the WO received date.")
	return w


def derive(d, survey_diff_pct=50, kmz_diff_pct=30):
	"""Fill every automatic field of a work order. `d` is a dict (or dict-like) of values;
	returns a dict of field -> value to apply."""
	out = {}
	out.update(parse_wo_number(d.get("wo_number")))
	out["latitude"], out["longitude"] = parse_lat_long(d.get("end_lat_long"))
	out["b_end_latitude"], out["b_end_longitude"] = parse_lat_long(d.get("b_end_lat_long"))
	out["final_b_end"] = d.get("new_b_end") or d.get("b_end")
	if not d.get("rfs_date") and d.get("work_completed_date"):
		out["rfs_date"] = d.get("work_completed_date")
	if d.get("fiber_type"):
		out["fiber_type"] = fiber_type(d.get("fiber_type"))
	s, f, sh = effective_distances(to_float(d.get("planning_distance")), to_float(d.get("survey_distance")),
								   to_float(d.get("final_distance")), to_float(d.get("distance_shared")))
	out["eff_survey_distance"], out["eff_final_distance"], out["eff_shared_distance"] = s, f, sh
	a, b = to_float(d.get("fiber_reading_a")), to_float(d.get("fiber_reading_b"))
	out["fiber_used"] = abs(a - b) if a is not None and b is not None else None
	rfs, recv = out.get("rfs_date") or d.get("rfs_date"), d.get("wo_received_date")
	out["rfs_month"] = rfs.strftime("%Y-%m") if isinstance(rfs, dt.date) else None
	out["rfs_year"] = rfs.year if isinstance(rfs, dt.date) else None
	out["days_to_rfs"] = (rfs - recv).days if isinstance(rfs, dt.date) and isinstance(recv, dt.date) and rfs >= recv else None
	if d.get("splicing_snap_a") and d.get("splicing_snap_b"):
		out["splicing_snaps_done"] = 1
	merged = {**dict(d), **out}
	out["status"] = merged["status"] = compute_status(merged)
	out["stage"] = compute_stage(merged)  # 2026-10-29
	warnings = compute_warnings(merged, survey_diff_pct, kmz_diff_pct)
	out["warnings"] = "\n".join(warnings) or None
	out["has_warnings"] = 1 if warnings else 0
	return out


def route_map_geojson(d, route_coords=None, route_name=None):
	feats = []
	if d.get("latitude") and d.get("longitude"):
		feats.append(point_feature(d["latitude"], d["longitude"], d.get("end_location") or "End"))
	if d.get("b_end_latitude") and d.get("b_end_longitude"):
		feats.append(point_feature(d["b_end_latitude"], d["b_end_longitude"], d.get("final_b_end") or "B End"))
	if route_coords and len(route_coords) >= 2:
		feats.append(line_feature(route_coords, route_name))
	return feature_collection(feats) if feats else None
