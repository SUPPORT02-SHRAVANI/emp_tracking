# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# FTTH Master Data: one row per FTTH site (OverHead Project menu)
#
# How this file works
#   The DocType holds the 51 columns of the "Master Data for Software - ODN sites only" sheet
#   (WO, site, survey, approval, fiber, splicing, completion). The sheet's rows are loaded once by
#   the patch emp_tracking.ftth.patches.import_ftth_master_data. Values are kept as written in the
#   sheet; distances such as "150+450" stay text, so nothing is lost on import.
#   validate() only tidies what people type later: spaces around names, and Year from Month.
#
# Change log
#   2026-11-27  Created (user's request: one master in OverHead Project with this sheet's data).
# ---------------------------------------------------------------------------------------------

from frappe.model.document import Document
from frappe.utils import getdate


class FTTHMasterData(Document):
	# Date: 2026-11-27
	def validate(self):
		for field in ("end_location_name", "gis", "wo", "evisions_link_id"):
			if self.get(field):
				self.set(field, self.get(field).strip())
		# Year follows the completion month, as in the sheet (Year = YEAR(Months))
		if self.month and not self.year:
			self.year = getdate(self.month).year
