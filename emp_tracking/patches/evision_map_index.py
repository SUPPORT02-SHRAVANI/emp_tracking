# ---------------------------------------------------------------------------------------------
# Patch: EVision Settings gets its map Index rows (KMZ Map and NOC map: every Index line with its
# label and colour as they are today, all shown) and the Index positions. Created 2026-11-28.
# Saving the page adds missing rows (EVisionSettings.sync_index_rows); saved rows are kept.
# ---------------------------------------------------------------------------------------------

import frappe


def execute():
	frappe.reload_doc("emp_tracking", "doctype", "evision_map_index_row")
	frappe.reload_doc("emp_tracking", "doctype", "evision_settings")
	doc = frappe.get_single("EVision Settings")
	doc.kmz_index_position = doc.kmz_index_position or "Bottom right"
	doc.noc_index_position = doc.noc_index_position or "Bottom left"
	doc.kmz_index_start = doc.kmz_index_start or "Open"
	doc.noc_index_start = doc.noc_index_start or "Open"
	doc.save(ignore_permissions=True)
