# ---------------------------------------------------------------------------------------------
# Patch: import the 03Y node site list
#
# How this file works
#   Runs once during "bench migrate". sites_03y.json holds the "03Y Node details" sheet:
#   [site name, B location] per row, 76 sites of GIS Node 03Y. B location is what the site is
#   fed from: the node itself ("03Y"), the "03Y Middle Enclosure", or another 03Y site, which
#   the Network Topology / KMZ Map pages use to draw the feeder tree. A row whose name, node and
#   B location already exist is skipped, so running it again adds nothing twice.
#   "Arihant Society" is in the sheet twice (fed from 03Y and from Jyoti Palace); both are kept.
#
# Change log
#   2026-10-28  Created (user asked to import "03Y Node details.pdf").
# ---------------------------------------------------------------------------------------------

import json
import os

import frappe

NODE = "03Y"


# Date: 2026-10-28
def execute():
	"""Create one Site per row of the 03Y sheet, under GIS Node 03Y."""
	if not frappe.db.exists("GIS Node", NODE):
		return  # the node comes from the FTTH data; without it these sites have nowhere to hang
	path = os.path.join(os.path.dirname(__file__), "sites_03y.json")
	with open(path, encoding="utf-8") as f:
		rows = json.load(f)
	for site_name, b_location in rows:
		row = {"site_name": site_name.strip(), "node": NODE, "b_location": b_location.strip()}
		if frappe.db.exists("Site", row):
			continue
		frappe.get_doc({"doctype": "Site", **row}).insert(ignore_permissions=True)
