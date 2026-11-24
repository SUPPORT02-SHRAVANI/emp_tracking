# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Team Monthly Cable: server code
#
# How this file works
#   One record = one cable entry of a Maintenance Team: date, Maintenance or Project, metres
#   and (optionally) where. Teams add entries one by one as work is done, either from the
#   quick-entry "+ Add" popup or from "Add for All Teams" on the list (add_entries: one date,
#   metres for every team in one grid). Month is set from the date on save; the Team Cable
#   Summary report adds entries up per month and team.
#   Past data: the "Fiber Maintenance & Project Data" sheet (Apr-Aug 2026) is stored as one
#   record per team, month and work type, ticked "Monthly Total from Sheet".
#
# Change log
#   2026-10-27  Created.
#   2026-10-27  One record per entry (Date instead of Month only, CBL- names, several entries per
#               month allowed); quick entry; add_entries for the "Add for All Teams" grid.
# ---------------------------------------------------------------------------------------------

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_first_day


class TeamMonthlyCable(Document):
	# Date: 2026-10-27
	def validate(self):
		self.month = get_first_day(self.date)
		if flt(self.total_cable) <= 0:
			frappe.throw(_("Total Cable must be more than 0 metres"))
		self.warn_if_repeated()

	# Date: 2026-10-27
	def warn_if_repeated(self):
		"""Warn (not block) when the same team, date, work type and metres were already entered.

		Two jobs on one day can have the same length, so this is only a hint against double entry.
		"""
		if self.is_monthly_total:
			return
		same = frappe.db.exists("Team Monthly Cable", {"team": self.team, "date": self.date,
			"work_type": self.work_type, "total_cable": self.total_cable, "name": ["!=", self.name]})
		if same:
			frappe.msgprint(_("{0} already has {1} m of {2} on this date ({3}). Saved anyway; delete one if it is a double entry.")
				.format(self.team, frappe.format(self.total_cable), self.work_type, same),
				indicator="orange", alert=True)


# Date: 2026-10-27
@frappe.whitelist()
def add_entries(date, work_type, rows, location=None, remarks=None):
	"""Create one entry per team row with metres > 0 ("Add for All Teams" on the list).

	rows: [{"team": ..., "total_cable": ...}]. Runs as the user, so their create permission
	applies; everything is saved or, if one row fails, nothing (one request = one transaction).
	"""
	rows = json.loads(rows) if isinstance(rows, str) else rows
	names = []
	for row in rows or []:
		if not row.get("team") or flt(row.get("total_cable")) <= 0:
			continue
		doc = frappe.get_doc({"doctype": "Team Monthly Cable", "date": date, "work_type": work_type,
			"team": row["team"], "total_cable": flt(row["total_cable"]), "location": location, "remarks": remarks})
		doc.insert()
		names.append(doc.name)
	if not names:
		frappe.throw(_("Enter the metres for at least one team"))
	return names
