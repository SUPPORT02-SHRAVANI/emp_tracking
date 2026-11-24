# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import Case
from frappe.query_builder.functions import Avg, Count, Sum


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data)


def get_columns():
	return [
		{"fieldname": "gis", "label": _("GIS"), "fieldtype": "Link", "options": "GIS Node", "width": 90},
		{"fieldname": "area", "label": _("Area"), "fieldtype": "Data", "width": 160},
		{"fieldname": "work_orders", "label": _("Work Orders"), "fieldtype": "Int", "width": 110},
		{"fieldname": "rfs_done", "label": _("RFS Done"), "fieldtype": "Int", "width": 100},
		{"fieldname": "pending", "label": _("Pending"), "fieldtype": "Int", "width": 90},
		{"fieldname": "home_pass", "label": _("Home Pass"), "fieldtype": "Int", "width": 100},
		{"fieldname": "fiber_m", "label": _("Final Distance (m)"), "fieldtype": "Float", "precision": 0, "width": 140},
		{"fieldname": "shared_m", "label": _("Shared to Airtel (m)"), "fieldtype": "Float", "precision": 0, "width": 150},
		{"fieldname": "avg_days", "label": _("Avg Days to RFS"), "fieldtype": "Float", "precision": 1, "width": 130},
		{"fieldname": "warnings", "label": _("With Warnings"), "fieldtype": "Int", "width": 120},
	]


def get_data(filters):
	wo = frappe.qb.DocType("FTTH Work Order")

	q = (
		frappe.qb.from_(wo)
		.select(
			wo.gis,
			wo.area,
			Count(wo.name).as_("work_orders"),
			Sum(Case().when(wo.status == "RFS Done", 1).else_(0)).as_("rfs_done"),
			Sum(wo.hp).as_("home_pass"),
			Sum(wo.eff_final_distance).as_("fiber_m"),
			Sum(wo.eff_shared_distance).as_("shared_m"),
			Avg(Case().when(wo.days_to_rfs > 0, wo.days_to_rfs)).as_("avg_days"),
			Sum(wo.has_warnings).as_("warnings"),
		)
		.groupby(wo.gis, wo.area)
		.orderby(wo.gis)
	)
	if filters.from_date:
		q = q.where(wo.wo_received_date >= filters.from_date)
	if filters.to_date:
		q = q.where(wo.wo_received_date <= filters.to_date)
	for field in ("ibd_team", "gis", "segment"):
		if filters.get(field):
			q = q.where(wo.field(field) == filters.get(field))
	rows = q.run(as_dict=True)
	for r in rows:
		r.pending = (r.work_orders or 0) - (r.rfs_done or 0)
	return rows


def get_chart(rows):
	if not rows:
		return None
	return {
		"data": {
			"labels": [r.gis for r in rows],
			"datasets": [
				{"name": _("RFS Done"), "values": [r.rfs_done or 0 for r in rows]},
				{"name": _("Pending"), "values": [r.pending or 0 for r in rows]},
			],
		},
		"type": "bar",
		"barOptions": {"stacked": 1},
		"colors": ["#1baf7a", "#eda100"],
	}
