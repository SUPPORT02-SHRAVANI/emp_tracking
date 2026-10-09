# ---------------------------------------------------------------------------------------------
# Patch: import the Team 2 site list
#
# How this file works
#   Runs once, automatically, during "bench migrate". It reads team2_sites.json (made from the
#   sheet "Team 2 Data - Updated till Jan 2026") and creates one Node per GIS code and one Site
#   per row. Rows that already exist are skipped, so running it again adds nothing twice.
#
# Change log
#   2026-10-07  Created: imports 22 nodes and 696 sites.
#   2026-10-07  Added this header.
# ---------------------------------------------------------------------------------------------

import json
import os

import frappe


# Date: 2026-10-07
def execute():
	"""Load the Team 2 site list (updated till Jan 2026) into Node and Site."""
	path = os.path.join(os.path.dirname(__file__), "team2_sites.json")
	with open(path, encoding="utf-8") as f:
		rows = json.load(f)

	for node in sorted({row["node"] for row in rows}):
		if not frappe.db.exists("Node", node):
			frappe.get_doc({"doctype": "Node", "node_id": node}).insert(ignore_permissions=True)

	for row in rows:
		# Site names repeat, so a site is the same only if name, node and ETIPL code all match.
		filters = {"site_name": row["site_name"], "node": row["node"], "etipl_code": row["etipl_code"]}
		if frappe.db.exists("Site", filters):
			continue
		frappe.get_doc({"doctype": "Site", **row}).insert(ignore_permissions=True)
