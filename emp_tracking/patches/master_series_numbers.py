# ---------------------------------------------------------------------------------------------
# Patch: Series No for the masters that already exist (2026-11-28, user: masters numbered
# NOD-00001, ARE-00001 ... as a second ID). For each doctype of master_series.MASTER_SERIES,
# records without a Series No are numbered oldest first (creation, then ID), after the highest
# number already given, and the series counter (tabSeries "NOD-" ...) is moved up so new records
# continue from there. IDs and links are not changed. Safe to run again.
# ---------------------------------------------------------------------------------------------

import frappe

from emp_tracking.master_series import DIGITS, MASTER_SERIES


def execute():
	modules = {"GIS Node": "ftth", "Field Staff": "ftth", "Fiber Team": "ftth"}
	for doctype, prefix in MASTER_SERIES.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		frappe.reload_doc(modules.get(doctype, "emp_tracking"), "doctype", frappe.scrub(doctype))
		table = f"`tab{doctype}`"
		key = prefix + "-"
		done = [int(s[len(key):]) for s in frappe.db.sql_list(f"select series_no from {table} where series_no like %s", key + "%")
			if s[len(key):].isdigit()]
		last = max(done or [0])
		todo = frappe.db.sql_list(f"select name from {table} where coalesce(series_no, '') = '' order by creation asc, name asc")
		for i, name in enumerate(todo, start=last + 1):
			frappe.db.sql(f"update {table} set series_no = %s where name = %s", (f"{key}{i:0{DIGITS}d}", name))
		last += len(todo)
		current = frappe.db.sql("select `current` from `tabSeries` where `name` = %s", key)
		if not current:
			frappe.db.sql("insert into `tabSeries` (`name`, `current`) values (%s, %s)", (key, last))
		elif (current[0][0] or 0) < last:
			frappe.db.sql("update `tabSeries` set `current` = %s where `name` = %s", (last, key))
		print(f"{doctype}: {len(todo)} numbered, series {key} at {last}")
	frappe.db.commit()
