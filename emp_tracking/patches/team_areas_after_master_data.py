# ---------------------------------------------------------------------------------------------
# Patch: place everything in the team areas again once the master data is in (2026-11-28).
# On the main site the team areas patches ran before any Network Link / Site / node position
# existed (the FTTH Master Data loaders came in a later deploy), so nothing was placed in
# Area 1-6. The loaders run before this patch; this runs the same placement as team_areas_v2
# (nodes, links, localities, complaints, Areas tree) over the loaded data. Safe to run again.
# ---------------------------------------------------------------------------------------------


def execute():
	from emp_tracking.patches import team_areas_v2

	team_areas_v2.execute()
