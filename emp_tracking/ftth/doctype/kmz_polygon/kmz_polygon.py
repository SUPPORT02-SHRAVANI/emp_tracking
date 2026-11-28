# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# KMZ Polygon: one shape (Polygon placemark) from an uploaded KMZ, e.g. an "Area Remarks" or DSA /
# cluster boundary, or an EVision team area. KMZ Upload creates these next to its KMZ Routes and
# KMZ Points, and the KMZ Map page draws them as shaded shapes in the "Map contents" tree.
# The boundary is the outer ring as JSON [[lat, lon], ...]; holes are not kept.
#
# Change log
#   2026-11-27  Created (user's report: the KMZ's polygons never reached the map).
# ---------------------------------------------------------------------------------------------

import json
import math

from frappe.model.document import Document

EARTH_R = 6371008.8  # mean earth radius in metres


def ring_area_sq_m(ring):
	"""Area of a [[lat, lon], ...] ring in square metres: the shoelace formula on a local flat
	projection, close enough for shapes of a few kilometres."""
	if len(ring) < 3:
		return 0.0
	lat0 = math.radians(sum(p[0] for p in ring) / len(ring))
	xy = [(math.radians(lon) * EARTH_R * math.cos(lat0), math.radians(lat) * EARTH_R) for lat, lon in ring]
	s = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1]))
	return abs(s) / 2


# 2026-11-28: point_in_ring moved to Area (the NOC flow uses it without the KMZ code); kept as a name here
from emp_tracking.emp_tracking.doctype.area.area import point_in_ring  # noqa: E402,F401


class KMZPolygon(Document):
	# Date: 2026-11-27
	def validate(self):
		try:
			ring = json.loads(self.boundary or "[]")
		except ValueError:
			ring = []
		self.area_sq_m = round(ring_area_sq_m(ring), 1)
		if self.fill_opacity is not None:
			self.fill_opacity = min(max(self.fill_opacity, 0), 1)
