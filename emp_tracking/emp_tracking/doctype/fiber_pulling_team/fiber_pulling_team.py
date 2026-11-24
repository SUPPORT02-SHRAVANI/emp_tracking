# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Fiber Pulling Team: master
#
# How this file works
#   One record per fiber pulling team (FPT), e.g. "Amrut Rathod", optionally under a vendor.
#   Later the FPT's bills and the material issued to it are tracked against this record.
#   No server logic yet.
#
# Change log
#   2026-10-09  Created for the OH Project flow.
#   2026-10-31  New Project (which picked the FPT) was merged into FTTH Work Order; work orders
#               pick their team from FTTH Tracker's Fiber Team. Kept for bills / material.
# ---------------------------------------------------------------------------------------------

from frappe.model.document import Document


class FiberPullingTeam(Document):
	pass
