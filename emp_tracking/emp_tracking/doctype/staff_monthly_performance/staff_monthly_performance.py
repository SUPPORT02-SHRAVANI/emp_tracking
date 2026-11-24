# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Staff Monthly Performance: server code
#
# How this file works
#   One record = one person's month: attendance (days, leaves), average daily time on field /
#   home / office location, maintenance calls with In / Out of SLA and MTTR. It holds the
#   figures of the monthly "Location and Calls Data" sheets (Supervisor, Splicer and Rider).
#   On save the month is moved to its 1st day, totals are worked out, the Employee is found
#   from the name when not picked, and the score is calculated with the weights in Leaderboard
#   Settings (emp_tracking.performance.score_calls). The Performance Leaderboard report
#   ("Maintenance Calls" source) ranks people on these records.
#
# Change log
#   2026-10-24  Created.
# ---------------------------------------------------------------------------------------------

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_first_day, getdate

from emp_tracking.performance import CALL_POINTS, score_calls


class StaffMonthlyPerformance(Document):
	# Date: 2026-10-24
	def autoname(self):
		# Readable and unique per person and month, e.g. "Sanket Kotkar - Apr 2025"
		self.month = get_first_day(self.month)
		self.name = f"{self.employee_name or self.employee} - {getdate(self.month):%b %Y}"

	# Date: 2026-10-24
	def validate(self):
		self.month = get_first_day(self.month)
		if not self.employee and self.employee_name:
			# Only an exact (case-insensitive) name match is linked; a guess could credit the wrong person
			self.employee = frappe.db.get_value("Employee", {"employee_name": self.employee_name.strip()})
		for field in ("total_leaves", "working_days", "main_calls", "assistant_calls", "in_sla", "out_sla"):
			if (self.get(field) or 0) < 0:
				frappe.throw(_("{0} cannot be negative").format(self.meta.get_label(field)))
		self.total_calls = (self.main_calls or 0) + (self.assistant_calls or 0)
		self.avg_calls_per_day = flt(self.total_calls / self.working_days, 2) if self.working_days else 0
		self.score = score_calls(self.as_dict(), get_call_points())


# Date: 2026-10-24
def get_call_points():
	"""Call weights from Leaderboard Settings; a field never saved falls back to CALL_POINTS."""
	stored = frappe.db.get_singles_dict("Leaderboard Settings")
	return {key: flt(stored[key]) if stored.get(key) not in (None, "") else default
		for key, default in CALL_POINTS.items()}
