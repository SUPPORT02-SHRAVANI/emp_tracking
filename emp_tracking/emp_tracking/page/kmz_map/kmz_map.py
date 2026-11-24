# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# KMZ Map dashboard (Desk page /app/kmz-map): data
#
# How this file works
#   The page draws FTTH Tracker's KMZ Routes (lines) and KMZ Points (pins) on a map. Rows come
#   from KMZ Upload or FTTH Import; each one carries its GIS Node (gis), the KMZ file it came
#   from (source_file) and its folder chain inside the KMZ (custom_kmz_path, set by KMZ Upload).
#   get_filter_options: the choices for the page's filters (only values that have KMZ rows).
#   get_map_data: the routes / points for the chosen filters, their totals and a per-node count.
#   get_item: one route / pin's details, for the popup.
#   add_route: saves one route drawn on the page as a KMZ Route.
#   fault_overlay: open complaints for the map (same rules as the Network Topology page): the
#     site with an open complaint is down (red), the sites fed through it are affected (orange),
#     and the node carrying them gets a fault count.
# Reads go through frappe.get_list, so a user only sees KMZ rows their permissions allow.
#
# Change log
#   2026-10-26  Created.
#   2026-10-27  Map rows sent as short arrays; popup details loaded on click (get_item).
#   2026-10-27  Open complaints on the map (fault_overlay): down sites red, affected orange;
#               route / pin rows now also carry their Site (custom_site).
#   2026-10-27  get_filter_options also returns node_area, for the linked Node / Area filters.
#   2026-10-27  get_filter_options also returns the KMZ Map Settings colours / pin types.
#   2026-10-27  add_route: saves one route drawn on the map (Add Route button), no KMZ file needed.
#   2026-10-27  preview_nearest / apply_nearest / undo_nearest: rows with no GIS Node get the node of
#               the closest matched row within a chosen distance (Assign Nodes button).
# ---------------------------------------------------------------------------------------------

import json
import math

import frappe
from frappe.utils import cint, flt

from emp_tracking.emp_tracking.doctype.kmz_map_settings.kmz_map_settings import get_map_settings
from emp_tracking.emp_tracking.page.network_topology.network_topology import CLOSED_STATES, site_parents

ROUTE_LIMIT = 4000  # lines drawn at once; the page says when a filter hits it
POINT_LIMIT = 8000  # pins drawn at once
NOT_MATCHED = "Not Matched"
DRAWN_SOURCE = "Drawn on KMZ Map"  # source_file / KMZ Path of routes made with add_route
DRAWN_BY = "Drawn on Map"  # their Matched By (an option of custom_kmz_matched_by, setup.py)


# Date: 2026-10-26
@frappe.whitelist()
def get_filter_options():
	def distinct(doctype, field):
		return {r[field] for r in frappe.get_list(doctype, fields=[field], filters={field: ["is", "set"]}, group_by=field,
			limit_page_length=0)}

	nodes = distinct("KMZ Route", "gis") | distinct("KMZ Point", "gis")
	files = distinct("KMZ Route", "source_file") | distinct("KMZ Point", "source_file")
	# 2026-10-27: node -> area, so the page limits Area to the chosen node's area (and nodes to the chosen area)
	node_area = {r.name: r.area for r in frappe.get_all("GIS Node", filters={"name": ["in", list(nodes)]},
		fields=["name", "area"]) if r.area} if nodes else {}
	return {"nodes": sorted(nodes), "files": sorted(files), "areas": sorted(set(node_area.values())), "node_area": node_area,
		"settings": get_map_settings()}  # 2026-10-27: pin types and colours (KMZ Map Settings)


def build_filters(gis=None, area=None, source_file=None, path=None, matched_by=None, site=None):
	filters = []
	if gis:
		filters.append(["gis", "=", gis])
	if area:
		filters.append(["gis", "in", frappe.get_all("GIS Node", filters={"area": area}, pluck="name") or [""]])
	if source_file:
		filters.append(["source_file", "=", source_file])
	if path:
		# the folder chain, so "C1U" or "Icon Residency" finds everything under that folder
		filters.append(["custom_kmz_path", "like", f"%{path}%"])
	if matched_by == NOT_MATCHED:
		filters.append(["gis", "is", "not set"])
	elif matched_by:
		filters.append(["custom_kmz_matched_by", "=", matched_by])
	if site:
		filters.append(["custom_site", "=", site])
	return filters


