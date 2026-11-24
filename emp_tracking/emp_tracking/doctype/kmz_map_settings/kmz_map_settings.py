# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# KMZ Map Settings: colours of the KMZ Map page. Created: 2026-10-27.
#
# pin_types (KMZ Pin Type rows): how a KMZ pin is recognised from its name, its colour and
# whether it shows when the map opens. The page takes the first row whose rule fits a pin name,
# so "Everything else" is moved to the end on save. DEFAULT_PIN_TYPES seeds the table
# (patch kmz_map_settings_defaults) and is used by get_map_settings when the table is empty.
#
# Change log
#   2026-10-27  Created.
#   2026-10-27  No GIS Node colour default grey -> fuchsia #c026d3 (grey routes were hard to see).
#   2026-10-27  ODF, Encloser / JC, Pole / Light, Tree, Chamber / HH hidden by default (click in Index to show).
# ---------------------------------------------------------------------------------------------

import re

import frappe
from frappe import _
from frappe.model.document import Document

EVERYTHING_ELSE = "Everything else"
HAS_WORD = "Name has word"

# the types the map used before these settings existed, read from the real KMZ pin names.
# show: 0 = hidden when the map opens (shown by clicking it in the Index); 2026-10-27 only
# Code point and Building show by default, the rest crowded the map
DEFAULT_PIN_TYPES = [
	{"label": "ODF", "match_type": HAS_WORD, "keywords": "odf", "colour": "#0f766e", "show": 0},
	{"label": "Encloser / JC", "match_type": HAS_WORD, "keywords": "encl*, jc, tapping", "colour": "#eab308", "show": 0},
	{"label": "Pole / Light", "match_type": HAS_WORD, "keywords": "pole, light", "colour": "#64748b", "show": 0},
	{"label": "Tree", "match_type": HAS_WORD, "keywords": "tree", "colour": "#22c55e", "show": 0},
	{"label": "Chamber / HH", "match_type": HAS_WORD, "keywords": "hh, chamber, manhole, mh", "colour": "#0ea5e9", "show": 0},
	{"label": "Code point", "match_type": "Short code (e.g. 1PZ21)", "keywords": "", "colour": "#ec4899", "show": 1},
	{"label": "Building", "match_type": EVERYTHING_ELSE, "keywords": "", "colour": "#7c3aed", "show": 1},
]
OTHER_COLOURS = {"down_colour": "#dc2626", "affected_colour": "#f97316", "no_node_colour": "#c026d3"}  # fuchsia (2026-10-27: was grey, hard to see)
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class KMZMapSettings(Document):
	# Date: 2026-10-27
	def validate(self):
		for row in self.pin_types:
			if row.colour and not HEX.match(row.colour):
				frappe.throw(_("Row {0}: colour must look like #1a2b3c").format(row.idx))
			if row.match_type == HAS_WORD and not (row.keywords or "").strip():
				frappe.throw(_("Row {0} ({1}): enter the words to look for in the pin name").format(row.idx, row.label))
		if len([r for r in self.pin_types if r.match_type == EVERYTHING_ELSE]) > 1:
			frappe.throw(_("Only one row can be \"Everything else\""))
		# a catch-all row anywhere but last would hide every row below it
		self.pin_types = [r for r in self.pin_types if r.match_type != EVERYTHING_ELSE] + \
			[r for r in self.pin_types if r.match_type == EVERYTHING_ELSE]
		for i, row in enumerate(self.pin_types, 1):
			row.idx = i


# Date: 2026-10-27
def get_map_settings():
	"""Colours for the KMZ Map page; built-in defaults for anything never saved."""
	doc = frappe.get_cached_doc("KMZ Map Settings")
	rows = [{"label": r.label, "match_type": r.match_type, "keywords": r.keywords or "", "colour": r.colour,
		"show": int(r.show_by_default)} for r in doc.pin_types if r.colour]
	return {
		"pin_types": rows or DEFAULT_PIN_TYPES,
		**{k: doc.get(k) or v for k, v in OTHER_COLOURS.items()},
	}
