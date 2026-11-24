# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# KMZ Site Check (Desk page /app/kmz-site-check): data, created 2026-10-27
#
# How this file works
#   A Site (building) and the KMZ pins of its GIS Node should carry the same building name, so
#   the KMZ lines / pins can be linked to the Site (custom_site) and turn red / orange on the
#   KMZ Map when the Site has an open complaint. Spelling differences ("Abhirochi Parisar" in
#   Site, "Abhiruchi Parisar" in the KMZ) break that link.
#   get_rows: each Site with how well its name matches the KMZ names of its node, how many KMZ
#     rows are linked to it, and the 3 closest KMZ names, for the team to check on screen.
#   apply: after the user picks a KMZ name for a Site, links that name's KMZ pins (and routes
#     ending at it) to the Site, and, when asked, renames the Site to the corrected spelling.
#   KMZ names are never changed: KMZ Upload finds rows again by name, so a renamed pin would come
#   back as a duplicate on the next upload.
#
# Change log
#   2026-10-27  Created.
# ---------------------------------------------------------------------------------------------

import difflib
import re
from collections import defaultdict

import frappe
from frappe import _

from emp_tracking.emp_tracking.doctype.kmz_upload.kmz_upload import END_WORDS


def norm(name):
	return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def clean(name):
	"""KMZ name without the ODF / Encloser / JC / Node / A end words: "Ujwal green ODF" -> "Ujwal green"."""
	return re.sub(r"\s+", " ", END_WORDS.sub(" ", name or "")).strip(" -_,.")


def status_of(key, names):
	"""exact: same name on the node; partial: one name contains the other; none: no such name."""
	if key in names:
		return "Exact"
	if len(key) >= 6 and any(key in x or (len(x) >= 6 and x in key) for x in names):
		return "Partial"
	return "No Match"


# Date: 2026-10-27
@frappe.whitelist()
def get_rows(node=None, show="Needs Check"):
	site_filters = {"node": node} if node else {"node": ["is", "set"]}
	sites = frappe.get_list("Site", filters=site_filters, fields=["name", "site_name", "node", "etipl_code"],
		limit_page_length=0, order_by="node asc, site_name asc")
	nodes = sorted({s.node for s in sites})
	if not nodes:
		return {"rows": [], "nodes": [], "counts": {}}

	# KMZ pin names per node: {node: {clean norm: {"name": original, "pins": n}}}
	pins = defaultdict(dict)
	# "free": pins not yet linked to any Site; "taken_by": Sites the other pins are linked to
	for r in frappe.get_list("KMZ Point", filters={"gis": ["in", nodes]}, fields=["gis", "point_name", "custom_site"],
			limit_page_length=0):
		if not r.point_name:
			continue
		entry = pins[r.gis].setdefault(norm(clean(r.point_name)) or norm(r.point_name),
			{"name": r.point_name, "pins": 0, "free": 0, "taken_by": set()})
		entry["pins"] += 1
		if r.custom_site:
			entry["taken_by"].add(r.custom_site)
		else:
			entry["free"] += 1
	site_names = {s.name: s.site_name for s in sites}
	linked = defaultdict(int)
	for doctype in ("KMZ Point", "KMZ Route"):
		for r in frappe.get_list(doctype, filters={"custom_site": ["in", [s.name for s in sites]]},
				fields=["custom_site", {"COUNT": "*", "as": "n"}], group_by="custom_site", limit_page_length=0):
			linked[r.custom_site] += r.n

	rows, counts = [], defaultdict(int)
	for s in sites:
		key = norm(s.site_name)
		names = pins.get(s.node, {})
		status = status_of(key, names) if key else "No Match"
		counts[status] += 1
		if not linked[s.name]:
			counts["Not Linked"] += 1
		if show == "Needs Check" and status == "Exact" and linked[s.name]:
			continue
		if show == "Not Linked" and linked[s.name]:
			continue
		# 3 closest KMZ names on the same node, by spelling similarity
		scored = sorted(((difflib.SequenceMatcher(None, key, k).ratio(), k) for k in names), reverse=True)[:3]
		rows.append({
			"site": s.name, "site_name": s.site_name, "node": s.node, "etipl_code": s.etipl_code,
			"status": status, "linked": linked[s.name],
			"candidates": [{"kmz_name": names[k]["name"], "suggest": clean(names[k]["name"]) or names[k]["name"],
				"pins": names[k]["pins"], "free": names[k]["free"], "score": round(r * 100),
				# 2026-10-27: a name already linked to another Site is usually another wing / building
				"taken_by": [{"site": t, "site_name": site_names.get(t) or t} for t in sorted(names[k]["taken_by"]) if t != s.name]}
				for r, k in scored],
		})
	rows.sort(key=lambda r: (-(r["candidates"][0]["score"] if r["candidates"] else 0), r["node"]))
	return {"rows": rows, "nodes": nodes, "counts": counts}


# Date: 2026-10-27
@frappe.whitelist()
def apply(site, kmz_name, new_site_name=None):
	"""Link the KMZ pins named kmz_name (and routes ending there) on the Site's node to the Site;
	rename the Site when new_site_name is given. Rows already linked to another Site are left alone."""
	doc = frappe.get_doc("Site", site)
	doc.check_permission("write")
	for doctype in ("KMZ Point", "KMZ Route"):
		if not frappe.has_permission(doctype, "write"):
			frappe.throw(_("No permission to update {0}").format(doctype), frappe.PermissionError)

	free = ["custom_site", "is", "not set"]
	points = frappe.get_all("KMZ Point", filters=[["gis", "=", doc.node], ["point_name", "=", kmz_name], free], pluck="name")
	routes = []
	for field in ("route_name", "a_end", "b_end"):
		routes += frappe.get_all("KMZ Route", filters=[["gis", "=", doc.node], [field, "=", kmz_name], free], pluck="name")
	for doctype, names in (("KMZ Point", points), ("KMZ Route", set(routes))):
		for name in names:
			frappe.db.set_value(doctype, name, {"custom_site": site, "custom_kmz_matched_by": "Building Name"})

	if not points and not routes:
		frappe.throw(_("All KMZ pins named \"{0}\" are already linked to another Site, so nothing was changed.").format(kmz_name))

	renamed = False
	new_site_name = (new_site_name or "").strip()
	if new_site_name and new_site_name != doc.site_name:
		old = doc.site_name
		doc.site_name = new_site_name
		doc.save()
		doc.add_comment("Info", _("Site name corrected from \"{0}\" to \"{1}\" to match the KMZ name \"{2}\" (KMZ Site Check).")
			.format(old, new_site_name, kmz_name))
		renamed = True
	return {"points": len(points), "routes": len(set(routes)), "renamed": renamed}
