# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Loads the "Fiber Maintenance Project Data April 2026-2027" register (Outward and Inward
# Details sheets, April - September 2026) into ERPNext stock as Fiber Store stock entries.
#
# Data: fiber_register_2026_27.json, the rows read from the client's PDF print of the Excel
# file with pdfplumber, unchanged: {"out": [18 columns], "in": [9 columns]}. Dates are Excel
# day numbers (46113 = 2026-04-01).
#
# What it creates (see emp_tracking/fiber_store.py for the design):
#   1. OPENING: one Material Receipt on 2026-04-01 00:00:01 for drums / accessories that were
#      issued before (or without) an inward row. Opening = the drum's first Start Reading,
#      raised if the sheet issues more than that, so no drum goes below zero.
#   2. INWARD : one Material Receipt per Inward row (supplier = Party Name).
#   3. OUTWARD: one Material Issue per Outward row with the job details.
# Each entry carries custom_sheet_ref ("FY26-27 IN 12", "FY26-27 OUT 345", "FY26-27 OPENING"),
# so running the patch again skips what is already there.
# Sheet problems are kept, not hidden: rows whose End Reading is above the Start Reading are
# posted with the sheet's Total cable and without readings, and the remarks say so.
#
# Change log
#   2026-10-26  Created.
# ---------------------------------------------------------------------------------------------

import json
import os
import re
from datetime import date, timedelta

import frappe
from frappe.utils import flt

from emp_tracking.fiber_store import item_for, setup, warehouse, default_company

REF = "FY26-27"
OPENING_DATE = "2026-04-01"  # first day of the fiscal year on the site


def execute():
	setup()
	company = default_company()
	if not company:
		return
	store = warehouse(company)
	with open(os.path.join(os.path.dirname(__file__), "fiber_register_2026_27.json")) as f:
		data = json.load(f)

	inward = [parse_in(r) for r in data["in"]]
	outward = [parse_out(r) for r in data["out"]]
	inward = [r for r in inward if r and r["qty"] > 0]
	outward = [r for r in outward if r and r["qty"] > 0]
	for r in inward + outward:
		ensure_batch(r)

	stats = {"opening": 0, "in": 0, "out": 0, "skipped": 0, "failed": 0}
	if not exists(f"{REF} OPENING"):
		post_opening(company, store, inward, outward, stats)

	for i, r in enumerate(inward):
		# a few Aug rows have no Sr No in the sheet: they are referenced by their position instead
		post(company, store, r, f"{REF} IN {r['sno'] or 'ROW' + str(i + 1)}", "Material Receipt", f"06:{i // 60:02d}:{i % 60:02d}", stats, "in")
	for r in outward:
		n = int(r["sno"]) if r["sno"].isdigit() else 0
		post(company, store, r, f"{REF} OUT {r['sno']}", "Material Issue", f"{9 + n // 3600:02d}:{n % 3600 // 60:02d}:{n % 60:02d}", stats, "out")
	frappe.db.commit()
	print("Fiber register import:", stats)


# ---------------------------------------------------------------- parsing

def xl_date(value):
	return str(date(1899, 12, 30) + timedelta(days=int(value)))


def num(value):
	"""'1430 H' -> 1430, '5 Ltr' -> 5, '' -> 0 (the sheet has a few such cells)."""
	m = re.match(r"\s*(\d+(?:\.\d+)?)", value or "")
	return flt(m.group(1)) if m else 0.0


def batch_name(cable_type, cable_id, fallback):
	cid = (cable_id or "").strip()
	return f"{cable_type.upper()}-{cid}" if cid not in ("", "0") else f"{cable_type.upper()}-{fallback}"


def qty_and_readings(start, end, total):
	start, end, total = num(start), num(end), num(total)
	qty = total or max(start - end, 0)
	bad = end > start
	return qty, (0 if bad else start), (0 if bad else end), bad


def parse_in(r):
	sno, _month, day, party, ctype, cid, start, end, total = r
	item = item_for(ctype)
	if not item or not day.isdigit():
		return None
	qty, s, e, bad = qty_and_readings(start, end, total)
	return {"kind": "in", "sno": sno, "date": xl_date(day), "item": item[0], "drum": item[3],
		"batch": batch_name(ctype, cid, f"NOID-IN{sno}") if item[3] else None,
		"qty": qty, "start": s, "end": e, "bad": bad,
		"party": re.sub(r"\s*\(\s*(.*?)\s*\)", r" (\1)", party).strip()}


