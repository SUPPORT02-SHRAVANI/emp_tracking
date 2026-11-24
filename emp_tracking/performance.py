# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt
"""Points, levels, badges and streaks for the Performance Leaderboard report.

Created: 2026-10-24.

Nothing here imports frappe, so the scoring rules can be unit-tested anywhere:
	python -m unittest emp_tracking.tests.test_performance
The report (emp_tracking/emp_tracking/report/performance_leaderboard) reads completed
FTTH Work Orders, turns each into a plain dict (see score_project) and passes them in.
(2026-10-31: was New Projects; New Project was merged into FTTH Work Order.)

Change log:
	2026-10-24  Added maintenance-call scoring (score_calls, build_call_leaderboard) for the
	            monthly Staff Monthly Performance records (calls, SLA, MTTR, field time). The
	            weights reproduce the company's sheets: Supervisor = calls + 0.5 In SLA
	            - 0.5 Out SLA; Splicer = splicer calls + 0.5 assistant calls + 0.25 In SLA
	            - 0.25 Out SLA.
"""

import datetime as dt

# Fallback point values, used when the matching Leaderboard Settings field has never been saved.
DEFAULT_POINTS = {
	"pts_rfs": 100,  # every project that reached RFS in the period
	"pts_per_100m": 10,  # per 100 m of final distance laid
	"pts_per_hp": 1,  # per home passed
	"pts_on_time": 50,  # bonus when WO received -> RFS took no more than rfs_target_days
	"rfs_target_days": 7,
	"pts_clean": 20,  # bonus: all four proof snaps attached and no re-work
	"pts_missing_proof": 20,  # penalty: a fiber/splicing snap is missing on a completed project
	"pts_rework": 30,  # penalty: a re-work was required on the site
}

# (minimum points, level name), highest first
LEVELS = (
	(10000, "Diamond"),
	(6000, "Platinum"),
	(3000, "Gold"),
	(1500, "Silver"),
	(500, "Bronze"),
	(0, "Rookie"),
)

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

# Badge rules need a minimum number of projects so one lucky job does not earn them.
BADGE_MIN_RFS = 5
STREAK_BADGE_WEEKS = 4
CENTURY_RFS = 100


def score_project(p, points=None):
	"""Points earned by one completed project, split into components.

	p: dict with fiber_m, hp, days_to_rfs (None when unknown), proof_complete, rework.
	"""
	pts = {**DEFAULT_POINTS, **(points or {})}
	fiber_m = float(p.get("fiber_m") or 0)
	hp = int(p.get("hp") or 0)
	days = p.get("days_to_rfs")
	on_time = days is not None and 0 <= int(days) <= pts["rfs_target_days"]
	proof = bool(p.get("proof_complete"))
	rework = bool(p.get("rework"))
	clean = proof and not rework

	parts = {
		"rfs": pts["pts_rfs"],
		"fiber": round(fiber_m / 100 * pts["pts_per_100m"]),
		"hp": hp * pts["pts_per_hp"],
		"on_time": pts["pts_on_time"] if on_time else 0,
		"clean": pts["pts_clean"] if clean else 0,
		"missing_proof": 0 if proof else -pts["pts_missing_proof"],
		"rework": -pts["pts_rework"] if rework else 0,
	}
	parts["total"] = sum(parts.values())
	parts.update(fiber_m=fiber_m, hp_count=hp, is_on_time=on_time, is_clean=clean,
		is_missing_proof=not proof, is_rework=rework)
	return parts


def level_for(points):
	"""Return (level, next level or None, points still needed, % of the way to the next level)."""
	for i, (floor, name) in enumerate(LEVELS):
		if points >= floor:
			if i == 0:
				return name, None, 0, 100
			ceiling, next_name = LEVELS[i - 1]
			return name, next_name, ceiling - points, round((points - floor) * 100 / (ceiling - floor))
	# Negative totals (penalties only) still count as Rookie
	return "Rookie", "Bronze", LEVELS[-2][0] - points, 0


def best_week_streak(dates):
	"""Longest run of consecutive weeks (Monday start) with at least one RFS."""
	weeks = sorted({_week_start(d) for d in dates if isinstance(d, dt.date)})
	best = run = 0
	prev = None
	for w in weeks:
		run = run + 1 if prev and (w - prev).days == 7 else 1
		best = max(best, run)
		prev = w
	return best


def _week_start(d):
	if isinstance(d, dt.datetime):
		d = d.date()
	return d - dt.timedelta(days=d.weekday())


