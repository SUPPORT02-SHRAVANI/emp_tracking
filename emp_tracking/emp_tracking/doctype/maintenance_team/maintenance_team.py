# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Maintenance Team: master (EVisions Team 1-6 or a vendor team)
#
# How this file works
#   Each team has a Team Leader (Employee) who is also the supervisor on projects, and a
#   Manager. New Project copies "Team Leader / Supervisor Name" and "Manager Name" from here.
#   On save, the leader's name is filled from the chosen Employee.
#
# Change log
#   2026-10-09  Added Team Leader / Supervisor Name and Manager Name; leader name from Employee.
# ---------------------------------------------------------------------------------------------

import frappe
from frappe.model.document import Document


class MaintenanceTeam(Document):
	# Date: 2026-10-09
	def validate(self):
		"""Fill the leader's name from the Employee when one is chosen (typed names are kept otherwise)."""
		if self.team_leader:
			self.team_leader_name = frappe.db.get_value("Employee", self.team_leader, "employee_name") or self.team_leader_name
