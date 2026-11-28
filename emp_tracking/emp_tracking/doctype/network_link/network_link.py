# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Network Link
#
# Change log
#   2026-11-27  Area is the EVision team area (Area 1-6) the link's latitude / longitude lies in,
#               when it has no team area yet (user's request: links under the six team areas).
#               The locality stays in Location.
#   2026-11-28  New link flow: with no position, Area = its node's Team Area; with no team and no
#               vendor, the EVisions team of that area (TEAM N), as on complaints.
# ---------------------------------------------------------------------------------------------

import frappe
from frappe.model.document import Document

from emp_tracking.emp_tracking.doctype.area.area import team_area_at


class NetworkLink(Document):
	# Date: 2026-11-27 (2026-11-28: node's team area, default team)
	def validate(self):
		is_team_area = lambda a: a and frappe.db.get_value("Area", a, "is_team_area")
		if self.latitude and self.longitude and not is_team_area(self.area):
			self.area = team_area_at(self.latitude, self.longitude) or self.area
		if not is_team_area(self.area) and self.node_id:
			self.area = frappe.db.get_value("GIS Node", self.node_id.strip().upper(), "team_area") or self.area
		if not self.maintenance_team and not self.mapped_vendor and is_team_area(self.area):
			self.maintenance_team = frappe.db.get_value("Maintenance Team",
				{"area": self.area, "team_type": "EVisions", "status": "Active"}, "name")
			if self.maintenance_team and not self.maintenance_responsibility:
				self.maintenance_responsibility = "EVisions"
