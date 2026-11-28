# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Area: a locality (Baner, Warje ...) or, with "EVision Team Area" ticked, one of the six EVision
# team areas (Area 1-6) with its Area Manager (Field Staff) and its boundary from the team KMZ.
#
# Change log
#   2026-11-27  Team areas: boundary + Field Staff manager; team_area_at() finds the team area a
#               point lies in (used by Network Link and patches/evision_team_areas.py).
#   2026-11-27  area_managers() / team_area_of_node(): a complaint's Area Manager from its node's
#               team area (Complaint Information).
#   2026-11-27  A locality has a Team Area (team_area_of), so a complaint with no node still gets
#               the manager of its locality's team area.
#   2026-11-28  Area is a tree (NestedSet, parent_area = Team Area): Areas opens as Area 1-6 with their
#               localities under them (area_tree.js, patch area_tree).
#   2026-11-28  add_to_team_area(): add unassigned localities to a team area from a team's form.
# ---------------------------------------------------------------------------------------------

import json

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet

CACHE_KEY = "emp_tracking:team_area_boundaries"


# 2026-11-28: kept here (was imported from KMZ Polygon), so Area and the NOC complaint flow do not
# depend on the OverHead KMZ code; KMZ Polygon imports it from here
def point_in_ring(lat, lon, ring):
	"""True when (lat, lon) is inside the [[lat, lon], ...] ring (ray casting)."""
	inside = False
	j = len(ring) - 1
	for i in range(len(ring)):
		yi, xi = ring[i]
		yj, xj = ring[j]
		if (xi > lon) != (xj > lon) and lat < (yj - yi) * (lon - xi) / (xj - xi) + yi:
			inside = not inside
		j = i
	return inside


# 2026-11-28: a tree (user: "only show Team 1 .. 6 and under teams the area names"): team areas
# are the groups, each locality sits under its Team Area; a locality with no team area yet is at
# the top until one is set
class Area(NestedSet):
	nsm_parent_field = "parent_area"

	# Date: 2026-11-27 (2026-11-28: tree place from the Team Area)
	def validate(self):
		if self.is_team_area:
			self.is_group, self.parent_area, self.team_area = 1, None, None
		else:
			self.is_group = 0
			self.parent_area = self.team_area or None
		if self.boundary:
			try:
				ring = json.loads(self.boundary)
			except ValueError:
				frappe.throw(frappe._("Boundary must be JSON: [[latitude, longitude], ...]"))
			if not isinstance(ring, list) or len(ring) < 3:
				frappe.throw(frappe._("Boundary needs at least 3 corners."))

	def on_update(self):
		super().on_update()  # NestedSet keeps the tree (lft / rgt) in order

	def on_change(self):
		frappe.cache.delete_value(CACHE_KEY)


# Date: 2026-11-28
@frappe.whitelist()
def get_tree_children(doctype=None, parent=None, is_root=False, **kwargs):
	"""Areas tree: at the top only the team areas (Area 1-6, with their manager), under each its
	localities A-Z. Localities without a team area are not in the tree (the page links to them)."""
	frappe.has_permission("Area", "read", throw=True)
	if not parent or frappe.utils.cint(is_root) or parent == _("All Areas"):
		rows = frappe.get_all("Area", filters={"is_team_area": 1}, fields=["name", "field_manager"], order_by="name asc")
		counts = dict(frappe.db.sql("select parent_area, count(*) from `tabArea` where coalesce(parent_area, '') != '' group by parent_area"))
		return [{"value": r.name, "expandable": 1,
			"title": f"{r.name} · {r.field_manager or _('no manager')} · {_('{0} areas').format(counts.get(r.name, 0))}"}
			for r in rows]
	return [{"value": r.name, "expandable": 0, "title": r.name}
		for r in frappe.get_all("Area", filters={"parent_area": parent}, fields=["name"], order_by="name asc")]


# Date: 2026-11-28
@frappe.whitelist(methods=["POST"])
def add_to_team_area(team_area, areas):
	"""Puts localities that are in no team area yet under a team area (user: "add row, only from
	the areas not assigned anywhere"). Each Area is saved, so the tree follows. Complaints in those
	localities that have no team area yet get this one and its Area Manager."""
	frappe.has_permission("Area", "write", throw=True)
	areas = frappe.parse_json(areas) if isinstance(areas, str) else areas
	if not frappe.db.get_value("Area", team_area, "is_team_area"):
		frappe.throw(_("{0} is not one of the team areas (Area 1-6).").format(team_area))
	staff, user = area_managers(team_area)
	added = []
	for name in areas or []:
		row = frappe.db.get_value("Area", name, ["is_team_area", "team_area"], as_dict=True)
		if not row or row.is_team_area or row.team_area:
			continue  # a team area itself, or already in a team: never moved from here
		doc = frappe.get_doc("Area", name)
		doc.team_area = team_area
		doc.save()
		added.append(name)
	if added:
		frappe.db.sql("""update `tabComplaint Information` set team_area = %s,
			area_manager_staff = coalesce(nullif(area_manager_staff, ''), %s)
			where area in %s and coalesce(team_area, '') = ''""", (team_area, staff, tuple(added)))
	return added


def team_area_boundaries():
	"""[(area name, ring)] of the active team areas, cached until an Area is saved."""
	rows = frappe.cache.get_value(CACHE_KEY)
	if rows is None:
		rows = []
		for a in frappe.get_all("Area", filters={"is_team_area": 1, "status": "Active", "boundary": ["is", "set"]},
				fields=["name", "boundary"], order_by="name asc"):
			try:
				rows.append((a.name, json.loads(a.boundary)))
			except ValueError:
				continue
		frappe.cache.set_value(CACHE_KEY, rows)
	return rows


# Date: 2026-11-27
def area_managers(area):
	"""(Field Staff, User or None) of an Area. The User is the Area's own Area Manager login, else
	an enabled User whose full name is the Field Staff's name (the managers have no logins yet)."""
	if not area:
		return None, None
	row = frappe.db.get_value("Area", area, ["field_manager", "area_manager"], as_dict=True) or {}
	staff, user = row.get("field_manager"), row.get("area_manager")
	if staff and not user:
		name = frappe.db.get_value("Field Staff", staff, "staff_name") or staff
		user = frappe.db.get_value("User", {"full_name": name, "enabled": 1}, "name")
	return staff, user


def team_area_of(area):
	"""The team area of an Area: itself when it is one, else the locality's Team Area."""
	if not area:
		return None
	row = frappe.db.get_value("Area", area, ["is_team_area", "team_area"], as_dict=True)
	if not row:
		return None
	return area if row.is_team_area else row.team_area


@frappe.whitelist()
def team_area_of_node(node, area=None):
	"""Team area and its managers for the Complaint form: from the GIS Node's Team Area, else
	(from_node false) from the complaint's Area / locality."""
	team = frappe.db.get_value("GIS Node", (node or "").strip().upper(), "team_area") if node else None
	from_node = bool(team)
	team = team or team_area_of(area)
	staff, user = area_managers(team)
	# 2026-11-28: the EVisions team working that area, the complaint's default team (NOC flow check)
	crew = frappe.db.get_value("Maintenance Team", {"area": team, "team_type": "EVisions", "status": "Active"}, "name") if team else None
	return {"area": team, "staff": staff, "user": user, "from_node": from_node, "team": crew}


# Date: 2026-11-27
def team_area_at(lat, lon):
	"""Name of the team area whose boundary holds (lat, lon), or None."""
	if not lat or not lon:
		return None
	for name, ring in team_area_boundaries():
		if point_in_ring(float(lat), float(lon), ring):
			return name
	return None
