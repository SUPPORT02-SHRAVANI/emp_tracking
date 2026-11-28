# ---------------------------------------------------------------------------------------------
# Patch: the six EVision team areas (Area 1-6) and their Area Managers. Created 2026-11-27.
#
# Data: evision_team_areas.json next to this file. Boundaries come from the user's
# "Evision team.kmz" (placemarks Team 1-6), and managers from the user's list:
#   Area 1 Akash Pardeshi, Area 2 Rahul Dilliwala, Area 3 Sanket Khandare, Area 4 Sachin Khude,
#   Area 5 Vilas Gaikwad, Area 6 Amar Belapurkar.
#
# What it does (safe to run again):
#   1. Area "Area N" with the "EVision Team Area" tick, code AN, its boundary and its manager.
#      The manager is a Field Staff record, made as "Area Manager" when missing.
#   2. Maintenance Team "TEAM N" gets Area N and the manager's name.
#   3. Every Network Link whose latitude / longitude is inside a boundary gets that Area. The
#      locality stays in Location.
#   4. Every GIS Node gets a Team Area, and that area's manager as Area Manager (the user chose to
#      replace the old managers). The area is decided in this order:
#        - the node's own KMZ pin (named with its GIS code), if it lies inside a boundary;
#        - else the area that most of its Network Links lie in;
#        - else the "Team N" most of its FTTH Master Data rows name.
#      Links with no coordinates, or outside every boundary, take their node's area.
#   5. A KMZ Polygon per area (KMZ path "EVision Team Areas"), so the KMZ Map draws the boundaries.
#
# Change log
#   2026-11-28  Boundaries from the updated "Evision team (1).kmz" (evision_team_areas.json).
#   2026-11-28  Step 5 only when the KMZ Polygon doctype is in the app (it is committed separately
#               with the OverHead KMZ work); point_in_ring comes from Area.
# ---------------------------------------------------------------------------------------------

import json
import os
from collections import Counter, defaultdict

import frappe

from emp_tracking.emp_tracking.doctype.area.area import CACHE_KEY
from emp_tracking.emp_tracking.doctype.area.area import point_in_ring

SOURCE = "Evision team.kmz"
FOLDER = "EVision Team Areas"


