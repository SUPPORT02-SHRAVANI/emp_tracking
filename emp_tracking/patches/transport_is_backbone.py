# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Patch: Transport link type becomes Backbone
#
# How this file works
#   The client counts Transport links as Backbone, so "Transport" was removed from the Link Type
#   lists. Runs once during migrate and changes any saved "Transport" to "Backbone" on
#   New Project, Complaint Information and Network Link. Project Type (ODN / Transport / IBD)
#   is a different field and is not touched.
#
# Change log
#   2026-10-09  Created.
# ---------------------------------------------------------------------------------------------

import frappe

# doctype -> link type field
LINK_TYPE_FIELDS = {
	"New Project": "link_type",
	"Complaint Information": "complaint_type",
	"Network Link": "network_type",
}


# Date: 2026-10-09
def execute():
	"""Replace the link type "Transport" with "Backbone" wherever it was saved.

	A Backbone Network Link needs a Section, so a Transport link without one gets its
	Society / Building or Location as the Section first.
	"""
	if frappe.db.has_column("Network Link", "section"):
		frappe.db.sql(
			"""update `tabNetwork Link`
			set section = coalesce(nullif(society_building, ''), nullif(location, ''), name)
			where network_type = 'Transport' and ifnull(section, '') = ''"""
		)
	for doctype, field in LINK_TYPE_FIELDS.items():
		if frappe.db.has_column(doctype, field):
			frappe.db.sql(
				f"update `tab{doctype}` set `{field}` = 'Backbone' where `{field}` = 'Transport'"  # nosemgrep: fixed names
			)
