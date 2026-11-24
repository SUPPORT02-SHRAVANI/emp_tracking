# Copyright (c) 2026, Softworld and contributors
# See license.txt
"""Pure-python tests: `python -m unittest emp_tracking.ftth.tests.test_logic` or `bench run-tests --app ftth_tracker`."""

import datetime as dt
import unittest

from emp_tracking.ftth.logic import (
	classify_issue,
	derive,
	excel_date,
	fiber_type,
	effective_distances,
	line_length_m,
	parse_lat_long,
	parse_wo_number,
	split_route_name,
)

WO = "BAL-ANG-UASL-ROM-Maharashtra/PUNE/Capex/FTTH/B2C/New Rollout/Midrise/IBW/20022025/104922"


class TestLogic(unittest.TestCase):
	def test_wo_number(self):
		info = parse_wo_number(WO)
		self.assertEqual(info["wo_id"], "104922")
		self.assertEqual(info["wo_date"], dt.date(2025, 2, 20))
		self.assertEqual(info["segment"], "B2C")
		self.assertEqual(info["building_type"], "Midrise")
		b2b = parse_wo_number("X/PUNE/Capex/FTTH/B2B/New Rollout/Flatbed(G+3)/IBW/28052025/111776")
		self.assertEqual((b2b["segment"], b2b["building_type"]), ("B2B", "Flatbed(G+3)"))
		self.assertIsNone(parse_wo_number("")["wo_id"])

	def test_lat_long_formats(self):
		for text in ("18.5210, 73.9083", "18.5210,73.9083", "18.5210 73.9083", " 18.5210 ,  73.9083 "):
			self.assertEqual(parse_lat_long(text), (18.521, 73.9083))
		self.assertEqual(parse_lat_long("abc"), (None, None))
		self.assertEqual(parse_lat_long("118.5 73.9"), (None, None))

	def test_blank_distance_means_same(self):
		self.assertEqual(effective_distances(130, None, None, None), (130, 130, 130))
		self.assertEqual(effective_distances(1220, 260, None, None), (260, 260, 260))
		self.assertEqual(effective_distances(220, 0, 0, 250), (220, 220, 250))

	def test_route_split_and_length(self):
		self.assertEqual(split_route_name("Gera Grand to ODF GARDEN VIEW"), ("Gera Grand", "ODF GARDEN VIEW"))
		# ~111 m per 0.001 deg latitude
		self.assertAlmostEqual(line_length_m([(73.9, 18.5), (73.9, 18.501)]), 111.2, delta=0.5)

	def test_derive_status_and_warnings(self):
		d = {
			"wo_number": WO, "wo_received_date": dt.date(2025, 2, 20), "ibd_team": "R.K.TECHNOSMART",
			"end_lat_long": "18.52108963626364, 73.90838399580204", "planning_distance": 220,
			"distance_shared": 250, "fiber_id": "20354", "fiber_reading_a": 400, "fiber_reading_b": 180,
			"rfs_date": dt.date(2025, 3, 1), "kmz_done": 0, "kmz_route_length": 400,
		}
		out = derive(d)
		self.assertEqual(out["status"], "RFS Done")
		self.assertEqual(out["wo_id"], "104922")
		self.assertEqual(out["eff_final_distance"], 220)
		self.assertEqual(out["eff_shared_distance"], 250)
		self.assertEqual(out["fiber_used"], 220)
		self.assertEqual(out["rfs_month"], "2025-03")
		self.assertEqual(out["days_to_rfs"], 9)
		self.assertAlmostEqual(out["latitude"], 18.5210896, places=6)
		self.assertEqual(out["has_warnings"], 1)
		text = out["warnings"]
		self.assertIn("shared to Airtel", text)
		self.assertIn("KMZ route length", text)
		self.assertIn("KMZ not marked", text)

	def test_status_progression(self):
		base = {"wo_number": WO, "ibd_team": "x"}
		self.assertEqual(derive(base)["status"], "New")
		self.assertEqual(derive({**base, "planning_distance": 100})["status"], "Survey")
		self.assertEqual(derive({**base, "planning_distance": 100, "fiber_id": "1"})["status"], "Fiber Laid")
		snaps = {**base, "fiber_id": "1", "splicing_snap_a": "/a.jpg", "splicing_snap_b": "/b.jpg"}
		self.assertEqual(derive(snaps)["status"], "Splicing Done")


class TestMonthlySheetRules(unittest.TestCase):
	def test_wo_number_variants(self):
		self.assertEqual(parse_wo_number("MWO NO :-" + WO)["wo_id"], "104922")
		self.assertIsNone(parse_wo_number("-")["wo_id"])
		self.assertIsNone(parse_wo_number("18.4874450625903 73.8731656967")["wo_id"])
		self.assertIsNone(parse_wo_number("AATMANAND APARTMENT")["wo_id"])

	def test_classify_issue(self):
		cases = {
			"Permission issue  A END": "Permission Issue A End",
			"Permission Issue B end": "Permission Issue B End",
			"Permission issue B END, , Mail Approval required": "Permission Issue B End",
			"Mail Approval Required": "Mail Approval Required",
			"OLT pending": "OLT Pending",
			"Completed": "Completed",
			"cancle site": "Cancelled",
			"Yet to Start": "Yet to Start",
			"B end not Belong to Evisions": "B End Not Evisions",
			"Site location not recived": "Site Location Not Received",
			"something odd": "Other",
		}
		for text, expected in cases.items():
			self.assertEqual(classify_issue(text), expected, text)
		self.assertEqual(classify_issue(None, "WIP"), "WIP")  # falls back to the second text
		self.assertIsNone(classify_issue(None, ""))

	def test_dates_and_fiber(self):
		self.assertEqual(excel_date(45431), dt.date(2024, 5, 19))
		self.assertEqual(excel_date("19/3/2026"), dt.date(2026, 3, 19))
		self.assertIsNone(excel_date("19/3/20266"))
		self.assertIsNone(excel_date(200))
		self.assertEqual(fiber_type("24"), "24F")
		self.assertEqual(fiber_type("12F"), "12F")

	def test_status_rules(self):
		base = {"wo_number": WO, "ibd_team": "x", "gis": "G0B", "planning_distance": 100}
		self.assertEqual(derive({**base, "issue_type": "Permission Issue A End"})["status"], "On Hold")
		self.assertEqual(derive({**base, "issue_type": "Cancelled"})["status"], "Cancelled")
		self.assertEqual(derive({**base, "issue_type": "Completed"})["status"], "RFS Done")
		out = derive({**base, "work_completed_date": dt.date(2025, 4, 10)})
		self.assertEqual((out["status"], out["rfs_date"]), ("RFS Done", dt.date(2025, 4, 10)))
		self.assertIn("No WO number yet.", derive({"end_location": "x", "gis": "G0B", "ibd_team": "x"})["warnings"])


if __name__ == "__main__":
	unittest.main()
