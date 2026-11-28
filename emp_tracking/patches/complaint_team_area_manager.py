# ---------------------------------------------------------------------------------------------
# Patch: existing complaints get the Area and Area Manager (Field Staff) of their node's EVision
# team area (GIS Node.team_area, set by evision_team_areas). Created 2026-11-27, user's request
# "assign area manager according to area in complaint". Runs after evision_team_areas; safe to
# run again. Complaints whose node has no team area are left as they are. The Area Manager login
# (area_manager) is only filled where it was empty and the area's manager has a login.
# ---------------------------------------------------------------------------------------------

import frappe

from emp_tracking.emp_tracking.doctype.area.area import area_managers


def execute():
	frappe.reload_doc("emp_tracking", "doctype", "complaint_information")
	areas = frappe.get_all("Area", filters={"is_team_area": 1}, pluck="name")
	for area in areas:
		staff, user = area_managers(area)
		nodes = frappe.get_all("GIS Node", filters={"team_area": area}, pluck="name")
		if not nodes:
			continue
		for start in range(0, len(nodes), 500):
			chunk = tuple(nodes[start:start + 500])
			frappe.db.sql("""update `tabComplaint Information` set area = %s, area_manager_staff = %s
				where upper(node_id) in %s""", (area, staff, chunk))
			if user:
				frappe.db.sql("""update `tabComplaint Information` set area_manager = %s
					where upper(node_id) in %s and coalesce(area_manager, '') = ''""", (user, chunk))
	frappe.db.commit()
	placed = frappe.db.count("Complaint Information", {"area_manager_staff": ["is", "set"]})
	print(f"Complaint team area / manager: {placed} complaints have a team area manager")
