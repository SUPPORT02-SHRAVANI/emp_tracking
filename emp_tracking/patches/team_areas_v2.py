# ---------------------------------------------------------------------------------------------
# Patch: the updated team areas map (2026-11-28, user: "this is updated teams map", file
# "Evision team (1).kmz"). Areas 1, 2, 3 and 5 got smaller (116 -> 46, 46 -> 31, 199 -> 144,
# 125 -> 68 km2); Areas 4 and 6 are unchanged. evision_team_areas.json now holds the new
# boundaries, and everything placed with the old ones is placed again, with the same rules:
#   1. Old placements cleared: GIS Node Team Area / Area Manager; Network Links whose Area is a
#      team area go back to their locality (Location, when it is an Area) or "Pune" (Area is
#      required); localities' Team Area; complaints' Team Area / Area Manager.
#   2. evision_team_areas (boundaries, managers, shapes, nodes, links) run again.
#   3. locality_team_areas (each locality's Team Area from the placed data) run again.
#   4. Complaints: Team Area from the node, else the locality; Area Manager = that area's manager;
#      a complaint on a node takes the node's team area as Area (as before).
#   5. The Areas tree is rebuilt.
# Teams' members, colours and the links' assigned teams are not touched. Safe to run again.
# ---------------------------------------------------------------------------------------------

import frappe


def execute():
	from emp_tracking.patches import area_tree, evision_team_areas, locality_team_areas

	teams = tuple(frappe.get_all("Area", filters={"is_team_area": 1}, pluck="name")) or ("",)
	localities = {a.lower(): a for a in frappe.get_all("Area", filters={"is_team_area": 0}, pluck="name")}

	# 1. clear what the old boundaries decided
	frappe.db.sql("update `tabGIS Node` set team_area = null, area_manager = null, area_manager_no = null")
	fallback = "Pune" if frappe.db.exists("Area", "Pune") else None  # 2026-11-28: only an Area that exists
	for name, location in frappe.db.sql("select name, location from `tabNetwork Link` where area in %s", (teams,)):
		back = localities.get((location or "").strip().lower(), fallback)
		if back:
			frappe.db.set_value("Network Link", name, "area", back, update_modified=False)
	frappe.db.sql("update `tabArea` set team_area = null where coalesce(is_team_area, 0) = 0")
	frappe.db.sql("update `tabComplaint Information` set team_area = null, area_manager_staff = null")
	frappe.db.commit()

	# 2. + 3. place again with the new boundaries
	evision_team_areas.execute()
	locality_team_areas.execute()

	# 4. complaints
	C = "`tabComplaint Information`"
	frappe.db.sql(f"""update {C} c join `tabGIS Node` g on g.name = c.node_id
		set c.team_area = g.team_area, c.area = g.team_area where coalesce(g.team_area, '') != ''""")
	frappe.db.sql(f"""update {C} c join `tabArea` a on a.name = c.area
		set c.team_area = if(a.is_team_area = 1, a.name, a.team_area) where coalesce(c.team_area, '') = ''""")
	frappe.db.sql(f"""update {C} c join `tabArea` a on a.name = c.team_area
		set c.area_manager_staff = a.field_manager where coalesce(a.field_manager, '') != ''""")
	frappe.db.commit()

	# 5. tree
	area_tree.execute()
	print("Team areas v2:",
		frappe.db.sql("select team_area, count(*) from `tabGIS Node` group by team_area"),
		"| links:", frappe.db.sql("select area, count(*) from `tabNetwork Link` where area in %s group by area", (teams,)),
		"| localities placed:", frappe.db.count("Area", {"is_team_area": 0, "team_area": ["is", "set"]}),
		"| complaints with a team area:", frappe.db.count("Complaint Information", {"team_area": ["is", "set"]}))