def execute():
	for doctype, module in (("area", "emp_tracking"), ("network_link", "emp_tracking"), ("gis_node", "ftth")):
		frappe.reload_doc(module, "doctype", doctype)
	# 2026-11-28: KMZ Polygon (OverHead KMZ code) may not be on the site yet; its shapes are then skipped
	has_polygons = os.path.exists(os.path.join(frappe.get_app_path("emp_tracking"), "ftth", "doctype", "kmz_polygon"))
	if has_polygons:
		frappe.reload_doc("ftth", "doctype", "kmz_polygon")
	with open(os.path.join(os.path.dirname(__file__), "evision_team_areas.json"), encoding="utf8") as f:
		areas = json.load(f)["areas"]

	staff = {name: ensure_staff(a["manager"]) for name, a in areas.items()}
	for name, a in areas.items():
		save_area(name, a, staff[name])
		set_team(a["team"], name, staff[name])
		if has_polygons:
			add_polygon(name, a)
	frappe.cache.delete_value(CACHE_KEY)

	rings = [(name, a["boundary"]) for name, a in areas.items()]

	def area_at(lat, lon):
		if not lat or not lon:
			return None
		return next((name for name, ring in rings if point_in_ring(float(lat), float(lon), ring)), None)

	# 3. links by their own position; votes per node
	links = frappe.db.sql("select name, node_id, latitude, longitude from `tabNetwork Link`", as_dict=True)
	link_area, votes = {}, defaultdict(Counter)
	for l in links:
		a = area_at(l.latitude, l.longitude)
		if a:
			link_area[l.name] = a
			if l.node_id:
				votes[l.node_id.upper()][a] += 1

	# 4. node area: own pin, else its links, else the master data's team
	nodes = frappe.get_all("GIS Node", pluck="name")
	codes = {n.upper(): n for n in nodes}
	pin_area = {}
	for p in frappe.db.sql("""select gis, upper(trim(point_name)) pname, latitude, longitude from `tabKMZ Point`
			where gis is not null and gis != ''""", as_dict=True):
		code = p.gis.upper()
		if p.pname in (code, code + " NODE") and code not in pin_area:
			a = area_at(p.latitude, p.longitude)
			if a:
				pin_area[code] = a
	team_votes = defaultdict(Counter)
	if frappe.db.exists("DocType", "FTTH Master Data"):
		for r in frappe.db.sql("""select upper(gis) gis, team, count(*) n from `tabFTTH Master Data`
				where team like 'Team %%' group by upper(gis), team""", as_dict=True):
			number = (r.team or "").split()[-1]
			if f"Area {number}" in areas:
				team_votes[r.gis][f"Area {number}"] += r.n

	node_area, how = {}, Counter()
	for code, name in codes.items():
		if code in pin_area:
			node_area[name] = pin_area[code]; how["node pin"] += 1
		elif votes.get(code):
			node_area[name] = votes[code].most_common(1)[0][0]; how["its links"] += 1
		elif team_votes.get(code):
			node_area[name] = team_votes[code].most_common(1)[0][0]; how["master data team"] += 1
		else:
			how["not placed"] += 1

	by_area = defaultdict(list)
	for node, a in node_area.items():
		by_area[a].append(node)
	for a, names in by_area.items():
		contact = frappe.db.get_value("Field Staff", staff[a], "contact_no") or ""
		for chunk in chunks(names):
			frappe.db.sql("""update `tabGIS Node` set team_area = %s, area_manager = %s, area_manager_no = %s
				where name in %s""", (a, staff[a], contact, tuple(chunk)))

	# links outside every boundary (or with no position) follow their node
	for l in links:
		if l.name not in link_area and l.node_id and codes.get(l.node_id.upper()) in node_area:
			link_area[l.name] = node_area[codes[l.node_id.upper()]]
	link_by_area = defaultdict(list)
	for name, a in link_area.items():
		link_by_area[a].append(name)
	for a, names in link_by_area.items():
		for chunk in chunks(names):
			frappe.db.sql("update `tabNetwork Link` set area = %s where name in %s", (a, tuple(chunk)))

	frappe.db.commit()
	print(f"EVision team areas: {len(node_area)} of {len(nodes)} GIS Nodes placed {dict(how)}; "
		f"{len(link_area)} of {len(links)} Network Links; per area nodes "
		f"{ {a: len(v) for a, v in sorted(by_area.items())} }")


def chunks(names, size=1000):
	for i in range(0, len(names), size):
		yield names[i:i + size]


def ensure_staff(staff_name):
	"""The Field Staff named staff_name (any case), made as an active Area Manager when missing."""
	found = frappe.db.get_value("Field Staff", {"staff_name": staff_name}, "name")
	if found:
		return found
	doc = frappe.get_doc({"doctype": "Field Staff", "staff_name": staff_name, "staff_type": "Area Manager", "is_active": 1})
	doc.insert(ignore_permissions=True)
	return doc.name


def save_area(name, a, manager):
	doc = frappe.get_doc("Area", name) if frappe.db.exists("Area", name) else frappe.new_doc("Area")
	doc.update({"area_name": name, "area_code": doc.area_code or a["code"], "status": "Active", "is_team_area": 1,
		"field_manager": manager, "boundary": json.dumps(a["boundary"], separators=(",", ":"))})
	doc.save(ignore_permissions=True)


def set_team(team, area, manager):
	"""Maintenance Team 'TEAM N' (any case) gets its area and manager; skipped when there is none."""
	name = frappe.db.get_value("Maintenance Team", {"team_name": team}, "name")
	if name:
		frappe.db.set_value("Maintenance Team", name, {"area": area,
			"manager_name": frappe.db.get_value("Field Staff", manager, "staff_name") or manager}, update_modified=False)


def add_polygon(name, a):
	key = f"evision team area|{name.lower()}"
	values = {"polygon_name": name, "boundary": json.dumps(a["boundary"], separators=(",", ":")),
		"line_colour": a["colour"], "fill_colour": a["colour"], "fill_opacity": 0.08, "source_file": SOURCE,
		"kmz_path": FOLDER, "node_folder": FOLDER, "dedupe_key": key}
	old = frappe.db.get_value("KMZ Polygon", {"dedupe_key": key}, "name")
	doc = frappe.get_doc("KMZ Polygon", old) if old else frappe.new_doc("KMZ Polygon")
	doc.update(values)
	doc.save(ignore_permissions=True)
