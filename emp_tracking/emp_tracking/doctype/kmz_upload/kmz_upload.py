# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# KMZ Upload: one place to upload a whole KMZ (e.g. "KMZ Till 16.09.2026 Part 8 of 8") and have
# its routes and pins filed under the right GIS Node.
#
# The team's KMZ has two kinds of folders:
#   * node folders named with the GIS code ("B1V", "C1U"), holding the node pin ("B1V") and its
#     joints / poles ("B1V05");
#   * building folders ("Deepa Apartment to ODF KASTURBA HOUSING SOCIETY") holding one route and
#     the building / ODF pins, often at the top level with no node folder above them.
# So each placemark gets its node, first match wins:
#   1. Node name  - the pin is named with a GIS code (B1V, B1V05), or the nearest folder above
#                   it is (a nested "1MG" folder inside "C1U" belongs to 1MG);
#   2. Building   - the pin name, or either end of a route "A to B", equals the name of a Site
#                   (emp_tracking) or a Node Site (FTTH Tracker), or its B Location, once words
#                   like "ODF", "Encloser", "B end" are dropped; a name that starts with the
#                   other (8+ letters) also counts. A name found under two nodes is not used;
#   3. Same folder - the rest of a building folder takes the node its matched pins got.
# Placemarks that match nothing are still imported, without a node, and listed on the form.
#
# The records are FTTH Tracker's own KMZ Route / KMZ Point, with the same dedupe keys as its
# FTTH Import, so loading a file through both never makes duplicates; a row that is already
# there only gets its node filled in when it had none. Polygons are skipped (FTTH Tracker has
# no polygon doctype). Custom Fields custom_site / custom_kmz_matched_by / custom_kmz_upload on
# both doctypes (setup.py) record how each row was matched.
#
# Change log
#   2026-10-26  Created.
#   2026-10-26  Saves the full folder chain (custom_kmz_path) on each row, for the KMZ Map page.
#   2026-10-27  Dedupe key moved into row_key(), shared with patches/backfill_kmz_path.py.
# ---------------------------------------------------------------------------------------------

import re
import xml.etree.ElementTree as ET
import zipfile

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

# words that describe the fiber end, not the building ("ODF KASTURBA HOUSING SOCIETY",
# "SHRIYANSH RESIDENCY JC" = joint closure)
END_WORDS = re.compile(r"(?i)\b(odf|encloser|enclosure|jc|node|[ab]\s*end)\b")
MIN_PREFIX = 8  # shortest building name used for a "starts with" match


class KMZUpload(Document):
	# Date: 2026-10-26
	def validate(self):
		if self.kmz_file and not self.kmz_file.lower().endswith((".kmz", ".kml")):
			frappe.throw(_("Please attach a .kmz or .kml file."))


# Date: 2026-10-26
@frappe.whitelist(methods=["POST"])
def start_import(name):
	"""Queues the matching / import (a KMZ part has ~4,000 placemarks)."""
	doc = frappe.get_doc("KMZ Upload", name)
	doc.check_permission("write")
	if doc.status in ("Queued", "Running"):
		frappe.throw(_("This KMZ is already being imported."))
	doc.db_set({"status": "Queued", "log": ""})
	frappe.enqueue("emp_tracking.emp_tracking.doctype.kmz_upload.kmz_upload.run_import", queue="long",
		timeout=3600, name=name, enqueue_after_commit=True)
	return "Queued"


# Date: 2026-10-26
def run_import(name):
	doc = frappe.get_doc("KMZ Upload", name)
	doc.db_set({"status": "Running", "started_at": now_datetime(), "finished_at": None})
	frappe.db.commit()
	try:
		counts, unmatched, log = KMZMatcher(doc).run()
		doc.db_set({**counts, "status": "Completed", "finished_at": now_datetime(),
			"unmatched_list": "\n".join(unmatched[:1000]), "log": "\n".join(log)})
	except Exception:
		frappe.db.rollback()
		doc.db_set({"status": "Failed", "finished_at": now_datetime(), "log": frappe.get_traceback()})
		frappe.log_error(title=f"KMZ Upload {name} failed")
	frappe.db.commit()
	frappe.publish_realtime("kmz_upload_done", {"name": name}, doctype="KMZ Upload", docname=name)


# ---------------------------------------------------------------- reading


