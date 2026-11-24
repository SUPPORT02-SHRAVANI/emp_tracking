# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt
"""Background job that loads an FTTH Import file into the database.

Change log
  2026-10-29  billing_to_work_orders(): billing rows without a Link ID fill the Billing tab of the
              work order with the same building name (and GIS; RFS month breaks ties).
"""

import shutil
import tempfile
import traceback

import frappe
from frappe import _
from frappe.utils import now_datetime

from emp_tracking.ftth.importer.readers import STAFF_RANK, read_all
from emp_tracking.ftth.linking import Matcher
from emp_tracking.ftth.logic import feature_collection, hoto_values, line_feature, norm

PROGRESS_EVENT = "ftth_import_progress"
FILL, SKIP, UPDATE = "Fill empty fields only", "Skip", "Update with file values"


@frappe.whitelist()
def start_import(import_name):
	doc = frappe.get_doc("FTTH Import", import_name)
	doc.check_permission("write")
	if doc.status in ("Queued", "Running"):
		frappe.throw(_("This import is already {0}.").format(doc.status))
	doc.db_set({"status": "Queued", "log": None})
	frappe.enqueue(
		"emp_tracking.ftth.importer.run.run_import",
		queue="long",
		timeout=4 * 3600,
		import_name=import_name,
		enqueue_after_commit=True,
		job_id=f"ftth_import::{import_name}",
		deduplicate=True,
	)
	return "Queued"


def run_import(import_name):
	doc = frappe.get_doc("FTTH Import", import_name)
	doc.db_set({"status": "Running", "started_at": now_datetime()}, commit=True)
	workdir = tempfile.mkdtemp(prefix="ftth_import_")
	log = []
	try:
		file_doc = frappe.get_doc("File", {"file_url": doc.import_file})
		data = read_all(file_doc.get_full_path(), workdir)
		log.append(f"Files read: {data.files_read}")
		for label, kind, rows in data.sheets:
			log.append(f"  {kind:9} {rows:6} rows  {label}")
		counts = Importer(doc, data, log).run()
		doc.reload()
		doc.update(counts)
		doc.issues_found = len(data.issues)
		doc.set("issues", [])
		for wo_id, ref, issue in data.issues[:5000]:
			doc.append("issues", {"wo_id": wo_id, "reference": (ref or "")[:255], "issue": issue})
		if len(data.issues) > 5000:
			log.append(f"Only the first 5000 of {len(data.issues)} issues are listed.")
		doc.status = "Completed"
		doc.finished_at = now_datetime()
		doc.log = "\n".join(log)
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		log.append(traceback.format_exc())
		frappe.db.set_value("FTTH Import", import_name,
							{"status": "Failed", "finished_at": now_datetime(), "log": "\n".join(log)})
		frappe.db.commit()
		frappe.log_error(title=f"FTTH Import {import_name} failed")
	finally:
		shutil.rmtree(workdir, ignore_errors=True)
		frappe.publish_realtime(PROGRESS_EVENT, {"done": True}, doctype="FTTH Import", docname=import_name)


def _std_values(name):
	now, user = now_datetime(), frappe.session.user
	return {"name": name, "creation": now, "modified": now, "owner": user, "modified_by": user, "docstatus": 0}


