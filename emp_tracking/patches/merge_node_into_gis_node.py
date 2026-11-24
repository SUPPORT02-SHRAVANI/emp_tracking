# ---------------------------------------------------------------------------------------------
# Patch: merge the Node master into GIS Node
#
# How this file works
#   Node (this app) and GIS Node (FTTH Tracker app) held the same GIS codes. GIS Node is kept as
#   the one master because it has the area, managers and engineer and every FTTH record links
#   to it. Site.node and Complaint Information.node_id now link to GIS Node (see their JSON).
#   For every Node row this patch:
#     1. finds the GIS Node with the same code (case / spaces ignored); a code typed with the
#        letter O where GIS Node has a zero (e.g. "OWC" for "0WC") is matched to that node;
#     2. creates the GIS Node when there is no match, copying the Node's area;
#     3. rewrites Site.node and Complaint Information.node_id from the old code to the GIS code.
#   Runs after the doctypes are synced, before the old Node doctype is removed as an orphan.
#   Safe to run twice: matched rows are left as they are.
#
# Change log
#   2026-10-24  Created.
# ---------------------------------------------------------------------------------------------

import frappe


# Date: 2026-10-24
def execute():
	if not frappe.db.table_exists("Node") or not frappe.db.exists("DocType", "GIS Node"):
		return

	gis = {code.strip().upper(): code for code in frappe.get_all("GIS Node", pluck="name")}
	nodes = frappe.db.sql("select name, area from `tabNode`", as_dict=True)

	for node in nodes:
		target = match_gis_code(node.name, gis)
		if not target:
			target = node.name.strip().upper()
			frappe.get_doc({
				"doctype": "GIS Node", "gis_code": target, "area": node.area, "is_active": 1,
			}).insert(ignore_permissions=True)
			gis[target] = target
		if target != node.name:
			# Direct updates: only the link value changes, no other save logic should run.
			frappe.db.sql("update `tabSite` set node=%s where node=%s", (target, node.name))
			frappe.db.sql("update `tabComplaint Information` set node_id=%s where node_id=%s", (target, node.name))


# Date: 2026-10-24
def match_gis_code(code, gis):
	"""GIS Node name for a Node code, or None. Tries the code as typed, then O -> 0 (letter O
	typed for a zero), which is how "OWC" appeared in the Team 2 sheet for GIS "0WC" (Warje)."""
	key = code.strip().upper()
	if key in gis:
		return gis[key]
	return gis.get(key.replace("O", "0"))
