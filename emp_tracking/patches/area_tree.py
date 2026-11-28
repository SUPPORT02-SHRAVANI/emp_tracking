# ---------------------------------------------------------------------------------------------
# Patch: Area becomes a tree (2026-11-28, user: "only show Team 1 .. 6 and under teams the area
# names"). Team areas are the groups; each locality goes under its Team Area (parent_area);
# localities with no team area yet stay at the top. Then the tree's lft / rgt are built.
# Safe to run again.
# ---------------------------------------------------------------------------------------------

import frappe
from frappe.utils.nestedset import rebuild_tree


def execute():
	frappe.reload_doc("emp_tracking", "doctype", "area")
	frappe.db.sql("update `tabArea` set is_group = 1, parent_area = null where is_team_area = 1")
	frappe.db.sql("""update `tabArea` set is_group = 0,
		parent_area = if(coalesce(team_area, '') = '', null, team_area) where coalesce(is_team_area, 0) = 0""")
	rebuild_tree("Area")
	frappe.db.commit()
