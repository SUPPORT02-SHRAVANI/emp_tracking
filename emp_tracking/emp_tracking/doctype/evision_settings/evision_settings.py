# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# EVision Settings (single): business rules that used to be fixed in the code, so the client can
# change them without a developer (user's request 2026-11-27: "give settings for each thing so
# nothing is hard coded"). Read with setting("sla_hours"); an empty field falls back to DEFAULTS
# (the values the code used before). Saving also puts the office hours on the office Shift Type.
#
# Change log
#   2026-11-27  Created.
#   2026-11-28  Day / night call times shown as 12-hour IST ("8:00 AM"), user: "show indian timing".
#   2026-11-28  Editable formulas (FORMULAS, formula(), sla_pct()): SLA In, In SLA %, Pending now,
#               office Present-from / Absent-under hours, In field %; checked on save, field names
#               listed beside each (user: "give option to change formula and suggest field names").
#   2026-11-28  Map Index settings (MAP_INDEX, get_map_index): position, open / folded, and per row
#               show / label / colour for the KMZ Map and the NOC map (user: "add option to set index on map").
# ---------------------------------------------------------------------------------------------

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

DEFAULTS = {
	"sla_hours": 4,
	"own_fiber_rfo": "Own Fiber Issue",
	"outage_days_per_month": 2,
	"day_start_hour": 8,
	"night_start_hour": 20,
	"office_full_day_hours": 9,
	"office_grace_minutes": 15,
	"location_radius_m": 200,
	"max_ping_gap_minutes": 15,
	"kmz_route_limit": 4000,
	"kmz_point_limit": 8000,
	"kmz_polygon_limit": 1500,
	"noc_map_limit": 5000,
	"noc_route_limit": 400,
}
ZERO_ALLOWED = {"office_grace_minutes"}  # 0 = no grace; for the rest 0 = empty = default
HOUR_FIELDS = {"day_start_hour", "night_start_hour"}  # saved as "8:00 AM" (IST), read as hour 0-23


# Date: 2026-11-28
def to_hour(value):
	"""'8:00 AM' -> 8, '8:00 PM' -> 20, '12:00 AM' -> 0; a plain number ('8', 20) is taken as is."""
	text = str(value or "").strip().upper()
	if text.endswith(("AM", "PM")):
		hour = cint(text.split(":")[0]) % 12
		return hour + 12 if text.endswith("PM") else hour
	return cint(text)


def to_label(hour):
	"""20 -> '8:00 PM' (the Select's option)."""
	hour = cint(hour) % 24
	return f"{(hour % 12) or 12}:00 {'AM' if hour < 12 else 'PM'}"


# Date: 2026-11-27
def setting(field):
	"""The saved value, else the default. Numbers keep the default's type (int / float)."""
	default = DEFAULTS[field]
	try:
		value = frappe.get_cached_doc("EVision Settings").get(field)
	except Exception:
		# before the migrate that creates the doctype
		return default
	if field in HOUR_FIELDS:
		return to_hour(value) if value not in (None, "") else default
	# an empty number field is saved as 0, so 0 means "default", except where 0 is a real choice
	if value in (None, "") or (value == 0 and field not in ZERO_ALLOWED):
		return default
	if isinstance(default, float):
		return flt(value)
	if isinstance(default, int):
		return cint(value)
	return value


# ---- editable formulas (2026-11-28, user: "give option to change formula and suggest field names") --
# key -> (label, field names the formula may use, default formula, sample values used to check it)
FORMULAS = {
	"sla_in": ("SLA In when", ("restore_hours", "sla_hours"), "restore_hours <= sla_hours",
		{"restore_hours": 3.5, "sla_hours": 4}),
	"in_sla_pct": ("In SLA %", ("in_sla", "out_sla"), "in_sla / (in_sla + out_sla) * 100", {"in_sla": 3, "out_sla": 1}),
	"pending_now": ("Pending now", ("opening", "received", "closed"), "max(0, opening + received - closed)",
		{"opening": 2, "received": 5, "closed": 4}),
	"present_from_hours": ("Office: Present from (hours)", ("full_day_hours", "grace_minutes"),
		"full_day_hours - grace_minutes / 60", {"full_day_hours": 9, "grace_minutes": 15}),
	"absent_under_hours": ("Office: Absent under (hours)", ("full_day_hours", "grace_minutes"), "full_day_hours / 2",
		{"full_day_hours": 9, "grace_minutes": 15}),
	"in_field_pct": ("In field %", ("field_hours", "home_hours", "office_hours", "other_hours", "tracked_hours"),
		"field_hours / tracked_hours * 100",
		{"field_hours": 5, "home_hours": 1, "office_hours": 1, "other_hours": 1, "tracked_hours": 8}),
}
FUNCTIONS = {"max": max, "min": min, "round": round, "abs": abs}


