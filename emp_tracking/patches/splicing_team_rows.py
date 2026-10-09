# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Patch: move New Project Rider / Splicer into the Splicing Team table
#
# How this file works
#   New Project's single Rider and Splicer fields were replaced by the Splicing Team table
#   (Rider + Splicer pairs). Frappe keeps the old columns in the database, so this patch reads
#   them and writes one row per project that had a Rider or Splicer, sets "Splicing Team
#   Required No", then recalculates every project's Stage. The Assistant Splicer was dropped
#   on request and is not carried over (its value stays in the old database column).
#
# Change log
#   2026-10-09  Created.
# ---------------------------------------------------------------------------------------------

import frappe


# Date: 2026-10-09
def execute():
	"""Copy old Rider / Splicer into a first Splicing Team row, then refresh stages."""
	frappe.reload_doc("emp_tracking", "doctype", "project_splicing_team_member")
	frappe.reload_doc("emp_tracking", "doctype", "new_project")
	if frappe.db.has_column("New Project", "splicer") and frappe.db.has_column("New Project", "splicing_rider"):
		old = frappe.db.sql(
			"""select name, splicing_rider, splicer from `tabNew Project`
			where ifnull(splicer, '') != '' or ifnull(splicing_rider, '') != ''""",
			as_dict=True,
		)
		for project in old:
			if frappe.db.exists("Project Splicing Team Member", {"parent": project.name, "parenttype": "New Project"}):
				continue
			frappe.get_doc({
				"doctype": "Project Splicing Team Member",
				"parent": project.name,
				"parenttype": "New Project",
				"parentfield": "splicing_team",
				"idx": 1,
				"rider": project.splicing_rider,
				"rider_name": frappe.db.get_value("Employee", project.splicing_rider, "employee_name") if project.splicing_rider else None,
				"splicer": project.splicer,
				"splicer_name": frappe.db.get_value("Employee", project.splicer, "employee_name") if project.splicer else None,
			}).db_insert()
			frappe.db.set_value("New Project", project.name, "splicing_team_required_no", 1, update_modified=False)

	from emp_tracking.patches.oh_project_masters import refresh_projects

	refresh_projects()
