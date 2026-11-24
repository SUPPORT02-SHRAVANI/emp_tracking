# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt
"""Connect work orders to the link register and to KMZ pins by name / GIS / distance.

Pure python (no frappe) so the same rules run in the importer (bulk, in memory)
and in the work-order form (via small DB lookups that build a Matcher on the fly).
"""

from collections import defaultdict

from emp_tracking.ftth.logic import haversine_m, norm

MAX_PIN_DISTANCE_M = 1000  # a pin further than this from the site's own coordinates is not the same place


class Matcher:
	def __init__(self):
		self._links = defaultdict(set)  # norm(name) -> {link_id}
		self._link_gis = defaultdict(set)  # link_id -> {gis}
		self._points = defaultdict(list)  # norm(name) -> [(id, lat, lon, gis)]

	# ------------------------------------------------------------ loading
	def add_link(self, link_id, names, gis_codes=()):
		for n in names:
			k = norm(n)
			if len(k) >= 4:  # ignore tiny names like "A1"
				self._links[k].add(link_id)
		for g in gis_codes:
			if g:
				self._link_gis[link_id].add(str(g).upper())

	def add_point(self, point_id, name, lat, lon, gis=None):
		k = norm(name)
		if len(k) >= 4 and lat and lon:
			self._points[k].append((point_id, float(lat), float(lon), (gis or "").upper() or None))

	# ------------------------------------------------------------ matching
	def match_link(self, name, gis=None):
		"""Return the single link whose A/B end or HOTO section name equals `name` (same GIS preferred)."""
		cands = self._links.get(norm(name), set())
		if len(cands) > 1 and gis:
			same = {c for c in cands if str(gis).upper() in self._link_gis.get(c, set())}
			unknown = {c for c in cands if not self._link_gis.get(c)}
			cands = same or (unknown if len(unknown) == 1 else cands)
		return next(iter(cands)) if len(cands) == 1 else None

	def match_point(self, name, gis=None, near=None):
		"""Return (point_id, lat, lon) for a pin named `name`.
		near=(lat, lon): take the closest pin, rejecting pins more than MAX_PIN_DISTANCE_M away."""
		cands = self._points.get(norm(name), [])
		if not cands:
			return None
		if near and near[0] and near[1]:
			best = min(cands, key=lambda c: haversine_m(near[1], near[0], c[2], c[1]))
			if haversine_m(near[1], near[0], best[2], best[1]) > MAX_PIN_DISTANCE_M:
				return None
			return best[:3]
		if gis:
			same = [c for c in cands if c[3] == str(gis).upper()]
			if len(same) == 1:
				return same[0][:3]
			if same:
				cands = same
		# several pins with the same name and nothing to choose by: only accept if they are all one spot
		first = cands[0]
		if all(haversine_m(first[2], first[1], c[2], c[1]) < 50 for c in cands):
			return first[:3]
		return None