class Importer:
	def __init__(self, import_doc, data, log):
		self.doc, self.data, self.log = import_doc, data, log
		self.mode = import_doc.existing_records or FILL
		self.counts = dict(work_orders_created=0, work_orders_updated=0, work_orders_skipped=0,
						   work_orders_failed=0, routes_created=0, points_created=0, sites_created=0,
						   links_created=0, links_updated=0, masters_created=0, connections_made=0)
		self.total = max(1, len(data.work_orders) + len(data.sites) + 4)
		self.done = 0
		self.gis_codes = set()
		self.canon = {}  # doctype -> {lower name: real name}
		self.matcher = None

	# ---------------------------------------------------------------- helpers
	def progress(self, label, step=1):
		self.done += step
		if self.done % 25 == 0 or step > 1 or self.done >= self.total:
			frappe.publish_realtime(PROGRESS_EVENT, {"progress": min(self.done, self.total), "total": self.total,
													 "label": label}, doctype="FTTH Import", docname=self.doc.name)
			frappe.db.commit()

	def insert(self, doc_dict):
		doc = frappe.get_doc(doc_dict)
		doc.flags.from_ftth_import = True
		doc.insert(ignore_permissions=True)
		return doc

	def merge_into(self, doc, values):
		"""Apply import values to an existing document according to the chosen mode."""
		if self.mode == SKIP:
			return False
		changed = False
		for k, v in values.items():
			if k.startswith("_") or v in (None, "") or not doc.meta.has_field(k):
				continue
			current = doc.get(k)
			if self.mode == FILL and current not in (None, "", 0):
				continue
			if str(current) != str(v):
				doc.set(k, v)
				changed = True
		if changed:
			doc.flags.from_ftth_import = True
			doc.save(ignore_permissions=True)
		return changed

	# ---------------------------------------------------------------- steps
	def run(self):
		self.settings()
		self.masters()
		self.progress("Masters", 1)
		self.kmz_routes()
		self.kmz_points()
		self.progress("KMZ", 1)
		self.links()
		self.progress("Link register", 1)
		self.node_sites()
		self.build_matcher()
		self.work_orders()
		self.approvals()
		self.progress("Approvals", 1)
		self.billing_to_work_orders()
		self.log.append(", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in self.counts.items()))
		return self.counts

	def settings(self):
		s = frappe.get_single("FTTH Settings")
		changed = False
		for key, val in self.data.settings.items():
			if val and not s.get(key):
				s.set(key, val)
				changed = True
		if changed:
			s.flags.ignore_permissions = True
			s.save()

	def _canon_map(self, doctype):
		if doctype not in self.canon:
			self.canon[doctype] = {n.lower(): n for n in frappe.get_all(doctype, pluck="name")}
		return self.canon[doctype]

	def canonical(self, doctype, name):
		"""Existing record name for `name`, ignoring case (MariaDB names are case-insensitive)."""
		if not name:
			return None
		return self._canon_map(doctype).get(str(name).strip().lower())

	def ensure(self, doctype, field, name, extra=None):
		"""Create a master record if it doesn't exist yet; return its real name."""
		name = (str(name).strip() if name else "")[:140]
		if not name:
			return None
		found = self.canonical(doctype, name)
		if found:
			return found
		self.insert({"doctype": doctype, field: name, **(extra or {})})
		self._canon_map(doctype)[name.lower()] = name
		self.counts["masters_created"] += 1
		return name

	def masters(self):
		for name, info in self.data.staff.items():
			found = self.canonical("Field Staff", name)
			if found:
				cur = frappe.db.get_value("Field Staff", found, ["contact_no", "staff_type"], as_dict=True)
				upd = {}
				if info.get("contact_no") and not cur.contact_no:
					upd["contact_no"] = info["contact_no"]
				if cur.staff_type in STAFF_RANK and STAFF_RANK.index(info["staff_type"]) < STAFF_RANK.index(cur.staff_type):
					upd["staff_type"] = info["staff_type"]
				if upd:
					frappe.db.set_value("Field Staff", found, upd)
				continue
			self.ensure("Field Staff", "staff_name", name,
						{"staff_type": info["staff_type"], "contact_no": info.get("contact_no")})
		existing = set(frappe.get_all("GIS Node", pluck="name"))
		for code, row in self.data.gis.items():
			row = {k: v for k, v in row.items() if v}
			for f in ("area_manager", "manager", "company_engineer"):
				if row.get(f):
					row[f] = self.canonical("Field Staff", row[f])
			row = {k: v for k, v in row.items() if v}
			if code in existing:
				# fill what an earlier import left empty (e.g. a GIS first seen only in billing data)
				doc = frappe.get_doc("GIS Node", code)
				if doc.area == code and row.get("area"):
					doc.area = row["area"]
				self.merge_into(doc, {k: v for k, v in row.items() if k != "gis_code"})
				continue
			row.setdefault("area", code)
			self.insert({"doctype": "GIS Node", **row})
			existing.add(code)
			self.counts["masters_created"] += 1
		self.gis_codes = existing
		vendors = set(self.data.ibd_teams) | {l["vendor"] for l in self.data.links.values() if l.get("vendor")}
		for name in sorted(vendors):
			self.ensure("IBD Team", "team_name", name)
		for name in sorted(self.data.fiber_teams):
			self.ensure("Fiber Team", "team_name", name)
		frappe.db.commit()

	def _gis(self, code):
		code = (code or "").strip().upper()
		return code if code in self.gis_codes else None

	def kmz_routes(self):
		have = set(frappe.get_all("KMZ Route", pluck="dedupe_key"))
		fields = ["name", "creation", "modified", "owner", "modified_by", "docstatus", "route_name", "a_end",
				  "b_end", "length_m", "node_folder", "gis", "source_file", "location", "dedupe_key"]
		values = []
		for r in self.data.routes:
			if r["dedupe_key"] in have:
				continue
			have.add(r["dedupe_key"])
			std = _std_values(frappe.generate_hash(length=10))
			values.append([std[f] for f in fields[:6]] + [
				r["route_name"], r["a_end"], r["b_end"], r["length_m"], r["node_folder"], self._gis(r["node_folder"]),
				r["source_file"], feature_collection([line_feature(r["coords"], r["route_name"])]), r["dedupe_key"]])
		if values:
			frappe.db.bulk_insert("KMZ Route", fields, values, ignore_duplicates=True, chunk_size=2000)
		self.counts["routes_created"] = len(values)
		frappe.db.commit()

	def kmz_points(self):
		have = set(frappe.get_all("KMZ Point", pluck="dedupe_key"))
		fields = ["name", "creation", "modified", "owner", "modified_by", "docstatus", "point_name", "latitude",
				  "longitude", "node_folder", "gis", "source_file", "dedupe_key"]
		values = []
		for p in self.data.points:
			if p["dedupe_key"] in have:
				continue
			have.add(p["dedupe_key"])
			std = _std_values(frappe.generate_hash(length=10))
			values.append([std[f] for f in fields[:6]] + [
				p["point_name"], p["latitude"], p["longitude"], p["node_folder"], self._gis(p["node_folder"]),
				p["source_file"], p["dedupe_key"]])
		if values:
			frappe.db.bulk_insert("KMZ Point", fields, values, ignore_duplicates=True, chunk_size=5000)
		self.counts["points_created"] = len(values)
		frappe.db.commit()

	def links(self):
		link_ids = set(self.data.links) | set(self.data.hotos)
		if not link_ids:
			return
		have = set(frappe.get_all("FTTH Link", pluck="name"))
		fields = ["name", "creation", "modified", "owner", "modified_by", "docstatus", "link_id", "link_date",
				  "company", "link_type", "vendor", "supervisor", "a_end", "b_end", "area", "distance",
				  "installation_date", "gis", "is_billed", "source_file"]
		hfields = ["name", "creation", "modified", "owner", "modified_by", "docstatus", "parent", "parenttype",
				   "parentfield", "idx", "hoto_no", "hoto_date", "year", "section_name", "gis", "site_rfs_month",
				   "fiber_type"]
		values, hvalues = [], []
		for lid in sorted(link_ids):
			r = dict(self.data.links.get(lid, {"link_id": lid}))
			r["vendor"] = self.canonical("IBD Team", r.get("vendor"))
			r["supervisor"] = self.canonical("Field Staff", r.get("supervisor"))
			hotos = self.data.hotos.get(lid, [])
			if lid in have:
				doc = frappe.get_doc("FTTH Link", lid)
				changed = self.merge_into(doc, {k: v for k, v in r.items() if k != "link_id"})
				known = {(h.hoto_no, str(h.hoto_date)) for h in doc.hotos}
				new = [h for h in hotos if (h["hoto_no"], str(h["hoto_date"])) not in known]
				for h in new:
					doc.append("hotos", {**h, "gis": self._gis(h["gis"])})
				if new:
					doc.is_billed = 1
					doc.save(ignore_permissions=True)
				if changed or new:
					self.counts["links_updated"] += 1
				continue
			gis = next((self._gis(h["gis"]) for h in hotos if self._gis(h["gis"])), None)
			std = _std_values(lid)
			values.append([std[f] for f in fields[:6]] + [
				lid, r.get("link_date"), r.get("company"), r.get("link_type"), r.get("vendor"),
				r.get("supervisor"), (r.get("a_end") or "")[:255] or None, (r.get("b_end") or "")[:255] or None,
				r.get("area"), r.get("distance") or 0, r.get("installation_date"), gis, 1 if hotos else 0,
				(r.get("source_file") or "")[:255]])
			for i, h in enumerate(hotos, 1):
				hs = _std_values(frappe.generate_hash(length=10))
				hvalues.append([hs[f] for f in hfields[:6]] + [lid, "FTTH Link", "hotos", i, h["hoto_no"], h["hoto_date"],
															   h["year"], (h["section_name"] or "")[:255] or None,
															   self._gis(h["gis"]), h["site_rfs_month"], h["fiber_type"]])
		if values:
			frappe.db.bulk_insert("FTTH Link", fields, values, ignore_duplicates=True, chunk_size=2000)
		if hvalues:
			frappe.db.bulk_insert("FTTH Link HOTO", hfields, hvalues, ignore_duplicates=True, chunk_size=2000)
		self.counts["links_created"] = len(values)
		frappe.db.commit()

	def node_sites(self):
		from emp_tracking.ftth.logic import norm

		have = set(frappe.get_all("Node Site", pluck="dedupe_key"))
		for s in self.data.sites.values():
			key = f"{norm(s['site_name'])}|{norm(s['gis'])}"[:255]
			if key not in have:
				rec = {k: v for k, v in s.items() if v not in (None, "")}
				rec["gis"] = self._gis(s.get("gis"))
				self.insert({"doctype": "Node Site", **rec, "dedupe_key": key})
				have.add(key)
				self.counts["sites_created"] += 1
			self.progress("Node sites")

	def build_matcher(self):
		"""Index every link-register name and KMZ pin once, for fast matching of thousands of work orders."""
		m = Matcher()
		for l in frappe.get_all("FTTH Link", fields=["name", "a_end", "b_end", "gis"]):
			m.add_link(l.name, (l.a_end, l.b_end), (l.gis,))
		for h in frappe.get_all("FTTH Link HOTO", fields=["parent", "section_name", "gis"]):
			m.add_link(h.parent, (h.section_name,), (h.gis,))
		for p in frappe.get_all("KMZ Point", fields=["name", "point_name", "latitude", "longitude", "gis"]):
			m.add_point(p.name, p.point_name, p.latitude, p.longitude, p.gis)
		self.matcher = m

	def connect(self, values):
		"""Fill link-register and KMZ-pin connections (and missing coordinates) on an import record."""
		from emp_tracking.ftth.logic import parse_lat_long

		made = False
		m = self.matcher
		lid = values.get("evisions_link_id")
		if lid and frappe.db.exists("FTTH Link", lid):
			values["ftth_link"] = lid
		elif not lid:
			found = m.match_link(values.get("end_location"), values.get("gis"))
			if found:
				values["ftth_link"] = values["evisions_link_id"] = found
				made = True
		for name_field, ll_field, point_field in (("end_location", "end_lat_long", "end_point"),
												  ("_b_end", "b_end_lat_long", "b_end_point")):
			if name_field == "_b_end":
				name = values.get("new_b_end") or values.get("b_end")
			else:
				name = values.get(name_field)
			if not name:
				continue
			near = parse_lat_long(values.get(ll_field))
			pin = m.match_point(name, values.get("gis"), near if near[0] else None)
			if pin:
				values[point_field] = pin[0]
				if not near[0]:
					values[ll_field] = f"{pin[1]:.7f}, {pin[2]:.7f}"
				made = True
		if made:
			self.counts["connections_made"] += 1

	def find_work_order(self, rec):
		if rec.get("wo_id"):
			name = frappe.db.get_value("FTTH Work Order", {"wo_id": rec["wo_id"]})
			if name:
				return name
		if rec.get("unique_id"):
			name = frappe.db.get_value("FTTH Work Order", {"unique_id": rec["unique_id"]})
			if name:
				return name
		if not rec.get("wo_id") and rec.get("end_location"):
			return frappe.db.get_value("FTTH Work Order", {"end_location": rec["end_location"], "gis": rec.get("gis")})
		return None

	def work_orders(self):
		for rec in self.data.work_orders.values():
			ref = rec.get("wo_id") or rec.get("unique_id") or ""
			values = {k: v for k, v in rec.items() if v not in (None, "") and k != "wo_id"}
			if values.get("gis") and not self._gis(values["gis"]):
				values.pop("gis")
			for link_field, doctype in (("ibd_team", "IBD Team"), ("fiber_team", "Fiber Team"),
										("splicer", "Field Staff"), ("assistant_splicer", "Field Staff"),
										("splicer_2", "Field Staff"), ("rider_1", "Field Staff"), ("rider_2", "Field Staff")):
				if values.get(link_field):
					real = self.canonical(doctype, values[link_field])
					if real:
						values[link_field] = real
					else:
						values.pop(link_field)
			self.connect(values)
			values["ftth_import"] = self.doc.name if frappe.db.exists("FTTH Import", self.doc.name) else None
			frappe.db.savepoint("ftth_wo")
			try:
				existing = self.find_work_order(rec)
				if existing:
					doc = frappe.get_doc("FTTH Work Order", existing)
					if self.merge_into(doc, values):
						self.counts["work_orders_updated"] += 1
					else:
						self.counts["work_orders_skipped"] += 1
				else:
					self.insert({"doctype": "FTTH Work Order", **values})
					self.counts["work_orders_created"] += 1
			except Exception as e:
				frappe.db.rollback(save_point="ftth_wo")
				self.counts["work_orders_failed"] += 1
				self.data.issue(ref, rec.get("end_location"), f"Could not save work order: {frappe.as_unicode(e)[:300]}")
				frappe.clear_messages()
			self.progress("Work orders")

	def approvals(self):
		"""Approvals whose work order was not in this file: apply to work orders already in the database."""
		for keys, ap in self.data.approvals:
			name = None
			for key in keys:
				kind, _sep, value = key.partition(":")
				field = "wo_id" if kind == "wo" else "unique_id"
				name = frappe.db.get_value("FTTH Work Order", {field: value})
				if name:
					break
			if name:
				try:
					self.merge_into(frappe.get_doc("FTTH Work Order", name), ap)
				except Exception as e:
					self.data.issue(name, ap.get("_end"), f"Could not apply mail approval: {frappe.as_unicode(e)[:200]}")
		frappe.db.commit()

	# Date: 2026-10-29
	def billing_to_work_orders(self):
		"""Billing rows without a Link ID: put the HOTO details on the work order whose building name
		(End Location) and GIS are the same. When several work orders share the name, the one whose
		RFS month equals the row's Site RFS Month is used. Rows that cannot be placed become Issues."""
		if not self.data.wo_billing:
			return
		index = {}
		for w in frappe.get_all("FTTH Work Order", fields=["name", "end_location", "gis", "rfs_month"]):
			index.setdefault((norm(w.end_location or ""), (w.gis or "").upper()), []).append(w)
		placed = 0
		for h in self.data.wo_billing:
			gis = (self._gis(h.get("gis")) or "").upper()
			cands = index.get((norm(h["section_name"]), gis), [])
			if len(cands) > 1 and h.get("site_rfs_month"):
				month = h["site_rfs_month"].strftime("%Y-%m")
				cands = [w for w in cands if w.rfs_month == month] or cands
			if len(cands) != 1:
				why = "several work orders have this name" if cands else "no work order with this building name"
				self.data.issue("", h["section_name"], f"Billing row (no Link ID) not placed: {why} on GIS {gis or '-'}")
				continue
			try:
				self.merge_into(frappe.get_doc("FTTH Work Order", cands[0].name), hoto_values([h]))
				placed += 1
			except Exception as e:
				self.data.issue(cands[0].name, h["section_name"], f"Could not apply billing: {frappe.as_unicode(e)[:200]}")
		self.log.append(f"Billing rows without Link ID placed on work orders: {placed} of {len(self.data.wo_billing)}")
		frappe.db.commit()
