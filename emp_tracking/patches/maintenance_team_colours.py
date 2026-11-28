# ---------------------------------------------------------------------------------------------
# Patch: Maintenance Team colours (2026-11-28, user: "add team color option"). TEAM 1-6 get the
# colour of their team area's boundary (evision_team_areas.json: Area 1 blue ... Area 6 violet);
# a colour already set is kept. The hidden leader name is refreshed from the leader Employee
# (one leader field now). Safe to run again.
# ---------------------------------------------------------------------------------------------

import json
import os

import frappe


def execute():
	frappe.reload_doc("emp_tracking", "doctype", "maintenance_team")
	with open(os.path.join(os.path.dirname(__file__), "evision_team_areas.json"), encoding="utf8") as f:
		areas = json.load(f)["areas"]
	for name, a in areas.items():
		team = frappe.db.get_value("Maintenance Team", {"team_name": a["team"]}, ["name", "team_colour"], as_dict=True)
		if team and not team.team_colour:
			frappe.db.set_value("Maintenance Team", team.name, "team_colour", a["colour"], update_modified=False)
	for t in frappe.get_all("Maintenance Team", fields=["name", "team_leader"]):
		name = frappe.db.get_value("Employee", t.team_leader, "employee_name") if t.team_leader else None
		frappe.db.set_value("Maintenance Team", t.name, "team_leader_name", name, update_modified=False)
	frappe.db.commit()