def route_coords(location):
	"""[[lat, lon], ...] of the route's first LineString (location is GeoJSON, lon / lat order)."""
	try:
		data = json.loads(location) if isinstance(location, str) else location
	except (TypeError, ValueError):
		return []
	for feature in (data or {}).get("features") or []:
		geometry = feature.get("geometry") or {}
		if geometry.get("type") == "LineString":
			return [[round(c[1], 6), round(c[0], 6)] for c in geometry.get("coordinates") or [] if len(c) >= 2]
	return []


# Date: 2026-10-26
@frappe.whitelist()
def get_map_data(gis=None, area=None, source_file=None, path=None, matched_by=None, site=None, show="Routes and Pins"):
	filters = build_filters(gis, area, source_file, path, matched_by, site)
	out = {"routes": [], "points": [], "limit_hit": False}

	# 2026-10-27: only what the map needs, as short arrays (all rows of all 8 KMZ parts were
	# ~5.5 MB as full records); the popup loads the rest of a row on click (get_item)
	if show != "Pins Only":
		rows = frappe.get_list("KMZ Route", filters=filters, fields=["name", "gis", "route_name", "location", "custom_site"],
			limit_page_length=ROUTE_LIMIT + 1, order_by="gis asc", as_list=True)
		out["limit_hit"] |= len(rows) > ROUTE_LIMIT
		for name, node, title, location, site in rows[:ROUTE_LIMIT]:
			coords = route_coords(location)
			if coords:
				out["routes"].append([name, node or "", title, coords, site or ""])
	if show != "Routes Only":
		rows = frappe.get_list("KMZ Point", filters=filters, fields=["name", "gis", "point_name", "latitude", "longitude",
			"custom_site"], limit_page_length=POINT_LIMIT + 1, order_by="gis asc", as_list=True)
		out["limit_hit"] |= len(rows) > POINT_LIMIT
		out["points"] = [[name, node or "", title, round(flt(lat), 6), round(flt(lon), 6), site or ""]
			for name, node, title, lat, lon, site in rows[:POINT_LIMIT] if lat and lon]

	# totals and the per-node list are counted in the database, not from the capped rows
	def per_node(doctype):
		return {r.gis or "": cint(r.n) for r in frappe.get_list(doctype, filters=filters,
			fields=["gis", {"COUNT": "*", "as": "n"}], group_by="gis", limit_page_length=0)}

	routes, points = per_node("KMZ Route"), per_node("KMZ Point")
	length = frappe.get_list("KMZ Route", filters=filters, fields=[{"SUM": "length_m", "as": "m"}], limit_page_length=0)
	nodes = sorted(set(routes) | set(points), key=lambda g: (-(routes.get(g, 0) + points.get(g, 0)), g))
	out["summary"] = {
		"routes": sum(routes.values()), "points": sum(points.values()),
		"length_km": round(flt(length[0].m if length else 0) / 1000, 2),
		"nodes": len([g for g in nodes if g]), "not_matched": routes.get("", 0) + points.get("", 0),
	}
	out["by_node"] = [{"gis": g, "routes": routes.get(g, 0), "points": points.get(g, 0)} for g in nodes]
	out["faults"] = fault_overlay()
	return out


