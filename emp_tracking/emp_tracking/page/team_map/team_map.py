# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Team Map (Desk page /app/team-map): data. Created 2026-11-28 (user: "make new map for team
# assignment view").
#
# How this file works
#   get_team_map() returns, in one call, what the page draws:
#     teams       one card per EVisions team with an area (TEAM 1-6): colour, area, area manager,
#                 leader, splicers / riders, localities, links, open complaints, links of other areas;
#     boundaries  each team area's boundary ring (Area.boundary);
#     nodes       GIS Nodes with a position (their own KMZ pin, named with the GIS code) and team area;
#     links       Network Links with a position: [lat, lon, assigned team, area team, linkid] - a link
#                 assigned to a team whose area is not the link's area is a "mismatch";
#     complaints  open complaints with a position (own, else their LINKID's): team, area team.
#   Reads go through frappe.get_list / permissions of the page's roles.
# ---------------------------------------------------------------------------------------------

import json

import frappe
from frappe.utils import cint, flt

OPEN_DONE = ("Closed", "Resolved", "Rejected", "Fiber Restored", "Awaiting Operator Confirmation")


# Date: 2026-11-28
@frappe.whitelist()
def get_team_map():
	frappe.has_permission("Maintenance Team", "read", throw=True)
	areas = {a.name: a for a in frappe.get_all("Area", filters={"is_team_area": 1},
		fields=["name", "field_manager", "field_manager_no", "boundary"], order_by="name asc")}
	team_rows = frappe.get_all("Maintenance Team", filters={"team_type": "EVisions", "area": ["in", list(areas) or [""]]},
		fields=["name", "area", "team_colour", "team_leader_name", "status"], order_by="name asc")
	team_of_area = {t.area: t.name for t in team_rows}
	area_of_team = {t.name: t.area for t in team_rows}

	# members by role, localities per area
	roles = {}
	for m in frappe.db.sql("""select parent, role, count(*) n from `tabMaintenance Team Member`
			where coalesce(active, 0) = 1 group by parent, role""", as_dict=True):
		roles.setdefault(m.parent, {})[m.role] = cint(m.n)
	places = dict(frappe.db.sql("select team_area, count(*) from `tabArea` where coalesce(team_area, '') != '' group by team_area"))

	# links with a position
	links, link_count, link_mismatch = [], {}, {}
	for l in frappe.get_list("Network Link", fields=["name", "latitude", "longitude", "maintenance_team", "area"],
			filters={"latitude": ["!=", 0]}, limit_page_length=0):
		if not (flt(l.latitude) and flt(l.longitude)):
			continue
		team = l.maintenance_team or ""
		area_team = team_of_area.get(l.area or "", "")
		if team in area_of_team:
			link_count[team] = link_count.get(team, 0) + 1
			if area_team and team != area_team:
				link_mismatch[team] = link_mismatch.get(team, 0) + 1
		links.append([round(flt(l.latitude), 5), round(flt(l.longitude), 5), team, area_team, l.name])

	# open complaints: own position, else the LINKID's
	link_pos = {l[4]: (l[0], l[1]) for l in links}
	complaints, open_count = [], {}
	for c in frappe.get_list("Complaint Information", filters={"workflow_state": ["not in", OPEN_DONE]},
			fields=["name", "latitude", "longitude", "linkid", "maintenance_team", "mapped_vendor", "team_area",
				"society_name", "workflow_state"], limit_page_length=0):
		pos = (flt(c.latitude), flt(c.longitude)) if flt(c.latitude) and flt(c.longitude) else link_pos.get(c.linkid)
		team = c.maintenance_team or ""
		if team:
			open_count[team] = open_count.get(team, 0) + 1
		if pos:
			complaints.append([pos[0], pos[1], team or (c.mapped_vendor or ""), team_of_area.get(c.team_area or "", ""),
				c.name, c.society_name or "", c.workflow_state])

	# node positions: the node's own KMZ pin ("D1J" / "D1J Node")
	node_area = dict(frappe.db.sql("select name, team_area from `tabGIS Node` where coalesce(team_area, '') != ''"))
	nodes, seen = [], set()
	for p in frappe.db.sql("""select gis, upper(trim(point_name)) pname, latitude, longitude from `tabKMZ Point`
			where coalesce(gis, '') != ''""", as_dict=True):
		code = p.gis.upper()
		if code in seen or p.pname not in (code, code + " NODE") or not (flt(p.latitude) and flt(p.longitude)):
			continue
		seen.add(code)
		nodes.append([round(flt(p.latitude), 5), round(flt(p.longitude), 5), p.gis, team_of_area.get(node_area.get(p.gis, ""), "")])

	teams = []
	for t in team_rows:
		a = areas.get(t.area) or frappe._dict()
		teams.append({
			"name": t.name, "area": t.area, "colour": t.team_colour or "#2563eb", "status": t.status,
			"leader": t.team_leader_name, "manager": a.field_manager, "manager_no": a.field_manager_no,
			"splicers": roles.get(t.name, {}).get("Splicer", 0), "riders": roles.get(t.name, {}).get("Rider", 0),
			"places": cint(places.get(t.area)), "links": link_count.get(t.name, 0),
			"links_other_area": link_mismatch.get(t.name, 0), "open": open_count.get(t.name, 0),
		})
	boundaries = {}
	for name, a in areas.items():
		try:
			ring = json.loads(a.boundary or "[]")
		except ValueError:
			ring = []
		if len(ring) >= 3:
			boundaries[name] = ring
	return {"teams": teams, "boundaries": boundaries, "nodes": nodes, "links": links, "complaints": complaints}
