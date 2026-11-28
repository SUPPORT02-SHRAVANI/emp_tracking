# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Maintenance Team: master (EVisions Team 1-6 or a vendor team)
#
# How this file works
#   Each team has a Team Leader (Employee) who is also the supervisor on projects, and a
#   Manager. Complaints and Network Links name the team that maintains a link.
#   On save, the leader's name is filled from the chosen Employee.
#
# Change log
#   2026-10-09  Added Team Leader / Supervisor Name and Manager Name; leader name from Employee.
#   2026-10-31  Header: New Project (which copied the leader / manager names) was merged into
#               FTTH Work Order; a work order's Network Link takes the team named in its Team field.
#   2026-11-26  Members table (Maintenance Team Member: employee, role, active), read by the NOC
#               Team Availability report (who was present / assigned per team per day).
#   2026-11-28  One leader field (user: "why two"): Team Leader / Supervisor (Employee); the name
#               is hidden and always follows it (complaints copy it). Team Colour, used for the
#               team's area on the maps ("View team on map" opens the KMZ Map on its area).
#   2026-11-28  No Team Leader (user: "no TL, only area manager"): the leader fields are hidden
#               (the stored Employees are the area managers; app_attendance still gives them the
#               field shift); "Area Manager" (manager_name) always follows the team's Area.
# ---------------------------------------------------------------------------------------------

import frappe
from frappe.model.document import Document


class MaintenanceTeam(Document):
	# Date: 2026-10-09 (2026-11-28: the name always follows the Employee, empty without one;
	# the manager is the Area's Area Manager)
	def validate(self):
		"""The leader's name from the chosen Employee (hidden; kept for the attendance shift rule).
		2026-11-28 (user: "no TL, only area manager"): Manager = the team Area's Area Manager."""
		self.team_leader_name = frappe.db.get_value("Employee", self.team_leader, "employee_name") if self.team_leader else None
		if self.area:
			manager = frappe.db.get_value("Area", self.area, "field_manager")
			if manager:
				self.manager_name = frappe.db.get_value("Field Staff", manager, "staff_name") or manager
