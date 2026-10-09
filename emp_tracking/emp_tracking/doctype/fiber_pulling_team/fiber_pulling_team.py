# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Fiber Pulling Team: master
#
# How this file works
#   One record per fiber pulling team (FPT), e.g. "Amrut Rathod", optionally under a vendor.
#   New Project picks the FPT in the Area Manager's Fiber Team section; later the FPT's bills
#   and the material issued to it are tracked against this record. No server logic yet.
#
# Change log
#   2026-10-09  Created for the OH Project flow.
# ---------------------------------------------------------------------------------------------

from frappe.model.document import Document


class FiberPullingTeam(Document):
	pass
