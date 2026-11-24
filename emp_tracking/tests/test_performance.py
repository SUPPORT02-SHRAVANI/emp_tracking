# Copyright (c) 2026, milind and contributors
# See license.txt
"""Pure-python tests for the Performance Leaderboard scoring (created 2026-10-24):
`python -m unittest emp_tracking.tests.test_performance` or `bench run-tests --app emp_tracking`."""

import datetime as dt
import unittest

from emp_tracking.performance import (
	best_week_streak,
	build_call_leaderboard,
	build_leaderboard,
	level_for,
	score_calls,
	score_project,
)


def project(**kw):
	base = {"fiber_m": 0, "hp": 0, "days_to_rfs": None, "proof_complete": True, "rework": False,
		"rfs_date": dt.date(2026, 10, 1), "participants": []}
	base.update(kw)
	return base


class TestPerformance(unittest.TestCase):
	def test_score_components(self):
		s = score_project(project(fiber_m=450, hp=12, days_to_rfs=5))
		# 100 RFS + 45 fiber (450 m) + 12 HP + 50 on time + 20 clean
		self.assertEqual(s["total"], 227)
		late = score_project(project(days_to_rfs=30, proof_complete=False, rework=True))
		self.assertEqual(late["total"], 100 - 20 - 30)
		self.assertFalse(late["is_clean"])

	def test_custom_points(self):
		s = score_project(project(days_to_rfs=9), {"pts_rfs": 10, "rfs_target_days": 10, "pts_on_time": 5, "pts_clean": 0})
		self.assertEqual(s["total"], 15)

	def test_levels(self):
		self.assertEqual(level_for(0)[0], "Rookie")
		self.assertEqual(level_for(1000), ("Bronze", "Silver", 500, 50))
		self.assertEqual(level_for(12000)[:2], ("Diamond", None))
		self.assertEqual(level_for(-40)[0], "Rookie")

	def test_streak(self):
		d = dt.date(2026, 10, 5)  # a Monday
		dates = [d, d + dt.timedelta(days=8), d + dt.timedelta(days=15), d + dt.timedelta(days=35)]
		self.assertEqual(best_week_streak(dates), 3)
		self.assertEqual(best_week_streak([]), 0)

	def test_leaderboard_ranks_and_badges(self):
		rows = [project(participants=["A"], fiber_m=1000, days_to_rfs=3) for _ in range(5)]
		rows += [project(participants=["B", "C"], proof_complete=False)]
		board = build_leaderboard(rows)
		self.assertEqual([r["participant"] for r in board], ["A", "B", "C"])
		self.assertEqual([r["rank"] for r in board], [1, 2, 2])  # B and C share the job and the rank
		self.assertEqual(board[0]["medal"], "🥇")
		for badge in ("🚀 Speedster", "🧹 Clean Sheet", "🧵 Fiber King"):
			self.assertIn(badge, board[0]["badges"])
		self.assertEqual(board[0]["on_time_pct"], 100)
		self.assertEqual(board[1]["badges"], [])
		self.assertEqual(board[1]["missing_proof"], 1)

	# 2026-10-24: maintenance-call scoring, checked against the FY 2025-26 sheets
	def test_call_scores_match_sheets(self):
		# Supervisor sheet, Akash, April: 109 calls, 64 in SLA, 45 out -> 118.5
		self.assertEqual(score_calls({"designation": "Supervisor", "main_calls": 109, "in_sla": 64, "out_sla": 45}), 118.5)
		# Splicer MARKS SUMMARY, Ram Kedarkunte: 571 + 157 x 0.5 + 406 x 0.25 - 322 x 0.25 = 670.5
		self.assertEqual(score_calls({"designation": "Splicer", "main_calls": 571, "assistant_calls": 157,
			"in_sla": 406, "out_sla": 322}), 670.5)

	def test_call_leaderboard(self):
		month = {"designation": "Splicer", "assistant_calls": 0, "total_leaves": 1, "working_days": 25,
			"avg_field_time": 3600, "avg_working_time": 36000}
		recs = [{**month, "participant": "A", "main_calls": 40, "in_sla": 35, "out_sla": 5, "avg_mttr": 3600} for _ in range(3)]
		recs += [{**month, "participant": "B", "main_calls": 10, "in_sla": 2, "out_sla": 8, "avg_mttr": 7200,
			"total_leaves": 9, "avg_field_time": 7200}]
		board = build_call_leaderboard(recs)
		self.assertEqual([r["participant"] for r in board], ["A", "B"])
		a, b = board
		self.assertEqual((a["main_calls"], a["sla_pct"], a["avg_mttr"], a["months"]), (120, 88, 3600, 3))
		for badge in ("📞 Call Champ", "🎯 SLA Star", "⚡ Fast Fixer", "📅 Always There"):
			self.assertIn(badge, a["badges"])
		self.assertEqual(b["badges"], ["🏃 Field Warrior"])


if __name__ == "__main__":
	unittest.main()