def read_placemarks(path):
	"""Every Point / LineString placemark: {kind, name, folders (outer -> inner), coords}."""
	if path.lower().endswith(".kml"):
		with open(path, "rb") as f:
			xml = f.read()
	else:
		with zipfile.ZipFile(path) as z:
			xml = z.read(next(n for n in z.namelist() if n.lower().endswith(".kml")))
	root = ET.fromstring(xml)
	tag = lambda e: e.tag.split("}")[-1]

	def child_text(e, t):
		c = next((c for c in e if tag(c) == t), None)
		return re.sub(r"\s+", " ", c.text).strip() if c is not None and c.text else ""

	def coords(geom):
		for c in geom.iter():
			if tag(c) == "coordinates" and c.text:
				pts = []
				for tok in c.text.split():
					p = tok.split(",")
					try:
						pts.append((float(p[0]), float(p[1])))
					except (ValueError, IndexError):
						pass
				return pts
		return []

	out, polygons = [], 0

	def walk(e, folders):
		nonlocal polygons
		for c in e:
			t = tag(c)
			if t == "Folder":
				walk(c, folders + [child_text(c, "name")])
			elif t == "Document":
				walk(c, folders)
			elif t == "Placemark":
				# the first geometry decides, as in FTTH Tracker's reader
				geom = next((g for g in c.iter() if tag(g) in ("Point", "LineString", "Polygon")), None)
				if geom is None:
					continue
				if tag(geom) == "Polygon":
					polygons += 1
					continue
				pts = coords(geom)
				kind = "route" if tag(geom) == "LineString" else "point"
				if (kind == "route" and len(pts) >= 2) or (kind == "point" and pts):
					out.append({"kind": kind, "name": (child_text(c, "name") or "(no name)")[:255],
						"folders": tuple(folders), "coords": pts})

	walk(root, [])
	return out, polygons


# Date: 2026-10-27
def row_key(pm):
	"""(doctype, dedupe_key) of a placemark: the same keys as FTTH Tracker's reader, so both
	importers share the rows. Also used by patches/backfill_kmz_path.py."""
	from ftth_tracker.logic import line_length_m, norm

	if pm["kind"] == "route":
		return "KMZ Route", f"{norm(pm['name'])}|{round(round(line_length_m(pm['coords']), 1))}"[:255]
	lon, lat = pm["coords"][0]
	return "KMZ Point", f"{norm(pm['name'])}|{lat:.5f}|{lon:.5f}"[:255]


# ---------------------------------------------------------------- matching


