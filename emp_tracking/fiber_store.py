# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Fiber Store: cable drum register (inward / outward) on ERPNext's own stock features
#
# How it is built (no new doctypes, upgrade-safe):
#   - Each fiber type (6F / 12F / 24F / 48F / 96F) is an Item in metres, with batches on:
#     every DRUM is a Batch named "<type>-<Cable ID>" (e.g. "24F-31593").
#   - Accessories (closure, sleeves, rope, power meter, cleaver, IPA) are plain Items.
#   - INWARD  = Stock Entry "Material Receipt" into the "Fiber Store" warehouse; the party is the
#               standard Supplier field.
#   - OUTWARD = Stock Entry "Material Issue" from the Fiber Store; the job (Link ID, project or
#               maintenance, A / B end, area, team, client, issued to, vendor bill) is kept in
#               Custom Fields on Stock Entry, the drum meter readings on Stock Entry Detail.
#   - The visual is a standard Frappe Dashboard "Fiber Store" (/app/dashboard-view/Fiber Store)
#     made of Number Cards and Dashboard Charts on those fields; drum balances come from the
#     standard "Batch-Wise Balance History" and "Stock Balance" reports.
#   setup() creates all of the above and is safe to run again (after_migrate).
#   stock_entry_validate() (doc_events) fills the totals the dashboard reads.
#
# Change log
#   2026-10-26  Created.
# ---------------------------------------------------------------------------------------------

import json

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt

CABLE_GROUP = "Fiber Cable"
ACCESSORY_GROUP = "Fiber Accessories"
WAREHOUSE = "Fiber Store"
DASHBOARD = "Fiber Store"
MODULE = "Emp Tracking"

# Sheet "Cable Type" -> (item code, item name, stock UOM, is a drum / batch item)
ITEMS = {
	"6F": ("FIBER-6F", "Fiber Cable 6F", "Meter", True),
	"12F": ("FIBER-12F", "Fiber Cable 12F", "Meter", True),
	"24F": ("FIBER-24F", "Fiber Cable 24F", "Meter", True),
	"48F": ("FIBER-48F", "Fiber Cable 48F", "Meter", True),
	"96F": ("FIBER-96F", "Fiber Cable 96F", "Meter", True),
	"CLOUSER": ("FIBER-CLOSURE", "Fiber Closure", "Nos", False),
	"SLEEVES": ("FIBER-SLEEVE", "Splice Sleeve", "Nos", False),
	"ROPE": ("FIBER-ROPE", "Rope", "Meter", False),
	"POWER METER": ("OPTICAL-POWER-METER", "Optical Power Meter", "Nos", False),
	"CLEAVER": ("FIBER-CLEAVER", "Fiber Cleaver", "Nos", False),
	"IP": ("IPA-LIQUID", "IPA Cleaning Liquid", "Litre", False),
}

CUSTOM_FIELDS = {
	"Stock Entry": [
		{"fieldname": "custom_fiber_section", "label": "Fiber Job Details", "fieldtype": "Section Break",
			"insert_after": "get_stock_and_rate", "collapsible": 0,
			"depends_on": "eval:doc.custom_fiber_direction"},
		{"fieldname": "custom_fiber_direction", "label": "Fiber Register", "fieldtype": "Select",
			"options": "\nInward\nOutward\nOpening", "insert_after": "custom_fiber_section",
			"in_standard_filter": 1, "in_list_view": 1,
			"description": "Inward: cable received into the Fiber Store. Outward: cable issued for a job. "
				"Opening: balance on drums already in hand when the register started."},
		{"fieldname": "custom_work_type", "label": "Project / Maintenance", "fieldtype": "Select",
			"options": "\nProject\nMaintenance", "insert_after": "custom_fiber_direction", "in_standard_filter": 1},
		{"fieldname": "custom_link_id", "label": "Link ID", "fieldtype": "Data", "insert_after": "custom_work_type",
			"in_standard_filter": 1},
		{"fieldname": "custom_client", "label": "Company (Client)", "fieldtype": "Data", "insert_after": "custom_link_id"},
		{"fieldname": "custom_fiber_col1", "fieldtype": "Column Break", "insert_after": "custom_client"},
		{"fieldname": "custom_a_end", "label": "A End", "fieldtype": "Data", "insert_after": "custom_fiber_col1"},
		{"fieldname": "custom_b_end", "label": "B End", "fieldtype": "Data", "insert_after": "custom_a_end"},
		{"fieldname": "custom_area", "label": "Area", "fieldtype": "Data", "insert_after": "custom_b_end",
			"in_standard_filter": 1},
		{"fieldname": "custom_fiber_col2", "fieldtype": "Column Break", "insert_after": "custom_area"},
		{"fieldname": "custom_team", "label": "Team", "fieldtype": "Data", "insert_after": "custom_fiber_col2",
			"in_standard_filter": 1},
		{"fieldname": "custom_issued_to", "label": "Issued To", "fieldtype": "Data", "insert_after": "custom_team",
			"description": "Supervisor or vendor who took the cable"},
		{"fieldname": "custom_issued_to_type", "label": "Own / Vendor", "fieldtype": "Select",
			"options": "\nOwn\nVendor", "insert_after": "custom_issued_to"},
		{"fieldname": "custom_vendor_bill", "label": "Vendor Bill", "fieldtype": "Data",
			"insert_after": "custom_issued_to_type"},
		{"fieldname": "custom_cable_m", "label": "Fiber Cable (m)", "fieldtype": "Float", "precision": "0",
			"read_only": 1, "insert_after": "custom_vendor_bill", "in_list_view": 1,
			"description": "Total metres of fiber cable in this entry (filled on save)"},
		{"fieldname": "custom_sheet_ref", "label": "Sheet Reference", "fieldtype": "Data", "read_only": 1,
			"insert_after": "custom_cable_m", "description": "Row of the imported Excel register, if any"},
	],
	"Stock Entry Detail": [
		{"fieldname": "custom_start_reading", "label": "Start Reading (m)", "fieldtype": "Float", "precision": "0",
			"insert_after": "qty", "description": "Meter marking on the drum before cutting"},
		{"fieldname": "custom_end_reading", "label": "End Reading (m)", "fieldtype": "Float", "precision": "0",
			"insert_after": "custom_start_reading", "description": "Meter marking left on the drum after cutting"},
	],
}


