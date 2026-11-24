# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt
#
# FTTH Work Order controller: cleans the WO number, connects the Link Register and KMZ data,
# and fills the automatic fields (status, stage, warnings, route map) from logic.py.
# Stage notifications to the next person are sent by emp_tracking (hooks.py doc_events).
#
# Change log
#   2026-10-29  set_area_manager_user(): Area Manager (Login) filled from the Area Manager name.
#   2026-10-29  set_billing_values(): Billing tab filled from the Link Register's HOTO rows (only
#               empty fields), and Final Amount = Base + GST.

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

from emp_tracking.ftth.linking import Matcher
from emp_tracking.ftth.logic import (
	derive,
	final_amount,
	haversine_m,
	hoto_values,
	line_from_geojson,
	parse_lat_long,
	parse_wo_number,
	route_map_geojson,
)

MAX_KMZ_MATCH_DISTANCE_M = 500


class FTTHWorkOrder(Document):
	# ------------------------------------------------------------ validation
	def validate(self):
		self.wo_number = " ".join((self.wo_number or "").split()) or None
		self.unique_id = (self.unique_id or "").strip().upper() or None
		if not self.wo_received_date:
			self.wo_received_date = parse_wo_number(self.wo_number).get("wo_date") or getdate()
		self.connect_link_register()
		self.connect_kmz_pins()
		self.match_kmz_route()
		self.apply_derived_values()
		self.check_duplicate_wo()
		self.validate_people()
		self.set_area_manager_user()
		self.set_billing_values()

	# Date: 2026-10-29
	def set_billing_values(self):
		"""Billing tab: HOTO details from the linked Link Register (fills only what is empty, so a
		value typed by Accounts is never overwritten), and Final Amount = Base + GST."""
		if self.ftth_link:
			rows = frappe.get_all("FTTH Link HOTO", filters={"parent": self.ftth_link, "parenttype": "FTTH Link"},
								  fields=["hoto_no", "hoto_date", "year", "section_name"])
			for field, value in hoto_values(rows).items():
				if not self.get(field):
					self.set(field, value)
		self.final_amount = final_amount(self.base_amount, self.gst_amount)

	# Date: 2026-10-29
	def set_area_manager_user(self):
		"""Area Manager (Login) from the Area Manager name, when exactly one enabled user has that
		full name. Left alone when already chosen by hand."""
		if self.area_manager_user or not self.area_manager:
			return
		users = frappe.get_all("User", filters={"full_name": self.area_manager.strip(), "enabled": 1}, pluck="name")
		if len(users) == 1:
			self.area_manager_user = users[0]

	def check_duplicate_wo(self):
		if not self.wo_id:
			return
		other = frappe.db.get_value("FTTH Work Order", {"wo_id": self.wo_id, "name": ["!=", self.name]})
		if other:
			frappe.throw(
				_("WO {0} is already saved as {1}.").format(
					frappe.bold(self.wo_id), f'<a href="/app/ftth-work-order/{other}">{other}</a>'
				),
				frappe.UniqueValidationError,
				title=_("Duplicate work order"),
			)

	# ------------------------------------------------------------ connections
	def connect_link_register(self):
		"""Link ID typed -> link it. Otherwise find the link whose A/B end or HOTO section is this building."""
		if self.evisions_link_id and frappe.db.exists("FTTH Link", self.evisions_link_id):
			self.ftth_link = self.evisions_link_id
			return
		if self.ftth_link:
			self.evisions_link_id = self.evisions_link_id or self.ftth_link
			return
		if self.evisions_link_id or not self.end_location:
			return
		name = self.end_location.strip()
		m = Matcher()
		for field in ("a_end", "b_end"):
			for l in frappe.get_all("FTTH Link", filters={field: name}, fields=["name", "a_end", "b_end", "gis"], limit=20):
				m.add_link(l.name, (l.a_end, l.b_end), (l.gis,))
		for h in frappe.get_all("FTTH Link HOTO", filters={"section_name": name}, fields=["parent", "section_name", "gis"],
								limit=20):
			m.add_link(h.parent, (h.section_name,), (h.gis,))
		found = m.match_link(name, self.gis)
		if found:
			self.ftth_link = self.evisions_link_id = found

	def connect_kmz_pins(self):
		"""Find the KMZ pins for the A end and B end; use their coordinates when none were typed."""
		for name, ll_field, point_field in ((self.end_location, "end_lat_long", "end_point"),
											(self.new_b_end or self.b_end, "b_end_lat_long", "b_end_point")):
			if not name or self.get(point_field):
				continue
			m = Matcher()
			for p in frappe.get_all("KMZ Point", filters={"point_name": name.strip()},
									fields=["name", "point_name", "latitude", "longitude", "gis"], limit=50):
				m.add_point(p.name, p.point_name, p.latitude, p.longitude, p.gis)
			near = parse_lat_long(self.get(ll_field))
			pin = m.match_point(name, self.gis, near if near[0] else None)
			if pin:
				self.set(point_field, pin[0])
				if not near[0]:
					self.set(ll_field, f"{pin[1]:.7f}, {pin[2]:.7f}")

	def match_kmz_route(self):
		"""Link the KMZ route named '<End Location> to …'. When several share the name, take the one
		whose end is closest to the site's coordinates (and reject routes more than 500 m away)."""
		settings = frappe.get_cached_doc("FTTH Settings")
		if self.kmz_route or not cint(settings.auto_match_kmz) or not self.end_location:
			return
		pattern = f"{self.end_location.strip()} to %"
		candidates = frappe.get_all(
			"KMZ Route", filters={"route_name": ["like", pattern]}, fields=["name", "length_m", "gis", "location"],
			limit=50,
		)
		if not candidates:
			return
		lat, lon = parse_lat_long(self.end_lat_long)
		best, best_dist = None, None
		for c in candidates:
			coords = line_from_geojson(c.location)
			if lat and coords:
				dist = min(haversine_m(lon, lat, *coords[0]), haversine_m(lon, lat, *coords[-1]))
			else:
				dist = 0 if c.gis and c.gis == self.gis else 1
			if best_dist is None or dist < best_dist:
				best, best_dist = c, dist
		if lat and best_dist is not None and best_dist > MAX_KMZ_MATCH_DISTANCE_M:
			return
		self.kmz_route = best.name
		self.kmz_route_length = best.length_m

	def apply_derived_values(self):
		settings = frappe.get_cached_doc("FTTH Settings")
		values = self.as_dict()
		for key in ("rfs_date", "wo_received_date", "work_completed_date"):
			values[key] = getdate(values[key]) if values.get(key) else None
		if self.kmz_route and not self.kmz_route_length:
			self.kmz_route_length = frappe.db.get_value("KMZ Route", self.kmz_route, "length_m")
			values["kmz_route_length"] = self.kmz_route_length
		derived = derive(values, flt(settings.survey_diff_pct) or 50, flt(settings.kmz_diff_pct) or 30)
		for field, value in derived.items():
			if self.meta.has_field(field):
				self.set(field, value)
		route_coords = None
		if self.kmz_route:
			route_coords = line_from_geojson(frappe.db.get_value("KMZ Route", self.kmz_route, "location"))
		self.route_map = route_map_geojson(self.as_dict(), route_coords, self.kmz_route)

	def validate_people(self):
		for field, expected in (("splicer", "Splicer"), ("assistant_splicer", "Assistant Splicer"),
								("rider_1", "Rider"), ("rider_2", "Rider")):
			name = self.get(field)
			if name and self.flags.get("from_ftth_import") is not True:
				kind = frappe.db.get_value("Field Staff", name, "staff_type")
				if kind and kind != expected:
					frappe.msgprint(
						_("{0} is registered as {1}, not {2}.").format(frappe.bold(name), kind, expected),
						indicator="orange", alert=True,
					)

	# ------------------------------------------------------------ after save
	def on_update(self):
		self.mark_node_site()

	def mark_node_site(self):
		if not self.end_location:
			return
		sites = frappe.get_all(
			"Node Site",
			filters={"site_name": ["like", f"{self.end_location.strip()}%"], "has_work_order": 0},
			pluck="name",
		)
		for site in sites:
			frappe.db.set_value("Node Site", site, {"has_work_order": 1, "work_order": self.name},
								update_modified=False)


@frappe.whitelist()
def preview_wo_number(wo_number):
	"""Used by the form to show WO ID / date / segment while typing."""
	info = parse_wo_number(wo_number)
	info["existing"] = frappe.db.get_value("FTTH Work Order", {"wo_id": info["wo_id"]}) if info["wo_id"] else None
	return info