def check_formula(key, expr):
	"""Raises with a plain message when the formula uses an unknown name or anything but simple
	maths; returns its result on the sample values."""
	import ast

	from frappe.utils.safe_exec import safe_eval

	label, names, _default, sample = FORMULAS[key]
	try:
		tree = ast.parse(expr, mode="eval")
	except SyntaxError:
		frappe.throw(_("{0}: the formula is not complete or has a typo: {1}").format(label, expr))
	allowed_nodes = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp, ast.Call, ast.Name,
		ast.Load, ast.Constant, ast.operator, ast.unaryop, ast.boolop, ast.cmpop)
	for node in ast.walk(tree):
		if not isinstance(node, allowed_nodes):
			frappe.throw(_("{0}: only numbers, field names, + - * / ( ), comparisons, and / or and max() min() round() abs() can be used.").format(label))
		if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS):
			frappe.throw(_("{0}: only max(), min(), round() and abs() can be called.").format(label))
		if isinstance(node, ast.Name) and node.id not in names and node.id not in FUNCTIONS:
			frappe.throw(_("{0}: '{1}' is not a field name. Use: {2}").format(label, node.id, ", ".join(names)))
	try:
		return safe_eval(expr, dict(FUNCTIONS), dict(sample))
	except ZeroDivisionError:
		return None
	except Exception as e:
		frappe.throw(_("{0}: the formula does not work: {1}").format(label, e))


def _compiled(expr):
	"""Frappe's restricted compile of a formula, once per text (reports run one formula per row)."""
	from frappe.utils.safe_exec import WHITELISTED_SAFE_EVAL_GLOBALS, _compile_code

	# keyed by the formula text only, so one cache serves every site in the process
	if expr not in _CODE:
		_CODE[expr] = _compile_code(expr, filename="<safe_eval>", mode="eval")
	return _CODE[expr], {"__builtins__": {}, **WHITELISTED_SAFE_EVAL_GLOBALS, **FUNCTIONS}


_CODE = {}  # formula text -> compiled code


# Date: 2026-11-28
def formula(key, **values):
	"""The formula's result for these values (the saved formula, else the default). Dividing by
	zero gives None (e.g. In SLA % with nothing closed); a formula that fails falls back to the default.
	Saved formulas were checked on save (check_formula): only field names, numbers and simple maths."""
	default = FORMULAS[key][2]
	try:
		rows = {r.formula_key: r.formula for r in frappe.get_cached_doc("EVision Settings").get("formula_table") or []}
	except Exception:
		rows = {}
	expr = (rows.get(key) or "").strip() or default
	for attempt in (expr, default):
		try:
			code, env = _compiled(attempt)
			return eval(code, env, dict(values))
		except ZeroDivisionError:
			return None
		except Exception:
			if attempt == default:
				raise
			frappe.log_error(title=f"EVision formula {key} failed, default used")
	return None


def sla_pct(in_sla, out_sla, digits=1):
	"""In SLA % through the editable formula, rounded; None when nothing was closed."""
	if not (in_sla or out_sla):
		return None
	value = formula("in_sla_pct", in_sla=in_sla, out_sla=out_sla)
	return None if value is None else round(flt(value), digits)


# ---- map Index (legend) rows (2026-11-28, user: "add option to set index on map") ------------
# (map, key, default label, default colour or None = the row has no colour of its own)
MAP_INDEX = [
	("KMZ Map", "pins", "Pins (click to hide)", None),
	("KMZ Map", "route_node", "Route, coloured by GIS Node", None),
	("KMZ Map", "route_none", "Route with no GIS Node (dashed)", "#c026d3"),
	("KMZ Map", "node_pin", "Node pin (labelled with GIS code)", None),
	("KMZ Map", "shapes", "Shape (area / DSA / cluster boundary)", None),
	("KMZ Map", "open_complaint", "Open complaint", None),
	("KMZ Map", "node_faults", "Node with open complaints", None),
	("KMZ Map", "down", "Down: site with an open complaint", "#dc2626"),
	("KMZ Map", "affected", "Affected: fed through a down site", "#f97316"),
	("NOC Map", "open", "Open complaint", "#d97706"),
	("NOC Map", "overdue", "Open over the SLA hours", "#dc2626"),
	("NOC Map", "closed_sla", "Closed within SLA", "#15803d"),
	("NOC Map", "closed_late", "Closed late", "#94a3b8"),
	("NOC Map", "ring", "Pulsing ring: still open", None),
	("NOC Map", "badge", "Badge: how long it has been open", None),
	("NOC Map", "own_route", "Fibre route to the complaint's building", "#2563eb"),
	("NOC Map", "other_route", "Other fibre routes of its node", "#7c3aed"),
	("NOC Map", "building", "Building (KMZ pin)", "#06b6d4"),
	("NOC Map", "own_building", "The complaint's building", "#2563eb"),
	("NOC Map", "encloser", "Encloser / JC", "#eab308"),
	("NOC Map", "hover", "Hover a building or violet route: its routes light up", None),
]