# Date: 2026-10-26
def after_migrate():
	"""Keeps the Fiber Store set up on every migrate; a problem here must never fail a deploy."""
	try:
		setup()
	except Exception:
		frappe.log_error(title="emp_tracking: Fiber Store setup after migrate failed")


# Date: 2026-10-26
def setup():
	if not frappe.db.exists("DocType", "Stock Entry"):
		return  # ERPNext not installed on this site
	company = default_company()
	if not company:
		return
	create_custom_fields(CUSTOM_FIELDS, update=True)
	enable_batches()
	make_item_groups()
	make_items()
	warehouse(company)
	make_dashboard()


# Date: 2026-10-26
def default_company():
	return frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")


# Date: 2026-10-26
def warehouse(company):
	"""The 'Fiber Store - <abbr>' warehouse under the company's warehouse group (created once)."""
	abbr = frappe.get_cached_value("Company", company, "abbr")
	name = f"{WAREHOUSE} - {abbr}"
	if not frappe.db.exists("Warehouse", name):
		parent = frappe.db.get_value("Warehouse", {"company": company, "is_group": 1, "parent_warehouse": ["in", ("", None)]})
		frappe.get_doc({"doctype": "Warehouse", "warehouse_name": WAREHOUSE, "company": company,
			"parent_warehouse": parent}).insert(ignore_permissions=True)
	return name


# Date: 2026-10-26
def enable_batches():
	"""Standard Stock Settings a drum-as-batch register needs; only switched on, never off."""
	for field in ("enable_serial_and_batch_no_for_item", "use_serial_batch_fields"):
		if not frappe.db.get_single_value("Stock Settings", field):
			frappe.db.set_single_value("Stock Settings", field, 1)


# Date: 2026-10-26
def make_item_groups():
	for group in (CABLE_GROUP, ACCESSORY_GROUP):
		if not frappe.db.exists("Item Group", group):
			frappe.get_doc({"doctype": "Item Group", "item_group_name": group,
				"parent_item_group": "All Item Groups"}).insert(ignore_permissions=True)


# Date: 2026-10-26
def make_items():
	for code, name, uom, is_drum in ITEMS.values():
		if frappe.db.exists("Item", code):
			continue
		frappe.get_doc({
			"doctype": "Item", "item_code": code, "item_name": name, "stock_uom": uom,
			"item_group": CABLE_GROUP if is_drum else ACCESSORY_GROUP,
			"is_stock_item": 1, "include_item_in_manufacturing": 0,
			# a drum is a batch: its Cable ID is typed in, never generated
			"has_batch_no": 1 if is_drum else 0, "create_new_batch": 0,
		}).insert(ignore_permissions=True)


# Date: 2026-10-26
def item_for(cable_type):
	"""Sheet cable type ('24F', '12f', 'clouser', 'Power Meter') -> ITEMS entry, or None."""
	return ITEMS.get((cable_type or "").strip().upper())


# Date: 2026-10-26
def stock_entry_validate(doc, method=None):
	"""doc_events: checks the drum readings and fills custom_cable_m / custom_fiber_direction.

	Only touches entries that carry fiber items, so all other stock entries are left alone.
	"""
	metres, has_fiber = 0.0, False
	for row in doc.items:
		start, end = flt(row.get("custom_start_reading")), flt(row.get("custom_end_reading"))
		if (start or end) and end > start:
			frappe.throw(_("Row {0}: End Reading ({1}) cannot be more than Start Reading ({2}); "
				"the reading is what is left on the drum.").format(row.idx, end, start))
		group = frappe.get_cached_value("Item", row.item_code, "item_group") if row.item_code else None
		if group in (CABLE_GROUP, ACCESSORY_GROUP):
			has_fiber = True
		if group == CABLE_GROUP:
			metres += flt(row.transfer_qty or row.qty)
	if not has_fiber:
		return
	doc.custom_cable_m = metres
	if not doc.custom_fiber_direction:
		doc.custom_fiber_direction = {"Material Receipt": "Inward", "Material Issue": "Outward"}.get(doc.purpose)