class KMZMatcher:
	def __init__(self, doc):
		from ftth_tracker.logic import norm

		self.doc, self.norm = doc, norm
		self.codes = {c.upper() for c in frappe.get_all("GIS Node", pluck="name")}
		self.buildings = self.building_index()

	def bkey(self, name):
		return self.norm(END_WORDS.sub(" ", name or ""))

	# Date: 2026-10-26
	def building_index(self):
		"""Building name -> (GIS node, Site or None). Names found under two nodes map to None."""
		index = {}

		def add(name, node, site=None):
			key = self.bkey(name)
			if len(key) < 4 or not node:
				return
			if key in index and index[key] and index[key][0] != node:
				index[key] = None  # ambiguous: same building name under two nodes
			elif key not in index or (index[key] and not index[key][1]):
				index[key] = (node, site)

		for s in frappe.get_all("Site", fields=["name", "site_name", "b_location", "node"], filters={"node": ["is", "set"]}):
			add(s.site_name, s.node, s.name)
			add(s.b_location, s.node)
		if frappe.db.exists("DocType", "Node Site"):
			for s in frappe.get_all("Node Site", fields=["site_name", "gis"], filters={"gis": ["is", "set"]}):
				add(s.site_name, s.gis)
		return index

	def node_code(self, text):
		"""'B1V' / 'B1V05' / 'C1U NOde To Aero East' -> the GIS code, if this site has it."""
		text = (text or "").strip().upper()
		m = re.fullmatch(r"([A-Z0-9]{3})\d{0,3}", text)
		if m and m.group(1) in self.codes:
			return m.group(1)
		first = text.split(" ", 1)[0]
		return first if first in self.codes else None

	def find_building(self, name):
		key = self.bkey(name)
		if len(key) < 4:
			return None
		if key in self.buildings:
			return self.buildings[key]
		if len(key) < MIN_PREFIX:
			return None
		# "Shree Siddhivinayak Lotus Meera A wing" vs Site "Shree Siddhivinayak Lotus Meera"
		hits = {v for k, v in self.buildings.items() if v and len(k) >= MIN_PREFIX and (key.startswith(k) or k.startswith(key))}
		return hits.pop() if len({h[0] for h in hits}) == 1 else None

	# Date: 2026-10-26
	def match(self, pm):
		"""Sets pm['gis'], pm['site'], pm['by']."""
		from ftth_tracker.logic import split_route_name

		pm.update({"gis": None, "site": None, "by": None})
		if pm["kind"] == "point":
			code = self.node_code(pm["name"])
			if code:
				pm.update({"gis": code, "by": "Node Name"})
				return
		for folder in reversed(pm["folders"]):
			code = self.node_code(folder)
			if code:
				pm.update({"gis": code, "by": "Node Name"})
				break
		names = split_route_name(pm["name"]) if pm["kind"] == "route" else (pm["name"],)
		if not pm["gis"] and pm["kind"] == "route":
			# "Delight Pride to R0C Node": a route that ends at the node itself
			code = next((self.node_code(n) for n in names if self.node_code(n)), None)
			if code:
				pm.update({"gis": code, "by": "Node Name"})
		for n in names:
			hit = self.find_building(n)
			if hit:
				if not pm["gis"]:
					pm.update({"gis": hit[0], "by": "Building Name"})
				# the Site is linked when it is in the same node as the one already found
				if hit[1] and hit[0] == pm["gis"]:
					pm["site"] = hit[1]
					break

	# Date: 2026-10-26
	def run(self):
		from ftth_tracker.logic import feature_collection, line_feature, line_length_m, split_route_name

		file_doc = frappe.get_doc("File", {"file_url": self.doc.kmz_file})
		label = (file_doc.file_name or self.doc.kmz_file.rsplit("/", 1)[-1])[:255]
		placemarks, polygons = read_placemarks(file_doc.get_full_path())
		for pm in placemarks:
			self.match(pm)

		# 3. same folder: a building folder's unmatched pins take the node its matched pins got
		by_folder = {}
		for pm in placemarks:
			if pm["folders"] and pm["by"] == "Building Name":
				by_folder.setdefault(pm["folders"], set()).add(pm["gis"])
		for pm in placemarks:
			nodes = by_folder.get(pm["folders"])
			if not pm["gis"] and nodes and len(nodes) == 1:
				pm.update({"gis": next(iter(nodes)), "by": "Same Folder"})

		counts = {"placemarks": len(placemarks) + polygons, "polygons_skipped": polygons, "routes_created": 0,
			"points_created": 0, "already_existed": 0, "matched_by_node": 0, "matched_by_building": 0,
			"matched_by_folder": 0, "unmatched": 0}
		have = {d: {r.dedupe_key: r for r in frappe.get_all(d, fields=["name", "dedupe_key", "gis", "custom_kmz_path"])}
			for d in ("KMZ Route", "KMZ Point")}
		seen, unmatched = set(), []
		for i, pm in enumerate(placemarks):
			doctype, key = row_key(pm)
			if doctype == "KMZ Route":
				length = round(line_length_m(pm["coords"]), 1)
			else:
				lon, lat = pm["coords"][0]
			if (doctype, key) in seen:
				continue
			seen.add((doctype, key))
			counts[{"Node Name": "matched_by_node", "Building Name": "matched_by_building",
				"Same Folder": "matched_by_folder"}.get(pm["by"], "unmatched")] += 1
			if not pm["gis"]:
				unmatched.append(" / ".join([*pm["folders"], pm["name"]]))
			path = " / ".join(pm["folders"])
			extra = {"custom_site": pm["site"], "custom_kmz_matched_by": pm["by"], "custom_kmz_upload": self.doc.name,
				"custom_kmz_path": path}
			old = have[doctype].get(key)
			if old:
				counts["already_existed"] += 1
				if not old.gis and pm["gis"]:
					frappe.db.set_value(doctype, old.name, {"gis": pm["gis"], **extra}, update_modified=False)
				elif not old.custom_kmz_path and path:
					# rows from FTTH Import (or before 2026-10-26) get their folder chain for the KMZ Map
					frappe.db.set_value(doctype, old.name, "custom_kmz_path", path, update_modified=False)
				continue
			values = {"doctype": doctype, "gis": pm["gis"], "source_file": label, "dedupe_key": key,
				"node_folder": (pm["folders"][-1] if pm["folders"] else "")[:140], **extra}
			if doctype == "KMZ Route":
				a, b = split_route_name(pm["name"])
				values.update({"route_name": pm["name"], "a_end": (a or "")[:255], "b_end": (b or "")[:255],
					"length_m": length, "location": feature_collection([line_feature(pm["coords"], pm["name"])])})
				counts["routes_created"] += 1
			else:
				values.update({"point_name": pm["name"], "latitude": round(lat, 7), "longitude": round(lon, 7)})
				counts["points_created"] += 1
			frappe.get_doc(values).insert(ignore_permissions=True)
			if i % 500 == 0:
				frappe.db.commit()

		nodes = {pm["gis"] for pm in placemarks if pm["gis"]}
		counts["nodes_found"] = len(nodes)
		counts["sites_linked"] = len({pm["site"] for pm in placemarks if pm["site"]})
		log = [f"File: {label}", f"GIS Nodes: {', '.join(sorted(nodes)) or 'none'}"]
		# folders named like a GIS code that this site has no GIS Node for: create the node, then
		# upload again, and their routes / pins are filed under it
		missing = sorted({f.strip().upper() for pm in placemarks if not pm["gis"] for f in pm["folders"]
			if re.fullmatch(r"(?=.*\d)[A-Z0-9]{3}", f.strip().upper()) and f.strip().upper() not in self.codes})
		if missing:
			log.append(f"Folders named like a GIS code with no GIS Node on this site: {', '.join(missing)}")
		return counts, unmatched, log
