# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Fills KMZ Map Settings with the pin types and colours the KMZ Map used before the settings
# existed, so the map looks the same until someone changes them. Only fills an empty table /
# empty colours, so it never overwrites what a user saved. Safe to run again.
#
# Change log
#   2026-10-27  Created.
#   2026-10-27  Seeds Show from DEFAULT_PIN_TYPES (most types hidden by default).
# ---------------------------------------------------------------------------------------------

import frappe

from emp_tracking.emp_tracking.doctype.kmz_map_settings.kmz_map_settings import DEFAULT_PIN_TYPES, OTHER_COLOURS


def execute():
	frappe.reload_doc("emp_tracking", "doctype", "kmz_pin_type")
	frappe.reload_doc("emp_tracking", "doctype", "kmz_map_settings")
	doc = frappe.get_single("KMZ Map Settings")
	changed = False
	if not doc.pin_types:
		for row in DEFAULT_PIN_TYPES:
			doc.append("pin_types", {**{k: v for k, v in row.items() if k != "show"}, "show_by_default": row["show"]})
		changed = True
	for field, colour in OTHER_COLOURS.items():
		if not doc.get(field):
			doc.set(field, colour)
			changed = True
	if changed:
		doc.save(ignore_permissions=True)
