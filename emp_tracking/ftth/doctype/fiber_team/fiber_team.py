# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt

# Fiber Team
# Change log
#   2026-11-28  Team Area (Area 1-6) added (user: "put this in fiber team"); it must be one of the
#               six team areas, not a locality.

import frappe
from frappe import _
from frappe.model.document import Document


class FiberTeam(Document):
	# Date: 2026-11-28
	def validate(self):
		if self.team_area and not frappe.db.get_value("Area", self.team_area, "is_team_area"):
			frappe.throw(_("Team Area must be one of the team areas (Area 1-6), not a locality like {0}.").format(self.team_area))
