# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""GIS Node (FTTH Tracker) extension: shows this app's records in its Connections panel.

Created: 2026-10-24

Node (this app) was merged into GIS Node, so Site.node and Complaint Information.node_id now
link to GIS Node. Hooked through `override_doctype_dashboards` in hooks.py: Frappe first builds
the panel from GIS Node's own links (work orders, link register, node sites, KMZ), then calls
this to add a "Sites & Complaints" group. Nothing in FTTH Tracker is edited.

Change log
  2026-10-24  Created: "Sites & Complaints" connections.
  2026-10-26  get_kmz_files(): the KMZ source files imported for a node, for the form's
              "KMZ Files" section (public/js/gis_node.js).
"""

import frappe


# Date: 2026-10-24
def get_dashboard_data(data):
	data.setdefault("transactions", []).append({"label": "Sites & Complaints", "items": ["Site", "Complaint Information"]})
	# Both use their own field names, not GIS Node's default ("gis")
	data.setdefault("non_standard_fieldnames", {}).update({"Site": "node", "Complaint Information": "node_id"})
	return data


# Date: 2026-10-26
@frappe.whitelist()
def get_kmz_files(gis):
	"""KMZ files FTTH Tracker imported for this node: one row per source file / KMZ folder, with
	how many routes and points came from it. FTTH Tracker's importer stores the file name in
	KMZ Route / KMZ Point.source_file and links each row to its node through `gis`."""
	frappe.has_permission("GIS Node", "read", gis, throw=True)
	files = {}
	for doctype, key in (("KMZ Route", "routes"), ("KMZ Point", "points")):
		if not frappe.db.exists("DocType", doctype):
			continue
		# grouped in the database: a node can have thousands of KMZ points
		for r in frappe.get_all(doctype, filters={"gis": gis}, fields=["source_file", "node_folder", {"COUNT": "*", "as": "n"}],
				group_by="source_file, node_folder", ignore_permissions=False):
			row = files.setdefault((r.source_file or "", r.node_folder or ""),
				{"source_file": r.source_file or "", "node_folder": r.node_folder or "", "routes": 0, "points": 0})
			row[key] += r.n
	return sorted(files.values(), key=lambda r: (r["source_file"], r["node_folder"]))
