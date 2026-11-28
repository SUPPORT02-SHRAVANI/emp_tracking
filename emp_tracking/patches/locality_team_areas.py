# ---------------------------------------------------------------------------------------------
# Patch: every locality Area (Baner, Chakan ...) gets its EVision Team Area (Area 1-6), then
# complaints with no node get that team area's Area Manager. Created 2026-11-27, user's request
# "assign area manager according to area in complaint": most complaints (imported NOC sheets)
# have only a locality, no node.
#
# A locality's team area is the one most often seen with it in data placed by the team area
# boundaries (patches/evision_team_areas.py):
#   - GIS Node: its Area (locality) and its Team Area;
#   - Network Link: its Location (the locality from the master sheet) and its Area (team area);
#   - Complaint: its Area (locality) and its node's Team Area.
# Only localities that are Area records are set, and a Team Area already set by hand is kept.
# Safe to run again.
# ---------------------------------------------------------------------------------------------

from collections import Counter, defaultdict

import frappe

from emp_tracking.emp_tracking.doctype.area.area import area_managers


def execute():
	frappe.reload_doc("emp_tracking", "doctype", "area")
	frappe.reload_doc("emp_tracking", "doctype", "complaint_information")
	teams = set(frappe.get_all("Area", filters={"is_team_area": 1}, pluck="name"))
	if not teams:
		return
	localities = {a.lower(): a for a in frappe.get_all("Area", filters={"is_team_area": 0}, pluck="name")}
	votes = defaultdict(Counter)

	def vote(locality, team, n=1):
		key = localities.get((locality or "").strip().lower())
		if key and team in teams:
			votes[key][team] += n

	for r in frappe.db.sql("""select area, team_area, count(*) n from `tabGIS Node`
			where coalesce(team_area, '') != '' group by area, team_area""", as_dict=True):
		vote(r.area, r.team_area, r.n)
	for r in frappe.db.sql("""select location, area, count(*) n from `tabNetwork Link`
			where coalesce(location, '') != '' group by location, area""", as_dict=True):
		vote(r.location, r.area, r.n)
	for r in frappe.db.sql("""select c.area, g.team_area, count(*) n from `tabComplaint Information` c
			join `tabGIS Node` g on g.name = c.node_id where coalesce(g.team_area, '') != ''
			group by c.area, g.team_area""", as_dict=True):
		vote(r.area, r.team_area, r.n)

	set_count = 0
	for locality, counter in votes.items():
		if not frappe.db.get_value("Area", locality, "team_area"):
			frappe.db.set_value("Area", locality, "team_area", counter.most_common(1)[0][0], update_modified=False)
			set_count += 1

	# complaints with no node team area: the manager of their locality's team area
	for team in teams:
		staff, user = area_managers(team)
		places = frappe.get_all("Area", filters={"team_area": team}, pluck="name")
		if not staff or not places:
			continue
		frappe.db.sql("""update `tabComplaint Information` set area_manager_staff = %s
			where area in %s and coalesce(area_manager_staff, '') = ''""", (staff, tuple(places)))
		if user:
			frappe.db.sql("""update `tabComplaint Information` set area_manager = %s
				where area in %s and coalesce(area_manager, '') = ''""", (user, tuple(places)))
	frappe.db.commit()
	unset = frappe.db.count("Area", {"is_team_area": 0, "team_area": ["is", "not set"]})
	placed = frappe.db.count("Complaint Information", {"area_manager_staff": ["is", "set"]})
	print(f"Locality team areas: {set_count} set, {unset} localities still without one; "
		f"{placed} complaints have an Area Manager")
