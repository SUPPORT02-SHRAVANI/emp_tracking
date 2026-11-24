# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt

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