# Date: 2026-10-27
def fault_overlay():
	"""Open complaints for the map, worked out like the Network Topology page's live view.

	down_sites: sites with an open complaint; affected_sites: every site fed through one of them
	(Site ETIPL code tree, site_parents); nodes: {GIS Node: open complaints}; markers: one per
	complaint, at its own latitude / longitude, else at a KMZ pin of its site (else the page
	puts it on the node's pin). Complaints the user may not read are left out (get_list).
	"""
	empty = {"down_sites": [], "affected_sites": [], "nodes": {}, "markers": []}
	if not frappe.db.exists("DocType", "Complaint Information"):
		return empty
	faults = frappe.get_list("Complaint Information", filters=[["workflow_state", "not in", CLOSED_STATES],
		["docstatus", "<", 2]], fields=["name", "site", "node_id", "workflow_state", "society_name", "latitude",
		"longitude"], order_by="complaint_date_and_time desc", limit_page_length=500)
	site_node = {r.name: r.node for r in frappe.get_all("Site", filters={"name": ["in", [f.site for f in faults if f.site]]},
		fields=["name", "node"])} if any(f.site for f in faults) else {}

	nodes, down = {}, set()
	for f in faults:
		node = f.node_id or site_node.get(f.site)
		if node:
			nodes[node] = nodes.get(node, 0) + 1
		if f.site:
			down.add(f.site)

	# affected: walk each faulty node's site tree below the down sites
	affected = set()
	for node in {site_node[s] for s in down if site_node.get(s)}:
		sites = frappe.get_all("Site", filters={"node": node}, fields=["name", "site_name", "etipl_code", "b_location"])
		children = {}
		for child, parent in site_parents(sites, node).items():
			children.setdefault(parent, []).append(child)
		stack = [s for s in down if site_node.get(s) == node]
		while stack:
			for child in children.get(stack.pop(), []):
				if child not in affected and child not in down:
					affected.add(child)
					stack.append(child)

	# a complaint without coordinates is placed on a KMZ pin of its site when there is one
	no_geo = [f.site for f in faults if f.site and not (flt(f.latitude) and flt(f.longitude))]
	site_pin = {}
	for r in frappe.get_list("KMZ Point", filters={"custom_site": ["in", no_geo]}, fields=["custom_site", "latitude",
			"longitude"], limit_page_length=0) if no_geo else []:
		site_pin.setdefault(r.custom_site, (flt(r.latitude), flt(r.longitude)))
	markers = []
	for f in faults:
		lat, lon = (flt(f.latitude), flt(f.longitude)) if flt(f.latitude) and flt(f.longitude) else site_pin.get(f.site, (0, 0))
		markers.append([f.name, round(lat, 6), round(lon, 6), f.society_name or f.site or "", f.workflow_state,
			f.node_id or site_node.get(f.site) or "", f.site or ""])
	return {"down_sites": sorted(down), "affected_sites": sorted(affected), "nodes": nodes, "markers": markers}


# Date: 2026-10-27
@frappe.whitelist()
def get_item(doctype, name):
	"""One route / pin for the map popup: node, site, KMZ file and full KMZ path."""
	if doctype not in ("KMZ Route", "KMZ Point"):
		frappe.throw(frappe._("Not a KMZ doctype"))
	frappe.has_permission(doctype, "read", name, throw=True)
	fields = ["name", "gis", "source_file", "node_folder", "custom_kmz_path", "custom_site", "custom_kmz_matched_by"]
	fields += ["route_name", "length_m", "a_end", "b_end"] if doctype == "KMZ Route" else ["point_name", "latitude", "longitude"]
	return frappe.db.get_value(doctype, name, fields, as_dict=True)


