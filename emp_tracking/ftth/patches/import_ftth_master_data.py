# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Patch: load the FTTH Master Data sheet (9,730 ODN sites) into the FTTH Master Data DocType
#
# How this file works
#   Runs once during "bench migrate", so the data also reaches the Frappe Cloud site, where nobody
#   can run scripts by hand. ftth_master_data.json.gz holds the "Master data" tab of
#   "Master Data for Software - ODN sites only (no vendor fill).xlsx" (Drive, 2026-11-27), one dict
#   per site keyed by fieldname (dates as YYYY-MM-DD). Cells that are not real dates (e.g.
#   "16/16/2022") were moved into Data Match Notes when the file was made.
#   The rows are written with one bulk insert (9,730 single inserts would slow every deploy), named
#   FMD-00001 ... in sheet order, and the FMD- series is moved past them so new records continue.
#   Skipped when the DocType already has rows, so it never loads the sheet twice.
#
# Change log
#   2026-11-27  Created (user's request: one master in OverHead Project with this sheet's data).
# ---------------------------------------------------------------------------------------------

import gzip
import json
import os

import frappe
from frappe.utils import now

DOCTYPE = "FTTH Master Data"
SERIES = "FMD-"


# Date: 2026-11-27
def execute():
	frappe.reload_doc("ftth", "doctype", "ftth_master_data")
	if frappe.db.count(DOCTYPE):
		return  # already loaded (or records entered by hand): never import twice

	path = os.path.join(os.path.dirname(__file__), "ftth_master_data.json.gz")
	with gzip.open(path, "rt", encoding="utf-8") as f:
		rows = json.load(f)

	meta = frappe.get_meta(DOCTYPE)
	fields = [df for df in meta.fields if df.fieldtype not in ("Section Break", "Column Break", "Tab Break")]
	data_fields = [df.fieldname for df in fields]
	# number columns are NOT NULL in the database: an empty cell is stored as 0, as a form save would
	numeric = {df.fieldname for df in fields if df.fieldtype in ("Int", "Float", "Check")}
	columns = ["name", "creation", "modified", "owner", "modified_by", "docstatus", "idx", *data_fields]
	stamp, user = now(), "Administrator"
	values = [
		[f"{SERIES}{i:05d}", stamp, stamp, user, user, 0, 0,
			*(row.get(f, 0 if f in numeric else None) for f in data_fields)]
		for i, row in enumerate(rows, start=1)
	]
	frappe.db.bulk_insert(DOCTYPE, columns, values, chunk_size=1000)

	# Move the naming series past the imported rows, so the next record is FMD-09731
	found = frappe.db.sql("select `current` from `tabSeries` where `name` = %s", SERIES)
	current = found[0][0] if found else None
	if current is None:
		frappe.db.sql("insert into `tabSeries` (`name`, `current`) values (%s, %s)", (SERIES, len(rows)))
	elif current < len(rows):
		frappe.db.sql("update `tabSeries` set `current` = %s where `name` = %s", (len(rows), SERIES))
