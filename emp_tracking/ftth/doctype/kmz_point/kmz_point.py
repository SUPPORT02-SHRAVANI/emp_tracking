# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from emp_tracking.ftth.logic import norm


class KMZPoint(Document):
	def validate(self):
		if not self.dedupe_key:
			self.dedupe_key = f"{norm(self.point_name)}|{self.latitude or 0:.5f}|{self.longitude or 0:.5f}"[:255]
