# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Site: server code
#
# How this file works
#   A Site is one society/building on a Node, with its ETIPL code, B Location, vendor and month.
#   There is no server logic; sites are picked on a complaint and drawn in the Node diagram.
#
# Change log
#   2026-10-07  Created.
#   2026-10-07  Added this header.
# ---------------------------------------------------------------------------------------------

from frappe.model.document import Document


class Site(Document):
	pass
