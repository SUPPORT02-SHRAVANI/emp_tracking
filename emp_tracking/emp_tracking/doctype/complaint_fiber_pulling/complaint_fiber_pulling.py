# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Complaint Fiber Pulling: child table of Complaint Information
#
# How this file works
#   One row per stretch of new fibre pulled while restoring a link: which Fiber Pulling Team,
#   the core, the length in metres and where (lat/long). No logic of its own.
#
# Change log
#   2026-10-09  Created for the OH maintenance flow.
# ---------------------------------------------------------------------------------------------

from frappe.model.document import Document


class ComplaintFiberPulling(Document):
	pass
