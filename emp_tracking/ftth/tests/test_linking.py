# Copyright (c) 2026, Softworld and contributors
# See license.txt

import unittest

from emp_tracking.ftth.linking import Matcher


class TestMatcher(unittest.TestCase):
	def setUp(self):
		self.m = Matcher()
		self.m.add_link("202311108", ["Balaji Crystal"], ["S8K"])
		self.m.add_link("202401001", ["Laxmi Residency"], ["G0B"])
		self.m.add_link("202402002", ["Laxmi Residency"], ["H6Q"])
		self.m.add_point("p1", "Laxmi Residency", 18.5210, 73.9083, "G0B")
		self.m.add_point("p2", "Laxmi Residency", 18.6000, 73.7000, "H6Q")

	def test_link_by_name_and_gis(self):
		self.assertEqual(self.m.match_link("balaji  crystal"), "202311108")
		self.assertIsNone(self.m.match_link("Laxmi Residency"))  # two candidates, no GIS
		self.assertEqual(self.m.match_link("Laxmi Residency", "H6Q"), "202402002")
		self.assertIsNone(self.m.match_link("Unknown Tower"))

	def test_pin_nearest_and_gis(self):
		self.assertEqual(self.m.match_point("Laxmi Residency", near=(18.5211, 73.9084))[0], "p1")
		self.assertIsNone(self.m.match_point("Laxmi Residency", near=(19.5, 74.5)))  # too far away
		self.assertEqual(self.m.match_point("Laxmi Residency", "H6Q")[0], "p2")
		self.assertIsNone(self.m.match_point("Laxmi Residency"))  # same name, two different places


if __name__ == "__main__":
	unittest.main()
