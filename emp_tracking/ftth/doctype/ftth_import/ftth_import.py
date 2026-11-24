# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt
#
# FTTH Import: one uploaded export file (zip / xlsx / kmz) and the result of loading it.
# validate() checks the file type. autoname() puts the file's month and year in the ID
# ("April 2026 FTTH Sheet.xlsx" -> IMP-APR-2026-00001) and falls back to the old IMP-##### series.
#
# Change log
#   2026-10-29  autoname(): month and year from the import file name go into the ID.
#   2026-10-29  Fallback IMP-##### continues after the highest existing IMP-<number> (the old IDs
#               were not counted in the "IMP-" series, so it restarted at IMP-00001 and clashed).

import os
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname

ALLOWED = (".zip", ".xlsx", ".xlsm", ".kmz", ".kml")
# a whole month word, short or full ("Apr", "April", "Sept"), so "Marquee" is not March
MONTH_WORD = re.compile(
	r"(?<![a-z])(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
	r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?![a-z])"
)


# Date: 2026-10-29
def month_year(file_url):
	"""('APR', '2026') from a file name such as 'April 2026 FTTH Sheet.xlsx', else None.
	Uses the first whole month word in the name and the first 20xx year."""
	name = os.path.basename(file_url or "").lower()
	month = MONTH_WORD.search(name)
	year = re.search(r"(?<!\d)20\d\d(?!\d)", name)
	return (month.group(1)[:3].upper(), year.group(0)) if month and year else None


class FTTHImport(Document):
	# Date: 2026-10-29
	def autoname(self):
		"""IMP-<MON>-<YEAR>-##### (own counter per month) when the file name carries a month
		and year; otherwise IMP-#####, the same counter the doctype used before."""
		my = month_year(self.import_file)
		if not my:
			sync_plain_series()
		self.name = make_autoname(f"IMP-{my[0]}-{my[1]}-.#####" if my else "IMP-.#####", doc=self)


# Date: 2026-10-29
def sync_plain_series():
	"""Raise the "IMP-" naming counter to the highest existing IMP-<number>, so a file name without
	a month/year gets the next free plain ID (e.g. IMP-31861) instead of an existing one."""
	highest = frappe.db.sql(
		"select max(cast(substring(name, 5) as unsigned)) from `tabFTTH Import` where name regexp %s",
		("^IMP-[0-9]+$",),
	)[0][0] or 0
	current = frappe.db.get_value("Series", "IMP-", "current", order_by="name")
	if current is None:
		frappe.db.sql("insert into `tabSeries` (name, current) values (%s, %s)", ("IMP-", highest))
	elif current < highest:
		frappe.db.sql("update `tabSeries` set current = %s where name = %s", (highest, "IMP-"))

	# Date: 2026-10-29 (existing code, comment added)
	def validate(self):
		"""Only zip / xlsx / kmz files; a new import always starts as Pending."""
		if self.import_file and not self.import_file.lower().endswith(ALLOWED):
			frappe.throw(_("Please attach a .zip, .xlsx or .kmz file."))
		if self.is_new():
			self.status = "Pending"
