# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# Leaderboard Settings: point values for the Performance Leaderboard report.
# Created: 2026-10-24. The report reads these through get_points() and falls back to
# emp_tracking.performance.DEFAULT_POINTS for any value never saved.

from frappe.model.document import Document


class LeaderboardSettings(Document):
	pass