# Date: 2026-10-27
@frappe.whitelist(methods=["POST"])
def add_route(route_name, coords, gis=None, site=None):
	"""One KMZ Route drawn on the map (Add Route button), so a single new route needs no KMZ file.
	coords: [[lat, lon], ...] as clicked. Saved like an uploaded route (same dedupe key as KMZ
	Upload, so uploading the same line later does not duplicate it), with source_file
	DRAWN_SOURCE and Matched By "Drawn on Map". insert() checks the user may create KMZ Routes."""
	from ftth_tracker.logic import feature_collection, line_feature, line_length_m, split_route_name

	from emp_tracking.emp_tracking.doctype.kmz_upload.kmz_upload import row_key

	route_name = (route_name or "").strip()[:255]
	if not route_name:
		frappe.throw(frappe._("Enter a route name."))
	points = json.loads(coords) if isinstance(coords, str) else coords
	# GeoJSON / KMZ order is lon, lat
	line = [(round(flt(lon), 7), round(flt(lat), 7)) for lat, lon in points or []]
	if len(line) < 2:
		frappe.throw(frappe._("Click at least two points on the map."))
	if gis and not frappe.db.exists("GIS Node", gis):
		frappe.throw(frappe._("GIS Node {0} not found").format(gis))
	if site and not frappe.db.exists("Site", site):
		frappe.throw(frappe._("Site {0} not found").format(site))

	_, key = row_key({"kind": "route", "name": route_name, "coords": line})
	existing = frappe.db.get_value("KMZ Route", {"dedupe_key": key})
	if existing:
		frappe.throw(frappe._("This route is already saved: {0}").format(existing))
	a, b = split_route_name(route_name)
	doc = frappe.get_doc({
		"doctype": "KMZ Route", "route_name": route_name, "a_end": (a or "")[:255], "b_end": (b or "")[:255],
		"length_m": round(line_length_m(line), 1), "gis": gis or None, "node_folder": (gis or "")[:140],
		"location": feature_collection([line_feature(line, route_name)]), "source_file": DRAWN_SOURCE,
		"dedupe_key": key, "custom_site": site or None, "custom_kmz_matched_by": DRAWN_BY,
		"custom_kmz_path": DRAWN_SOURCE,
	}).insert()
	return {"name": doc.name, "length_m": doc.length_m}


# ---------------------------------------------------------------- nearest node (Assign Nodes button)
# 2026-10-27: most KMZ rows have no GIS Node (their KMZ folder is not a GIS code and their
# building is not a Site). nearest_node_plan gives each one the node of the closest row that
# *was* matched by Node Name or Building Name (pins, and the vertices of routes), within max_m.
# A row whose second-closest other node is about as close is "unsure" and only assigned when
# asked. Assigned rows get Matched By NEAREST_BY, so they can be listed and undone.
NEAREST_BY = "Nearest Node"
TRUSTED_BY = ("Node Name", "Building Name")
SNAP_M = 25  # reference points of one node closer than this are merged
PREVIEW_ROWS = 300


def _xy(lat, lon):
	"""Metres on a flat plane around Pune: close enough for distances of a few km."""
	return lon * 111320 * math.cos(math.radians(18.5)), lat * 110540


def _route_vertices(location, step=1):
	coords = route_coords(location)  # [[lat, lon], ...]
	return coords[::step] + coords[-1:] if coords else []


