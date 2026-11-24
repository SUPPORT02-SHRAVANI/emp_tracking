# ---------------------------------------------------------------------------------------------
# Patch: import the Team 2 site list
#
# How this file works
#   Runs once, automatically, during "bench migrate". It reads team2_sites.json (made from the
#   sheet "Team 2 Data - Updated till Jan 2026") and creates one GIS Node per GIS code that is
#   missing and one Site per row. Rows that already exist are skipped, so running it again adds
#   nothing twice.
#
# Change log
#   2026-10-07  Created: imports 22 nodes and 696 sites.
#   2026-10-07  Added this header.
#   2026-10-24  Nodes go to GIS Node (FTTH Tracker), which replaced the Node master; codes are
#               matched like merge_node_into_gis_node (so "OWC" in the sheet is GIS "0WC").
#               Only matters on a new site: this patch has already run on existing ones.
# ---------------------------------------------------------------------------------------------

import json
import os

import frappe

from emp_tracking.patches.merge_node_into_gis_node import match_gis_code


# Date: 2026-10-07
def execute():
	"""Load the Team 2 site list (updated till Jan 2026) into GIS Node and Site."""
	path = os.path.join(os.path.dirname(__file__), "team2_sites.json")
	with open(path, encoding="utf-8") as f:
		rows = json.load(f)

	gis = {code.strip().upper(): code for code in frappe.get_all("GIS Node", pluck="name")}
	codes = {}
	for node in sorted({row["node"] for row in rows}):
		code = match_gis_code(node, gis)
		if not code:
			code = node.strip().upper()
			frappe.get_doc({"doctype": "GIS Node", "gis_code": code, "is_active": 1}).insert(ignore_permissions=True)
			gis[code] = code
		codes[node] = code

	for row in rows:
		row = {**row, "node": codes[row["node"]]}
		# Site names repeat, so a site is the same only if name, node and ETIPL code all match.
		filters = {"site_name": row["site_name"], "node": row["node"], "etipl_code": row["etipl_code"]}
		if frappe.db.exists("Site", filters):
			continue
		frappe.get_doc({"doctype": "Site", **row}).insert(ignore_permissions=True)
