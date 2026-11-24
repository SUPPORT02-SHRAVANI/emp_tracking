# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from emp_tracking.ftth.logic import norm


class NodeSite(Document):
	def validate(self):
		if not self.dedupe_key:
			self.dedupe_key = f"{norm(self.site_name)}|{norm(self.gis)}"[:255]
		if not self.work_order and self.site_name:
			wo = frappe.db.get_value("FTTH Work Order", {"end_location": ["like", f"{self.site_name.strip()}%"]})
			self.work_order = wo
		self.has_work_order = 1 if self.work_order else 0
