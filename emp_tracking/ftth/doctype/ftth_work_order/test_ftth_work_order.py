# Copyright (c) 2026, Softworld and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

# 2026-11-24: setUp() makes the GIS Node and IBD Team these tests need, so Frappe must not build
# sample records for the linked doctypes. Its generator follows links deep into ERPNext and stops
# at Payment Gateway (payments app, not installed), which failed the whole CI test run.
IGNORE_TEST_RECORD_DEPENDENCIES = ["FTTH Import", "FTTH Link", "Fiber Team", "Field Staff", "GIS Node",
	"IBD Team", "KMZ Point", "KMZ Route", "Network Link", "User"]

WO = "BAL-ANG-UASL-ROM-Maharashtra/PUNE/Capex/FTTH/B2C/New Rollout/Midrise/IBW/20022025/{}"


class TestFTTHWorkOrder(FrappeTestCase):
	def setUp(self):
		# 2026-11-24: GIS Node.area_manager is a Link to Field Staff, so the manager must exist first
		# (the tests still passed plain text and failed with LinkValidationError).
		if not frappe.db.exists("Field Staff", "Test Manager"):
			frappe.get_doc({"doctype": "Field Staff", "staff_name": "Test Manager", "staff_type": "Area Manager",
							"contact_no": "9000000000"}).insert()
		if not frappe.db.exists("GIS Node", "ZZT"):
			frappe.get_doc({"doctype": "GIS Node", "gis_code": "ZZT", "area": "Test Area", "team": "Team 9",
							"area_manager": "Test Manager", "area_manager_no": "9000000000"}).insert()
		if not frappe.db.exists("IBD Team", "Test IBD"):
			frappe.get_doc({"doctype": "IBD Team", "team_name": "Test IBD"}).insert()

	def make(self, wo_id, fresh=True, **kw):
		if fresh:
			for name in frappe.get_all("FTTH Work Order", {"wo_id": wo_id}, pluck="name"):
				frappe.delete_doc("FTTH Work Order", name)
		return frappe.get_doc({
			"doctype": "FTTH Work Order", "wo_number": WO.format(wo_id), "gis": "ZZT", "ibd_team": "Test IBD",
			"end_location": "Test Residency", "end_lat_long": "18.5210, 73.9083", "planning_distance": 130, **kw,
		}).insert()

	def test_auto_fields(self):
		doc = self.make("990001")
		self.assertEqual(doc.wo_id, "990001")
		self.assertTrue(doc.name.startswith("FTTH-"))
		self.assertEqual(str(doc.wo_date), "2025-02-20")
		self.assertEqual(doc.segment, "B2C")
		self.assertEqual(doc.building_type, "Midrise")
		self.assertEqual(doc.area, "Test Area")  # fetched from GIS Node
		self.assertEqual(doc.area_manager_no, "9000000000")
		self.assertEqual(doc.eff_final_distance, 130)
		self.assertEqual(doc.status, "Survey")
		self.assertAlmostEqual(doc.latitude, 18.521)

	def test_duplicate_blocked(self):
		self.make("990002")
		self.assertRaises(frappe.UniqueValidationError, self.make, "990002", fresh=False)

	def test_issue_puts_on_hold(self):
		doc = self.make("990004", issue_type="Permission Issue A End")
		self.assertEqual(doc.status, "On Hold")

	def test_rfs_and_warning(self):
		doc = self.make("990003", distance_shared=200, rfs_date="2025-03-05", kmz_done=1)
		self.assertEqual(doc.status, "RFS Done")
		self.assertEqual(doc.has_warnings, 1)
		self.assertIn("shared to Airtel", doc.warnings)
