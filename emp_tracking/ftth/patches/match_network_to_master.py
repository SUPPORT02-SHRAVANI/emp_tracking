# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Patch: make the Network lists (GIS Nodes, Sites, Link Register) match FTTH Master Data
#
# How this file works
#   FTTH Master Data (9,730 ODN sites, loaded by import_ftth_master_data) is the reference. This
#   patch only ADDS missing records and FILLS BLANK fields; nothing typed by people is overwritten.
#   1. GIS Nodes: every master GIS code that looks like a real code (3-4 letters / digits, e.g.
#      03Y, V0N, BJFP) and has no GIS Node yet is created, with the area and team seen most often
#      on its master rows. Codes such as "BCW (1BE)" or "2E 2" are skipped (typos to check).
#   2. Sites: every master building (End Location Name + GIS) without a Site on that node is
#      created: B Location = Survey B End, Vendor Name = Team, Month = "Mon/YYYY". Existing sites
#      (matched by name + node, ignoring case) only get blank B Location / Vendor / Month filled;
#      their ETIPL topology codes are never touched. One bulk insert, SITE-##### continued.
#   3. Link Register (FTTH Link): blank GIS / A End filled from the master row with the same Link
#      ID; a master Link ID missing from the register is added (Airtel FTTH).
#   Safe to run again: a second run finds nothing left to add or fill.
#
# Change log
#   2026-11-27  Created (user: "can you make this data match to Master data" - Network menu).
#   2026-11-28  Fix: Site is named "format:SITE-{#####}", and Frappe keeps that number in the shared
#               series row "" (empty name; Complaint, KMZ Upload ... use it too), not in "SITE-".
#               Only "SITE-" was moved, so new Sites collided with the inserted ones. Both are moved now.
# ---------------------------------------------------------------------------------------------

import re
from collections import Counter, defaultdict

import frappe
from frappe.utils import flt, getdate, now

MASTER = "FTTH Master Data"
CODE = re.compile(r"[A-Z0-9]{3,4}")


# Date: 2026-11-27
def execute():
	if not frappe.db.exists("DocType", MASTER) or not frappe.db.count(MASTER):
		return
	rows = frappe.get_all(MASTER, fields=["end_location_name", "gis", "area", "team", "survey_b_end", "month",
		"evisions_link_id", "final_distance"], order_by="name asc")
	for r in rows:
		r.gis = (r.gis or "").strip().upper()
		r.end_location_name = (r.end_location_name or "").strip()
	add_gis_nodes(rows)
	match_sites(rows)
	match_link_register(rows)


def add_gis_nodes(rows):
	"""Step 1: GIS Node for each real-looking master GIS code that is missing."""
	existing = {n.upper() for n in frappe.get_all("GIS Node", pluck="name")}
	areas, teams = defaultdict(Counter), defaultdict(Counter)
	for r in rows:
		if r.gis and r.area:
			areas[r.gis][r.area.strip()] += 1
		if r.gis and r.team:
			teams[r.gis][r.team.strip()] += 1
	for code in sorted({r.gis for r in rows if r.gis}):
		if code in existing or not CODE.fullmatch(code):
			continue
		area = areas[code].most_common(1)[0][0] if areas[code] else "Not set"  # Area is mandatory
		team = teams[code].most_common(1)[0][0] if teams[code] else None
		frappe.get_doc({"doctype": "GIS Node", "gis_code": code, "area": area, "team": team, "is_active": 1}).insert(
			ignore_permissions=True)


def match_sites(rows):
	"""Step 2: one Site per master building on an existing node; blanks of existing Sites filled."""
	nodes = {n.upper(): n for n in frappe.get_all("GIS Node", pluck="name")}
	sites = {}
	for s in frappe.get_all("Site", fields=["name", "site_name", "node", "b_location", "vendor_name", "month"]):
		sites[((s.site_name or "").strip().lower(), (s.node or "").upper())] = s

	new = []
	for r in rows:
		node = nodes.get(r.gis)
		if not node or not r.end_location_name:
			continue
		month = getdate(r.month).strftime("%b/%Y") if r.month else None  # as the Site list has it: May/2023
		values = {"b_location": (r.survey_b_end or "").strip() or None, "vendor_name": (r.team or "").strip() or None,
			"month": month}
		site = sites.get((r.end_location_name.lower(), node.upper()))
		if site:
			blanks = {f: v for f, v in values.items() if v and not site.get(f)}
			if blanks:
				frappe.db.set_value("Site", site.name, blanks, update_modified=False)
			continue
		sites[(r.end_location_name.lower(), node.upper())] = frappe._dict(name=None)  # once per building
		new.append([r.end_location_name, node, values["b_location"], values["vendor_name"], month])

	if not new:
		return
	# continue SITE-##### after the highest number in use
	last = max([int(n.split("-")[-1]) for n in frappe.get_all("Site", pluck="name") if n.split("-")[-1].isdigit()] or [0])
	stamp, user = now(), "Administrator"
	values = [[f"SITE-{last + i:05d}", stamp, stamp, user, user, 0, 0, *row] for i, row in enumerate(new, start=1)]
	frappe.db.bulk_insert("Site", ["name", "creation", "modified", "owner", "modified_by", "docstatus", "idx",
		"site_name", "node", "b_location", "vendor_name", "month"], values, chunk_size=1000)
	_set_series("SITE-", last + len(new))
	# 2026-11-28: the counter "format:SITE-{#####}" really uses (shared, empty name)
	_set_series("", last + len(new))


def match_link_register(rows):
	"""Step 3: FTTH Link blanks (GIS, A End) from the master; missing master Link IDs added."""
	nodes = {n.upper(): n for n in frappe.get_all("GIS Node", pluck="name")}
	by_link = {}
	for r in rows:
		link = (r.evisions_link_id or "").strip()
		if link and link != "OK" and link not in by_link:
			by_link[link] = r  # a Link ID shared by several sites: the first site, as for Network Link
	links = {l.name: l for l in frappe.get_all("FTTH Link", fields=["name", "gis", "a_end"])}
	for link, r in by_link.items():
		node = nodes.get(r.gis)
		current = links.get(link)
		if current:
			blanks = {}
			if node and not current.gis:
				blanks["gis"] = node
			if r.end_location_name and not current.a_end:
				blanks["a_end"] = r.end_location_name
			if blanks:
				frappe.db.set_value("FTTH Link", link, blanks, update_modified=False)
			continue
		distance = flt(r.final_distance) if re.fullmatch(r"\d+(?:\.\d+)?", (r.final_distance or "").strip()) else 0
		frappe.get_doc({"doctype": "FTTH Link", "link_id": link, "company": "Airtel", "link_type": "FTTH",
			"a_end": r.end_location_name, "b_end": r.survey_b_end, "area": r.area, "gis": node,
			"distance": distance, "source_file": "FTTH Master Data"}).insert(ignore_permissions=True)


def _set_series(prefix, value):
	"""Moves a naming series up to value (never down)."""
	found = frappe.db.sql("select `current` from `tabSeries` where `name` = %s", prefix)
	if not found:
		frappe.db.sql("insert into `tabSeries` (`name`, `current`) values (%s, %s)", (prefix, value))
	elif found[0][0] < value:
		frappe.db.sql("update `tabSeries` set `current` = %s where `name` = %s", (value, prefix))
