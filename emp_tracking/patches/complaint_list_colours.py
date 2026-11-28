# ---------------------------------------------------------------------------------------------
# Patch: Complaint list colours and Team Area. Created 2026-11-27 (user's requests: coloured
# Status / Operator / Link Status / Link Type badges, and the Area column as Area 1-6 in colours).
#   1. Complaint List Colours gets its default colours when its table is empty.
#   2. Complaint Information.team_area: the node's Team Area, else the Area itself when it is a
#      team area, else the locality's Team Area. Safe to run again.
# ---------------------------------------------------------------------------------------------

import frappe


def execute():
	for doctype in ("complaint_list_colour", "complaint_list_colours", "complaint_information"):
		frappe.reload_doc("emp_tracking", "doctype", doctype)
	from emp_tracking.emp_tracking.doctype.complaint_list_colours.complaint_list_colours import set_defaults

	set_defaults()
	frappe.db.sql("""update `tabComplaint Information` c
		left join `tabGIS Node` g on g.name = c.node_id
		left join `tabArea` a on a.name = c.area
		set c.team_area = coalesce(nullif(g.team_area, ''), if(a.is_team_area = 1, a.name, nullif(a.team_area, '')))""")
	frappe.db.commit()
	print("Complaint team area set on", frappe.db.count("Complaint Information", {"team_area": ["is", "set"]}), "complaints")