def parse_out(r):
	(sno, _month, day, link, work, a_end, b_end, area, team, client, ctype, cid, start, end, total,
		vendor, vtype, bill) = r
	item = item_for(ctype)
	if not item or not day.isdigit():
		return None
	qty, s, e, bad = qty_and_readings(start, end, total)
	return {"kind": "out", "sno": sno, "date": xl_date(day), "item": item[0], "drum": item[3],
		"batch": batch_name(ctype, cid, "NOID") if item[3] else None,
		"qty": qty, "start": s, "end": e, "bad": bad,
		"custom_link_id": link, "custom_work_type": "Maintenance" if work.lower().startswith("maint") else "Project",
		"custom_a_end": a_end, "custom_b_end": b_end, "custom_area": area, "custom_team": team,
		"custom_client": client, "custom_issued_to": vendor,
		"custom_issued_to_type": "Vendor" if vtype.lower() == "vendor" else "Own", "custom_vendor_bill": bill}


# ---------------------------------------------------------------- masters

def ensure_batch(r):
	if r["batch"] and not frappe.db.exists("Batch", r["batch"]):
		frappe.get_doc({"doctype": "Batch", "batch_id": r["batch"], "item": r["item"],
			"description": "Fiber drum (Cable ID from the store register)"}).insert(ignore_permissions=True)


def ensure_supplier(name):
	if name and not frappe.db.exists("Supplier", name):
		group = frappe.db.get_value("Supplier Group", {"is_group": 0}) or "All Supplier Groups"
		frappe.get_doc({"doctype": "Supplier", "supplier_name": name, "supplier_group": group}).insert(ignore_permissions=True)
	return name


def exists(ref):
	return frappe.db.exists("Stock Entry", {"custom_sheet_ref": ref, "docstatus": ["<", 2]})


# ---------------------------------------------------------------- posting

def post_opening(company, store, inward, outward, stats):
	"""Walks every drum / accessory through the sheet in time order and opens it with enough
	stock that it never goes below zero (a drum first seen on an Outward row opens at its
	first Start Reading)."""
	events = sorted(inward + outward, key=lambda r: (r["date"], 0 if r["kind"] == "in" else 1, int(r["sno"] or 0)))
	balance, lowest, first = {}, {}, {}
	for r in events:
		key = (r["item"], r["batch"])
		first.setdefault(key, r)
		balance[key] = balance.get(key, 0) + (r["qty"] if r["kind"] == "in" else -r["qty"])
		lowest[key] = min(lowest.get(key, 0), balance[key])
	rows = []
	for key, low in lowest.items():
		start = first[key]
		opening = -low
		if start["kind"] == "out" and start["drum"]:
			opening = max(opening, start["start"])
		if opening > 0:
			rows.append({"item_code": key[0], "batch_no": key[1], "qty": opening, "t_warehouse": store,
				"custom_start_reading": opening if key[1] else 0})
	if rows:
		make_entry(company, "Material Receipt", OPENING_DATE, "00:00:01", rows,
			{"custom_fiber_direction": "Opening", "custom_sheet_ref": f"{REF} OPENING",
				"remarks": "Opening balance of drums / accessories in hand on 2026-04-01, worked out from "
					"the register: a drum's first Start Reading, raised where the sheet issues more."})
		stats["opening"] = len(rows)


def post(company, store, r, ref, purpose, time, stats, key):
	if exists(ref):
		stats["skipped"] += 1
		return
	row = {"item_code": r["item"], "batch_no": r["batch"], "qty": r["qty"],
		"custom_start_reading": r["start"], "custom_end_reading": r["end"],
		("t_warehouse" if purpose == "Material Receipt" else "s_warehouse"): store}
	header = {"custom_sheet_ref": ref, "remarks": f"Imported from the fiber register, {ref}."}
	if r["bad"]:
		header["remarks"] += " The sheet's End Reading is above its Start Reading; posted with its Total cable."
	if purpose == "Material Receipt":
		header.update({"custom_fiber_direction": "Inward", "supplier": ensure_supplier(r["party"])})
	else:
		header.update({k: v for k, v in r.items() if k.startswith("custom_")})
		header["custom_fiber_direction"] = "Outward"
	# a bad row is rolled back alone; earlier, not yet committed rows stay
	frappe.db.savepoint("fiber_row")
	try:
		make_entry(company, purpose, r["date"], time, [row], header)
		stats[key] += 1
	except Exception:
		frappe.db.rollback(save_point="fiber_row")
		stats["failed"] += 1
		frappe.log_error(title=f"Fiber register import: {ref} failed")
	if (stats["in"] + stats["out"]) % 50 == 0:
		frappe.db.commit()


def make_entry(company, purpose, posting_date, posting_time, rows, header):
	doc = frappe.new_doc("Stock Entry")
	doc.update({"stock_entry_type": purpose, "purpose": purpose, "company": company,
		"posting_date": posting_date, "posting_time": posting_time, "set_posting_time": 1, **header})
	for row in rows:
		uom = frappe.get_cached_value("Item", row["item_code"], "stock_uom")
		doc.append("items", {**row, "uom": uom, "stock_uom": uom, "conversion_factor": 1,
			"basic_rate": 0, "allow_zero_valuation_rate": 1,
			# the drum is chosen by its Batch field (no Serial and Batch Bundle needed)
			"use_serial_batch_fields": 1 if row.get("batch_no") else 0})
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc
