# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Patch: create the Airtel FTTH Network Links from FTTH Master Data
#
# How this file works
#   The Complaint form finds a complaint's LINKID by the node in the operator's message
#   (complaint_information.js pick_link_by_node: Network Link where Node ID = the node). Network
#   Link held only two demo links, so every real node failed ("No Network Link has Node ID GGG").
#   FTTH Master Data (9,730 sites) has each site's Evisions Link ID and node (GIS); this patch
#   makes one Network Link per Link ID from it:
#     linkid = Evisions Link ID, network_type FTTH, operator Airtel, status Active,
#     node_id = gis_node_id = GIS, society_building = site name, location = the sheet's area text,
#     latitude / longitude from the site's lat-long,
#     area = the Area record of the same name, else "Pune" (Area is mandatory),
#     "Team 1".."Team 6" -> EVisions + that Maintenance Team; a vendor name that matches a
#     Maintenance Vendor -> Vendor + that vendor; any other vendor text -> Vendor; blank -> EVisions.
#   A Link ID used by several sites takes the first site. Link IDs that already exist are never
#   touched, and "OK" (a placeholder in the sheet) is skipped. One bulk insert, like the master.
#
# Change log
#   2026-11-27  Created (user: "to solve this error I gave you the master data").
# ---------------------------------------------------------------------------------------------

import re

import frappe
from frappe.utils import flt, now

DEFAULT_AREA = "Pune"


# Date: 2026-11-27
def execute():
	if not frappe.db.exists("DocType", "FTTH Master Data") or not frappe.db.exists("DocType", "Network Link"):
		return
	frappe.reload_doc("emp_tracking", "doctype", "network_link")

	existing = {n.lower() for n in frappe.get_all("Network Link", pluck="name")}
	# lower-case name -> exact name, so "SPINE TELICOM" finds the record however it is spelled in case
	areas = {a.lower(): a for a in frappe.get_all("Area", pluck="name")}
	teams = {t.lower(): t for t in frappe.get_all("Maintenance Team", pluck="name")}
	vendors = {v.lower(): v for v in frappe.get_all("Maintenance Vendor", pluck="name")}
	default_area = areas.get(DEFAULT_AREA.lower()) or next(iter(areas.values()), None)
	if not default_area:
		return  # no Area at all: Network Link cannot be created on this site

	sites = frappe.get_all(
		"FTTH Master Data",
		filters={"evisions_link_id": ["not in", ["", "OK"]]},
		fields=["evisions_link_id", "end_location_name", "gis", "area", "team", "end_location_lat_long"],
		order_by="name asc",
	)
	columns = ["name", "creation", "modified", "owner", "modified_by", "docstatus", "idx",
		"linkid", "network_type", "status", "operator", "area", "location", "society_building",
		"node_id", "gis_node_id", "latitude", "longitude",
		"maintenance_responsibility", "maintenance_team", "mapped_vendor"]
	stamp, user, values = now(), "Administrator", []
	for s in sites:
		link = (s.evisions_link_id or "").strip()
		if not link or link.lower() in existing:
			continue
		existing.add(link.lower())  # a Link ID shared by several sites: the first site wins
		lat, lng = _lat_long(s.end_location_lat_long)
		responsibility, team, vendor = _responsibility(s.team, teams, vendors)
		node = (s.gis or "").strip().upper() or None
		values.append([link, stamp, stamp, user, user, 0, 0,
			link, "FTTH", "Active", "Airtel", areas.get((s.area or "").strip().lower(), default_area),
			s.area, s.end_location_name, node, node, lat, lng, responsibility, team, vendor])
	if values:
		frappe.db.bulk_insert("Network Link", columns, values, chunk_size=1000)


def _lat_long(text):
	"""'18.4836, 73.8763' -> (18.4836, 73.8763); anything else -> (0, 0) (columns are NOT NULL)."""
	nums = re.findall(r"-?\d+(?:\.\d+)?", text or "")
	if len(nums) >= 2:
		return flt(nums[0]), flt(nums[1])
	return 0, 0


def _responsibility(team_text, teams, vendors):
	"""Sheet's Team column -> (maintenance_responsibility, maintenance_team, mapped_vendor)."""
	text = (team_text or "").strip()
	if not text:
		return "EVisions", None, None
	if re.fullmatch(r"team\s*\d+", text, re.IGNORECASE):
		return "EVisions", teams.get(re.sub(r"\s+", " ", text.lower())), None
	return "Vendor", None, vendors.get(text.lower())