# Date: 2026-11-28
@frappe.whitelist()
def get_map_index(map_name):
	"""Index settings of one map for the page: position, open / folded, and per row key its
	label, colour (None = draw as before) and whether it is shown."""
	try:
		doc = frappe.get_cached_doc("EVision Settings")
	except Exception:
		doc = frappe._dict()
	prefix = "kmz" if map_name == "KMZ Map" else "noc"
	saved = {r.row_key: r for r in doc.get("map_index_rows") or [] if r.map_name == map_name}
	rows = {}
	for m, key, label, colour in MAP_INDEX:
		if m != map_name:
			continue
		r = saved.get(key)
		# "colour" only when changed from the default: otherwise the map keeps its own colour (KMZ Map
		# Settings, or the NOC theme colours that differ in dark mode)
		own = r.colour if r and r.colour and (r.colour or "").lower() != (colour or "").lower() else None
		rows[key] = {"label": _((r.label if r and r.label else label)), "colour": own, "show": cint(r.show) if r else 1}
	return {"position": doc.get(f"{prefix}_index_position") or ("Bottom right" if prefix == "kmz" else "Bottom left"),
		"start": doc.get(f"{prefix}_index_start") or "Open", "rows": rows}


class EVisionSettings(Document):
	# Date: 2026-11-28
	def sync_index_rows(self):
		"""One Index row per map line (added when missing, unknown ones dropped), in MAP_INDEX order;
		an empty label goes back to the default."""
		keys = {(m, k) for m, k, _l, _c in MAP_INDEX}
		have = {(r.map_name, r.row_key): r for r in self.get("map_index_rows") or [] if (r.map_name, r.row_key) in keys}
		rows = []
		for m, key, label, colour in MAP_INDEX:
			r = have.get((m, key))
			if not r:
				r = frappe._dict(map_name=m, row_key=key, show=1, label=label, colour=colour)
			r.default_label, r.default_colour = label, colour or ""
			r.label = (r.label or "").strip() or label
			rows.append(r)
		self.set("map_index_rows", [])
		for r in rows:
			self.append("map_index_rows", {k: r.get(k) for k in ("map_name", "row_key", "show", "label", "colour",
				"default_label", "default_colour")})

	# Date: 2026-11-28
	def sync_formulas(self):
		"""One row per formula (added when missing), with its allowed names and default; an empty
		formula goes back to the default; each formula is checked on sample values."""
		# rows that are not one of FORMULAS (e.g. added by hand) are dropped
		self.set("formula_table", [r for r in self.get("formula_table") or [] if r.formula_key in FORMULAS])
		have = {r.formula_key: r for r in self.formula_table}
		for key, (label, names, default, _sample) in FORMULAS.items():
			row = have.get(key) or self.append("formula_table", {"formula_key": key})
			row.label, row.fields, row.default_formula = label, ", ".join(names), default
			row.formula = (row.formula or "").strip() or default
			check_formula(key, row.formula)

	# Date: 2026-11-27
	def validate(self):
		self.sync_formulas()
		self.sync_index_rows()
		# 2026-11-28: the two call times are 12-hour IST labels; an old plain hour becomes its label
		for f in HOUR_FIELDS:
			if self.get(f) not in (None, ""):
				self.set(f, to_label(to_hour(self.get(f))))
		day, night = to_hour(self.day_start_hour or "8:00 AM"), to_hour(self.night_start_hour or "8:00 PM")
		if day >= night:
			frappe.throw(_("Day calls must start before night calls."))
		full = flt(self.office_full_day_hours or 9)
		if not 1 <= full <= 16:
			frappe.throw(_("Office full day must be between 1 and 16 hours."))
		if cint(self.office_grace_minutes) >= full * 60 / 2:
			frappe.throw(_("Grace must be less than half the full day."))

	def on_update(self):
		self.apply_office_shift()

	def apply_office_shift(self):
		"""The office Shift Type's thresholds follow these settings: Present from full day less grace,
		Absent under half the full day (HRMS marks attendance with them)."""
		from emp_tracking.app_attendance import OFFICE_SHIFT

		if not frappe.db.exists("Shift Type", OFFICE_SHIFT):
			return
		full = flt(self.office_full_day_hours or DEFAULTS["office_full_day_hours"])
		grace = cint(self.office_grace_minutes if self.office_grace_minutes is not None else DEFAULTS["office_grace_minutes"])
		shift = frappe.get_doc("Shift Type", OFFICE_SHIFT)
		# 2026-11-28: through the editable formulas (this doc's own rows, as the cache may be old)
		rows = {r.formula_key: r.formula for r in self.formula_table}
		from frappe.utils.safe_exec import safe_eval

		values = {"full_day_hours": full, "grace_minutes": grace}
		present = flt(safe_eval(rows.get("present_from_hours") or FORMULAS["present_from_hours"][2], dict(FUNCTIONS), dict(values)))
		absent = flt(safe_eval(rows.get("absent_under_hours") or FORMULAS["absent_under_hours"][2], dict(FUNCTIONS), dict(values)))
		if not 0 < absent <= present <= 24:
			frappe.throw(_("Office: Absent-under ({0} h) must be above 0 and not more than Present-from ({1} h).").format(
				round(absent, 2), round(present, 2)))
		shift.working_hours_threshold_for_half_day = round(present, 2)
		shift.working_hours_threshold_for_absent = round(absent, 2)
		shift.save(ignore_permissions=True)
