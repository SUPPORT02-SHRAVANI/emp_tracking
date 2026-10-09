# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Node: server code
#
# How this file works
#   A Node is a 3-character GIS code such as D1J. One Node has many Sites.
#   There is no server logic; the site diagram is drawn by node.js.
#
# Change log
#   2026-10-07  Created.
#   2026-10-07  Added this header.
# ---------------------------------------------------------------------------------------------

from frappe.model.document import Document


class Node(Document):
	pass