def build_leaderboard(projects, points=None):
	"""Aggregate completed projects into ranked leaderboard rows (dicts), best first.

	Each project dict carries "participants": everyone credited for it. Every participant
	gets the full points of the project (a shared job counts fully for each team member).
	"""
	board = {}
	for p in projects:
		score = score_project(p, points)
		for who in p.get("participants") or []:
			r = board.setdefault(who, {
				"participant": who, "points": 0, "rfs_done": 0, "fiber_m": 0.0, "home_pass": 0,
				"on_time": 0, "clean": 0, "missing_proof": 0, "rework": 0, "_days": [], "_dates": [],
			})
			r["points"] += score["total"]
			r["rfs_done"] += 1
			r["fiber_m"] += score["fiber_m"]
			r["home_pass"] += score["hp_count"]
			r["on_time"] += score["is_on_time"]
			r["clean"] += score["is_clean"]
			r["missing_proof"] += score["is_missing_proof"]
			r["rework"] += score["is_rework"]
			if p.get("days_to_rfs") is not None:
				r["_days"].append(int(p["days_to_rfs"]))
			r["_dates"].append(p.get("rfs_date"))

	rows = list(board.values())
	for r in rows:
		days, dates = r.pop("_days"), r.pop("_dates")
		r["avg_days"] = round(sum(days) / len(days), 1) if days else None
		r["on_time_pct"] = round(r["on_time"] * 100 / r["rfs_done"]) if r["rfs_done"] else 0
		r["streak_weeks"] = best_week_streak(dates)
		r["level"], r["next_level"], r["points_to_next"], r["level_progress"] = level_for(r["points"])

	# Ties on points go to more projects, then more fiber, then name for a stable order
	rows.sort(key=lambda r: (-r["points"], -r["rfs_done"], -r["fiber_m"], str(r["participant"])))
	rank = 0
	for i, r in enumerate(rows):
		# Equal points share a rank (1, 1, 3 ...)
		if i == 0 or r["points"] != rows[i - 1]["points"]:
			rank = i + 1
		r["rank"] = rank
		r["medal"] = MEDALS.get(rank, "")
	_award_badges(rows, (points or {}).get("rfs_target_days", DEFAULT_POINTS["rfs_target_days"]))
	return rows


def _award_badges(rows, target_days):
	top_fiber = max((r["fiber_m"] for r in rows), default=0)
	top_hp = max((r["home_pass"] for r in rows), default=0)
	for r in rows:
		badges = []
		if top_fiber > 0 and r["fiber_m"] == top_fiber:
			badges.append("🧵 Fiber King")
		if top_hp > 0 and r["home_pass"] == top_hp:
			badges.append("🏠 Home Hero")
		if r["rfs_done"] >= BADGE_MIN_RFS:
			if r["avg_days"] is not None and r["avg_days"] <= target_days:
				badges.append("🚀 Speedster")
			if r["missing_proof"] == 0 and r["rework"] == 0:
				badges.append("🧹 Clean Sheet")
		if r["streak_weeks"] >= STREAK_BADGE_WEEKS:
			badges.append("🔥 On Fire")
		if r["rfs_done"] >= CENTURY_RFS:
			badges.append("💯 Century")
		r["badges"] = badges


# ---------------------------------------------------------------------------------------------
# Maintenance calls (Staff Monthly Performance), added 2026-10-24
# ---------------------------------------------------------------------------------------------

# Fallback weights, used when the Leaderboard Settings field has never been saved. They are the
# weights of the "PERFORMACE ROOM" / "Total Score" columns in the FY 2025-26 sheets.
CALL_POINTS = {
	"pts_call": 1.0,  # per call handled as the main person (supervisor call / splicer call)
	"pts_assist_call": 0.5,  # per call as assistant splicer
	"pts_sup_in_sla": 0.5,  # supervisor: per call closed within SLA
	"pts_sup_out_sla": 0.5,  # supervisor: deducted per call closed out of SLA
	"pts_spl_in_sla": 0.25,  # splicer / rider: per call within SLA
	"pts_spl_out_sla": 0.25,  # splicer / rider: deducted per call out of SLA
}

SUPERVISOR = "Supervisor"
SLA_STAR_PCT = 70  # SLA Star badge: at least this share of calls within SLA ...
CALL_BADGE_MIN = 20  # ... and badges that judge quality need at least this many calls
ALWAYS_THERE_LEAVES = 2  # Always There badge: no more than this many leaves a month on average
ALWAYS_THERE_MONTHS = 3


