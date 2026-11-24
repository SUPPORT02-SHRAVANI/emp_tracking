# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from emp_tracking.ftth.logic import line_from_geojson, line_length_m, norm, split_route_name


class KMZRoute(Document):
	def validate(self):
		if self.route_name and not (self.a_end or self.b_end):
			self.a_end, self.b_end = split_route_name(self.route_name)
		coords = line_from_geojson(self.location)
		if len(coords) >= 2:
			self.length_m = round(line_length_m(coords), 1)
		if not self.dedupe_key:
			self.dedupe_key = f"{norm(self.route_name)}|{round(self.length_m or 0)}|{self.name or ''}"[:255]
