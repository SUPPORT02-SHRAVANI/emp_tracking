# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class FTTHLink(Document):
	def validate(self):
		self.link_id = (self.link_id or "").strip()
		self.is_billed = 1 if self.hotos else 0
		if not self.gis:
			self.gis = next((h.gis for h in self.hotos if h.gis), None)