def score_calls(r, points=None):
	"""Points for one person-month: r has designation, main_calls, assistant_calls, in_sla, out_sla."""
	pts = {**CALL_POINTS, **(points or {})}
	main, assist = r.get("main_calls") or 0, r.get("assistant_calls") or 0
	in_sla, out_sla = r.get("in_sla") or 0, r.get("out_sla") or 0
	if r.get("designation") == SUPERVISOR:
		total = main * pts["pts_call"] + in_sla * pts["pts_sup_in_sla"] - out_sla * pts["pts_sup_out_sla"]
	else:
		total = (main * pts["pts_call"] + assist * pts["pts_assist_call"]
			+ in_sla * pts["pts_spl_in_sla"] - out_sla * pts["pts_spl_out_sla"])
	return round(total, 2)


def build_call_leaderboard(records, points=None):
	"""Aggregate person-month records into ranked rows (dicts), best first.

	Each record carries "participant" (the key to group on), designation, main_calls,
	assistant_calls, in_sla, out_sla, total_leaves, working_days, and durations in seconds:
	avg_mttr, avg_field_time, avg_working_time (None when unknown).
	"""
	board = {}
	for rec in records:
		r = board.setdefault(rec["participant"], {
			"participant": rec["participant"], "designation": rec.get("designation"), "points": 0.0,
			"months": 0, "main_calls": 0, "assistant_calls": 0, "in_sla": 0, "out_sla": 0,
			"leaves": 0, "working_days": 0, "_mttr": [], "_field": [], "_work": [],
		})
		r["points"] += score_calls(rec, points)
		r["months"] += 1
		for key in ("main_calls", "assistant_calls", "in_sla", "out_sla"):
			r[key] += rec.get(key) or 0
		r["leaves"] += rec.get("total_leaves") or 0
		r["working_days"] += rec.get("working_days") or 0
		if rec.get("avg_mttr"):
			# MTTR weighted by the month's own calls
			r["_mttr"].append((rec["avg_mttr"], (rec.get("main_calls") or 0) or 1))
		if rec.get("avg_field_time") is not None:
			r["_field"].append(rec["avg_field_time"])
		if rec.get("avg_working_time"):
			r["_work"].append(rec["avg_working_time"])

	rows = list(board.values())
	for r in rows:
		mttr, field, work = r.pop("_mttr"), r.pop("_field"), r.pop("_work")
		r["points"] = round(r["points"], 2)
		closed = r["in_sla"] + r["out_sla"]
		r["sla_pct"] = round(r["in_sla"] * 100 / closed) if closed else 0
		weight = sum(w for _, w in mttr)
		r["avg_mttr"] = round(sum(m * w for m, w in mttr) / weight) if weight else None
		r["avg_field_time"] = round(sum(field) / len(field)) if field else None
		r["avg_working_time"] = round(sum(work) / len(work)) if work else None
		r["level"], r["next_level"], r["points_to_next"], r["level_progress"] = level_for(r["points"])

	rows.sort(key=lambda r: (-r["points"], -r["main_calls"], str(r["participant"])))
	rank = 0
	for i, r in enumerate(rows):
		if i == 0 or r["points"] != rows[i - 1]["points"]:
			rank = i + 1
		r["rank"] = rank
		r["medal"] = MEDALS.get(rank, "")
	_award_call_badges(rows)
	return rows


def _award_call_badges(rows):
	top_calls = max((r["main_calls"] for r in rows), default=0)
	top_field = max((r["avg_field_time"] or 0 for r in rows), default=0)
	enough = [r for r in rows if r["main_calls"] + r["assistant_calls"] >= CALL_BADGE_MIN and r["avg_mttr"]]
	best_mttr = min((r["avg_mttr"] for r in enough), default=None)
	for r in rows:
		badges = []
		if top_calls and r["main_calls"] == top_calls:
			badges.append("📞 Call Champ")
		if r in enough and r["sla_pct"] >= SLA_STAR_PCT:
			badges.append("🎯 SLA Star")
		if best_mttr is not None and r in enough and r["avg_mttr"] == best_mttr:
			badges.append("⚡ Fast Fixer")
		if top_field and r["avg_field_time"] == top_field:
			badges.append("🏃 Field Warrior")
		if r["months"] >= ALWAYS_THERE_MONTHS and r["leaves"] <= ALWAYS_THERE_LEAVES * r["months"]:
			badges.append("📅 Always There")
		r["badges"] = badges
