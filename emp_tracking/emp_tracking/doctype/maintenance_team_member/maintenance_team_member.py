# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Maintenance Team Member: one person in a Maintenance Team (child table "Members")
#
# How this file works
#   No logic. The NOC Team Availability report reads these rows: a team's members who are
#   Present in Attendance on a day are its available people that day.
#
# Change log
#   2026-11-26  Created (user's request: per day, how many splicers a team had and who was assigned).
# ---------------------------------------------------------------------------------------------

from frappe.model.document import Document


class MaintenanceTeamMember(Document):
	pass