# ---------------------------------------------------------------------------------------------
# Dashboard: standard Number Cards + Dashboard Charts, grouped in the Dashboard "Fiber Store"
# ---------------------------------------------------------------------------------------------

def _filters(direction, **extra):
	rows = [["Stock Entry", "docstatus", "=", 1, False],
		["Stock Entry", "custom_fiber_direction", "=", direction, False]]
	for field, value in extra.items():
		rows.append(["Stock Entry", field, "=", value, False])
	return json.dumps(rows)


CARDS = [
	# (label, filters, color, function)
	("Fiber Issued (m)", _filters("Outward"), "#2563eb"),
	("Maintenance Cable (m)", _filters("Outward", custom_work_type="Maintenance"), "#ea580c"),
	("Project Cable (m)", _filters("Outward", custom_work_type="Project"), "#16a34a"),
	("Fiber Received (m)", _filters("Inward"), "#9333ea"),
]

CHARTS = [
	# time series: metres per month
	{"chart_name": "Fiber Issued per Month", "chart_type": "Sum", "type": "Bar", "color": "#2563eb",
		"filters_json": _filters("Outward"), "width": "Full"},
	{"chart_name": "Maintenance Cable per Month", "chart_type": "Sum", "type": "Line", "color": "#ea580c",
		"filters_json": _filters("Outward", custom_work_type="Maintenance"), "width": "Half"},
	{"chart_name": "Project Cable per Month", "chart_type": "Sum", "type": "Line", "color": "#16a34a",
		"filters_json": _filters("Outward", custom_work_type="Project"), "width": "Half"},
	# group by: metres per team / client / person / area
	{"chart_name": "Fiber Used by Team", "chart_type": "Group By", "type": "Bar",
		"group_by_based_on": "custom_team", "number_of_groups": 12, "filters_json": _filters("Outward"), "width": "Half"},
	{"chart_name": "Project vs Maintenance Cable", "chart_type": "Group By", "type": "Pie",
		"group_by_based_on": "custom_work_type", "number_of_groups": 3, "filters_json": _filters("Outward"), "width": "Half"},
	{"chart_name": "Fiber Used by Client", "chart_type": "Group By", "type": "Donut",
		"group_by_based_on": "custom_client", "number_of_groups": 8, "filters_json": _filters("Outward"), "width": "Half"},
	{"chart_name": "Fiber Issued To", "chart_type": "Group By", "type": "Bar",
		"group_by_based_on": "custom_issued_to", "number_of_groups": 12, "filters_json": _filters("Outward"), "width": "Half"},
	{"chart_name": "Top Areas by Fiber Used", "chart_type": "Group By", "type": "Bar",
		"group_by_based_on": "custom_area", "number_of_groups": 15, "filters_json": _filters("Outward"), "width": "Full"},
	{"chart_name": "Fiber Received per Month", "chart_type": "Sum", "type": "Bar", "color": "#9333ea",
		"filters_json": _filters("Inward"), "width": "Full"},
]


# Date: 2026-10-26
def make_dashboard():
	"""Creates / refreshes the cards, charts and the Dashboard that shows them (idempotent)."""
	for label, filters, color in CARDS:
		card = frappe.get_doc("Number Card", label) if frappe.db.exists("Number Card", label) else frappe.new_doc("Number Card")
		card.update({"label": label, "type": "Document Type", "document_type": "Stock Entry",
			"function": "Sum", "aggregate_function_based_on": "custom_cable_m", "filters_json": filters,
			"is_public": 1, "show_percentage_stats": 0, "color": color, "module": MODULE})
		card.save(ignore_permissions=True)

	for spec in CHARTS:
		name = spec["chart_name"]
		chart = frappe.get_doc("Dashboard Chart", name) if frappe.db.exists("Dashboard Chart", name) else frappe.new_doc("Dashboard Chart")
		values = {"document_type": "Stock Entry", "is_public": 1, "module": MODULE, "timeseries": 0}
		values.update({k: v for k, v in spec.items() if k != "width"})
		if spec["chart_type"] == "Group By":
			values.update({"group_by_type": "Sum", "aggregate_function_based_on": "custom_cable_m"})
		else:
			values.update({"based_on": "posting_date", "value_based_on": "custom_cable_m", "timeseries": 1,
				"time_interval": "Monthly", "timespan": "Last Year"})
		chart.update(values)
		chart.save(ignore_permissions=True)

	dash = frappe.get_doc("Dashboard", DASHBOARD) if frappe.db.exists("Dashboard", DASHBOARD) else frappe.new_doc("Dashboard")
	dash.dashboard_name = DASHBOARD
	dash.module = MODULE
	dash.set("cards", [{"card": label} for label, _f, _c in CARDS])
	dash.set("charts", [{"chart": spec["chart_name"], "width": spec["width"]} for spec in CHARTS])
	dash.save(ignore_permissions=True)