def nearest_node_plan(max_m, include_pins=True):
	max_m = max(10, min(cint(max_m), 1000))  # 1 km takes ~30 s on all rows
	# reference points of every trusted row, merged to one per node per SNAP_M square (dense
	# areas have thousands of pins a few metres apart), in a grid of max_m squares, so a point
	# only looks at the 9 squares around it
	refs, seen = {}, set()
	def add_ref(lat, lon, node):
		x, y = _xy(flt(lat), flt(lon))
		key = (int(x // SNAP_M), int(y // SNAP_M), node)
		if key in seen:
			return
		seen.add(key)
		refs.setdefault((int(x // max_m), int(y // max_m)), []).append((x, y, node))
	for r in frappe.get_all("KMZ Point", filters={"gis": ["is", "set"], "custom_kmz_matched_by": ["in", TRUSTED_BY]},
			fields=["gis", "latitude", "longitude"]):
		if r.latitude and r.longitude:
			add_ref(r.latitude, r.longitude, r.gis)
	for r in frappe.get_all("KMZ Route", filters={"gis": ["is", "set"], "custom_kmz_matched_by": ["in", TRUSTED_BY]},
			fields=["gis", "location"]):
		for lat, lon in _route_vertices(r.location):
			add_ref(lat, lon, r.gis)

	def best_nodes(points):
		"""{node: closest distance} for the given [[lat, lon], ...], only nodes within max_m."""
		found = {}
		for lat, lon in points:
			x, y = _xy(lat, lon)
			ci, cj = int(x // max_m), int(y // max_m)
			for i in (ci - 1, ci, ci + 1):
				for j in (cj - 1, cj, cj + 1):
					for rx, ry, node in refs.get((i, j), ()):
						d = math.hypot(rx - x, ry - y)
						if d <= max_m and d < found.get(node, max_m + 1):
							found[node] = d
		return found

	rows = []
	todo = [("KMZ Route", r.name, r.route_name, _route_vertices(r.location, 3)) for r in frappe.get_all("KMZ Route", filters={"gis": ["is", "not set"]}, fields=["name", "route_name", "location"])]
	if include_pins:
		todo += [("KMZ Point", r.name, r.point_name, [[flt(r.latitude), flt(r.longitude)]])
			for r in frappe.get_all("KMZ Point", filters={"gis": ["is", "not set"]}, fields=["name", "point_name", "latitude", "longitude"])
			if r.latitude and r.longitude]
	for doctype, name, title, points in todo:
		found = sorted(best_nodes(points).items(), key=lambda kv: kv[1])
		if not found:
			continue
		node, d = found[0]
		second = found[1] if len(found) > 1 else None
		# another node almost as close: the line may belong to either, so a person should look
		unsure = bool(second and second[1] <= d * 1.5 + 30)
		rows.append({"doctype": doctype, "name": name, "title": title, "gis": node, "m": round(d),
			"other": second[0] if second else "", "other_m": round(second[1]) if second else None, "unsure": unsure})
	return rows, len(todo)


# Date: 2026-10-27
@frappe.whitelist()
def preview_nearest(max_m=200, include_pins=1):
	"""What Assign Nodes would do: totals, per-node counts and the first rows (unsure first)."""
	frappe.has_permission("KMZ Route", "write", throw=True)
	rows, total = nearest_node_plan(max_m, cint(include_pins))
	by_node = {}
	for r in rows:
		by_node[r["gis"]] = by_node.get(r["gis"], 0) + 1
	sure = [r for r in rows if not r["unsure"]]
	return {
		"without_node": total, "found": len(rows), "sure": len(sure), "unsure": len(rows) - len(sure),
		"routes": len([r for r in rows if r["doctype"] == "KMZ Route"]),
		"by_node": sorted(by_node.items(), key=lambda kv: -kv[1]),
		"rows": sorted(rows, key=lambda r: (not r["unsure"], -r["m"]))[:PREVIEW_ROWS],
		"already": frappe.db.count("KMZ Route", {"custom_kmz_matched_by": NEAREST_BY})
			+ frappe.db.count("KMZ Point", {"custom_kmz_matched_by": NEAREST_BY}),
	}


# Date: 2026-10-27
@frappe.whitelist(methods=["POST"])
def apply_nearest(max_m=200, include_pins=1, include_unsure=0):
	"""Gives the rows of preview_nearest their node (worked out again here, not taken from the page)."""
	for dt in ("KMZ Route", "KMZ Point"):
		frappe.has_permission(dt, "write", throw=True)
	rows, _ = nearest_node_plan(max_m, cint(include_pins))
	groups = {}
	for r in rows:
		if cint(include_unsure) or not r["unsure"]:
			groups.setdefault((r["doctype"], r["gis"]), []).append(r["name"])
	done = 0
	for (doctype, node), names in groups.items():
		# one UPDATE per node; rows that got a node meanwhile are left alone
		frappe.db.set_value(doctype, {"name": ["in", names], "gis": ["is", "not set"]},
			{"gis": node, "custom_kmz_matched_by": NEAREST_BY}, update_modified=False)
		done += len(names)
	return {"assigned": done}


# Date: 2026-10-27
@frappe.whitelist(methods=["POST"])
def undo_nearest():
	"""Takes the node off every row Assign Nodes filled in."""
	out = {}
	for dt in ("KMZ Route", "KMZ Point"):
		frappe.has_permission(dt, "write", throw=True)
		out[dt] = frappe.db.count(dt, {"custom_kmz_matched_by": NEAREST_BY})
		frappe.db.set_value(dt, {"custom_kmz_matched_by": NEAREST_BY}, {"gis": None, "custom_kmz_matched_by": ""},
			update_modified=False)
	return out
