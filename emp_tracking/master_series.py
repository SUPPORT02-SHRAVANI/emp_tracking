# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Master series numbers. Created 2026-11-28 (user: masters should be numbered in a series like
# NOD-00001, ARE-00001 ...; chose "series as a second ID": the records keep their IDs, which the
# rest of the app and the Airtel messages / KMZ files use, and get a Series No beside them).
#
# How this file works
#   Every master below has a read-only, unique "Series No" field (series_no). before_insert (doc
#   event, hooks.py) gives a new record the next number of its own series (tabSeries "NOD-" ...).
#   Patch master_series_numbers numbers the records that already exist, oldest first. series_no
#   is also in each doctype's search fields, so a Link dropdown finds a master by its number too.
# ---------------------------------------------------------------------------------------------

import frappe
from frappe.model.naming import getseries

# doctype -> series prefix (user's list, 2026-11-28)
MASTER_SERIES = {
	"GIS Node": "NOD",
	"Area": "ARE",
	"Site": "SIT",
	"Network Link": "LNK",
	"Maintenance Team": "TEM",
	"Maintenance Vendor": "VEN",
	"Field Staff": "STF",
	"Fiber Team": "FBT",
}
DIGITS = 5


# Date: 2026-11-28
def next_series_no(doctype):
	"""The next number of the doctype's series, e.g. NOD-00042."""
	prefix = MASTER_SERIES[doctype] + "-"
	return prefix + getseries(prefix, DIGITS)


# Date: 2026-11-28
def set_series_no(doc, method=None):
	"""doc_events before_insert: a new master gets its Series No (kept when one is already given,
	e.g. a copied import)."""
	if doc.doctype in MASTER_SERIES and doc.meta.has_field("series_no") and not doc.get("series_no"):
		doc.series_no = next_series_no(doc.doctype)
