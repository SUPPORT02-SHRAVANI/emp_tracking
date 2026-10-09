# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Project Fiber Team Member: one row of the Fiber Team table on a New Project.
#
# How this file works
#   Each row is one employee the Area Manager added to the project's Fiber Team. The employee
#   name and mobile number are filled from the Employee record. There is no logic here; the
#   duplicate-employee check is in new_project.py.
#
# Change log
#   2026-10-07  Created with Employee, Employee Name, Role in Team and Mobile No.
#   2026-10-07  Role in Team removed: Rider and Splicer belong to the Splicing Team.
#   2026-10-07  Added this header.
# ---------------------------------------------------------------------------------------------

from frappe.model.document import Document


class ProjectFiberTeamMember(Document):
	pass
