# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Complaint List Colours (single): the colour of each Status / Operator / Link Status / Link Type /
# Area / EVisions SLA value in the Complaint list (complaint_information_list.js). Values not
# listed stay grey. Defaults come from DEFAULT_COLOURS (patches/complaint_list_colours.py).
#
# Change log
#   2026-11-27  Created (user's request: "give option to add colors, they all look grey").
# ---------------------------------------------------------------------------------------------

import frappe
from frappe import _
from frappe.model.document import Document

CACHE_KEY = "emp_tracking:complaint_list_colours"

# column -> {value: colour}; colours are the list badge themes (Gray, Blue, Green, Orange, Red,
# Violet, Yellow, Cyan, Pink, Light Blue)
DEFAULT_COLOURS = {
	"Status": {"New": "Blue", "NOC Verification": "Cyan", "Assigned to Area Manager": "Violet",
		"Assigned to Maintenance Team": "Violet", "Accepted": "Light Blue", "Rejected": "Red", "In Progress": "Orange",
		"Restoration": "Orange", "Fiber Restored": "Green", "Awaiting Operator Confirmation": "Yellow",
		"Resolved": "Green", "Closed": "Gray"},
	"Operator": {"Airtel": "Red", "Vodafone": "Pink", "Railtel": "Blue", "Jio": "Light Blue", "Gazon": "Cyan",
		"GBPS": "Violet", "Powergrid": "Orange", "Sumashilp": "Yellow", "Hathway": "Green"},
	"Link Status": {"NEED TO ASSIGN": "Red", "ASSIGNED": "Orange", "WIP": "Yellow", "RESTORED": "Green",
		"AUTO RESTORED": "Green", "RESTORED BY AIRTEL TEAM": "Green", "NO FIBER ISSUE": "Cyan", "NOT OUR FIBER": "Cyan",
		"LOW RX ISSUE": "Violet", "POWER ISSUE": "Violet", "ACCESS ISSUE - OUR SIDE": "Orange",
		"ACCESS ISSUE - COMPANY SIDE": "Pink", "CONFIRMATION PENDING": "Yellow", "OTDR WAITED": "Yellow"},
	"Link Type": {"FTTH": "Blue", "Backbone": "Violet", "Small Cell": "Cyan", "ILL": "Orange", "LMC": "Pink"},
	"Area": {"Area 1": "Blue", "Area 2": "Green", "Area 3": "Orange", "Area 4": "Cyan", "Area 5": "Pink", "Area 6": "Violet"},
	"EVisions SLA": {"In": "Green", "Out": "Red"},
}


class ComplaintListColours(Document):
	# Date: 2026-11-27
	def validate(self):
		seen = set()
		for row in self.colours:
			key = (row.column_name, (row.value or "").strip().lower())
			if key in seen:
				frappe.throw(_("Row {0}: {1} '{2}' is listed twice").format(row.idx, row.column_name, row.value))
			seen.add(key)
			row.value = (row.value or "").strip()

	def on_update(self):
		frappe.cache.delete_value(CACHE_KEY)


# Date: 2026-11-27
@frappe.whitelist()
def get_colours():
	"""{column: {value: badge theme}} for the Complaint list, e.g. {"Link Status": {"RESTORED": "green"}}."""
	out = frappe.cache.get_value(CACHE_KEY)
	if out is None:
		out = {}
		for r in frappe.get_all("Complaint List Colour", filters={"parent": "Complaint List Colours"},
				fields=["column_name", "value", "colour"], order_by="idx asc"):
			out.setdefault(r.column_name, {})[r.value] = (r.colour or "Gray").lower().replace(" ", "-")
		frappe.cache.set_value(CACHE_KEY, out)
	return out


def set_defaults():
	"""Fills the table with DEFAULT_COLOURS when it is empty (patch / first use)."""
	doc = frappe.get_single("Complaint List Colours")
	if doc.colours:
		return
	for column, values in DEFAULT_COLOURS.items():
		for value, colour in values.items():
			doc.append("colours", {"column_name": column, "value": value, "colour": colour})
	doc.save(ignore_permissions=True)
