# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt

# Change log
#   2026-11-28  New node flow (user: "how does someone add a new node from the start"): the Team
#               Area comes from the area most of the node's Network Links are in when not picked,
#               and the Area Manager always follows the Team Area (Area.field_manager).

import frappe
from frappe.model.document import Document

# GIS Node field -> FTTH Work Order field (the work order shows these read-only)
SHARED_FIELDS = {
	"area": "area",
	"team": "team",
	"company_engineer": "company_engineer",
	"company_engineer_no": "company_engineer_no",
	"manager": "manager",
	"area_manager": "area_manager",
	"area_manager_no": "area_manager_no",
}


class GISNode(Document):
	def before_naming(self):
		self.gis_code = (self.gis_code or "").strip().upper()

	def validate(self):
		self.gis_code = (self.gis_code or "").strip().upper()
		self.set_team_area()

	# Date: 2026-11-28
	def set_team_area(self):
		"""Team Area: the one picked, else the team area most of this node's Network Links are in.
		Area Manager (and its phone) then follows the Team Area's manager."""
		if not self.meta.has_field("team_area"):
			return
		if not self.team_area and self.name:
			rows = frappe.db.sql("""select l.area, count(*) n from `tabNetwork Link` l join `tabArea` a on a.name = l.area
				where l.node_id = %s and a.is_team_area = 1 group by l.area order by n desc limit 1""", self.name)
			if rows:
				self.team_area = rows[0][0]
		if self.team_area:
			manager = frappe.db.get_value("Area", self.team_area, "field_manager")
			if manager:
				self.area_manager = manager
				self.area_manager_no = frappe.db.get_value("Field Staff", manager, "contact_no")

	def on_update(self):
		"""Keep every work order of this GIS in step when its area / people change."""
		before = self.get_doc_before_save()
		if not before:
			return
		changed = {wo_f: self.get(gis_f) for gis_f, wo_f in SHARED_FIELDS.items() if self.get(gis_f) != before.get(gis_f)}
		if changed:
			wo = frappe.qb.DocType("FTTH Work Order")
			q = frappe.qb.update(wo).where(wo.gis == self.name)
			for field, value in changed.items():
				# 2026-10-28: was wo.field(field), which returns a pseudo-column (TypeError on every save)
				q = q.set(getattr(wo, field), value)
			q.run()
