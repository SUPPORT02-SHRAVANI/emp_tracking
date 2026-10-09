# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Patch: OH Project masters
#
# How this file works
#   Runs once during `bench migrate` and loads the masters from the client's OH Project sheet:
#     1. Customers: Airtel, VIL, Gazon, Railtel, GBPS, Powergrid, Jio, Sumashilp, Hathway.
#     2. EVisions teams Team 1-6 (Maintenance Team) with team leader / supervisor and manager.
#     3. The 34 vendors (Maintenance Vendor).
#     4. Fiber Pulling Teams: Amrut, Harilal and Prakash Rathod.
#     5. Recalculates the Stage / Site Status / Link ID of every New Project, because the stages
#        after RFS changed ("RFS Done" became AT & HOTO -> Billing -> Closed).
#   Only missing records are created; existing ones are left as they are.
#
# Change log
#   2026-10-09  Created.
#   2026-10-09  refresh_projects writes 0, not NULL, into number columns (migrate failed on
#               "Column 'distance_difference' cannot be null").
# ---------------------------------------------------------------------------------------------

import frappe

CUSTOMERS = ["Airtel", "VIL", "Gazon", "Railtel", "GBPS", "Powergrid", "Jio", "Sumashilp", "Hathway"]

# Team name -> (team leader / supervisor, manager), from the sheet's "Team / Vendor Name" table.
TEAMS = {
	"Team 1": ("Rahul Dilliwala", "Shyam Morale"),
	"Team 2": ("Sanket Kandhare", "Amol Jagadale"),
	"Team 3": ("Amar Belapurkar", None),
	"Team 4": ("Akash Pardeshi", None),
	"Team 5": ("Sachin Khude", None),
	"Team 6": (None, None),
}

VENDORS = [
	"Swarad Connect", "Anil Enterprises", "Anjali Communication", "AS Communication", "Ashfaque Shaikh",
	"BS Tel Digital Solution", "Dream Cable", "G V Enterprises", "Goodlink Communication", "Goodwill Enterprises",
	"Harshad More", "Hashtag Services", "Hyperband Infra and Technologies", "ICC Broadband", "J R Communication",
	"Jay Ganesh Enterprises", "Manjara Network", "Om Enterprises", "Prasad Cable Network", "Pruthvi Enterprises",
	"Purple Enterprises", "Ramchandra Tukaram Bodke", "Reliable Systems & Network Services", "Sanavi Network",
	"Shafiq Salim Shaikh", "Shaurya Network", "Shital Enterprises", "Shiv Enterprises",
	"Shree Swami Samarth Net Services", "Shrinath Enterprises", "Skyline Technology", "Spine Teleinfra Pvt. Ltd.",
	"Star Entertainment", "Tushar Broadband & Digital Cable Services",
]

FIBER_PULLING_TEAMS = ["Amrut Rathod", "Harilal Rathod", "Prakash Rathod"]


# Date: 2026-10-09
def execute():
	"""Create the missing masters, then refresh every New Project's calculated fields."""
	frappe.reload_doc("emp_tracking", "doctype", "fiber_pulling_team")
	frappe.reload_doc("emp_tracking", "doctype", "maintenance_team")
	frappe.reload_doc("emp_tracking", "doctype", "new_project")
	make_customers()
	make_teams()
	make_vendors()
	make_fiber_pulling_teams()
	refresh_projects()


# Date: 2026-10-09
def make_customers():
	"""Customers from the sheet's company list; skipped if a customer with that name (or containing it) exists."""
	if not frappe.db.exists("DocType", "Customer"):
		return
	group = frappe.db.get_single_value("Selling Settings", "customer_group") or first("Customer Group", {"is_group": 0})
	territory = frappe.db.get_single_value("Selling Settings", "territory") or first("Territory", {"is_group": 0})
	for name in CUSTOMERS:
		if frappe.db.exists("Customer", {"customer_name": ["like", f"%{name}%"]}):
			continue
		frappe.get_doc({
			"doctype": "Customer",
			"customer_name": name,
			"customer_type": "Company",
			"customer_group": group,
			"territory": territory,
		}).insert(ignore_permissions=True, ignore_mandatory=True)


# Date: 2026-10-09
def first(doctype, filters):
	"""Name of the first record of a doctype matching filters (None if there is none)."""
	names = frappe.get_all(doctype, filters=filters, pluck="name", limit=1, order_by="lft asc")
	return names[0] if names else None


# Date: 2026-10-09
def make_teams():
	"""EVisions Team 1-6; leader and manager names filled only where still empty."""
	for team, (leader, manager) in TEAMS.items():
		if frappe.db.exists("Maintenance Team", team):
			doc = frappe.get_doc("Maintenance Team", team)
			changed = False
			if leader and not doc.team_leader_name:
				doc.team_leader_name, changed = leader, True
			if manager and not doc.manager_name:
				doc.manager_name, changed = manager, True
			if changed:
				doc.save(ignore_permissions=True)
			continue
		frappe.get_doc({
			"doctype": "Maintenance Team",
			"team_name": team,
			"team_type": "EVisions",
			"team_leader": frappe.db.get_value("Employee", {"employee_name": leader}, "name") if leader else None,
			"team_leader_name": leader,
			"manager_name": manager,
			"status": "Active",
		}).insert(ignore_permissions=True, ignore_mandatory=True)


# Date: 2026-10-09
def make_vendors():
	"""The 34 vendors from the sheet as Maintenance Vendor records."""
	for name in VENDORS:
		if not frappe.db.exists("Maintenance Vendor", name):
			frappe.get_doc({"doctype": "Maintenance Vendor", "vendor_name": name, "status": "Active"}).insert(
				ignore_permissions=True, ignore_mandatory=True
			)


# Date: 2026-10-09
def make_fiber_pulling_teams():
	"""Fiber Pulling Teams from the sheet (vendor left empty: the sheet doesn't say whose they are)."""
	for name in FIBER_PULLING_TEAMS:
		if not frappe.db.exists("Fiber Pulling Team", name):
			frappe.get_doc({"doctype": "Fiber Pulling Team", "fpt_name": name, "status": "Active"}).insert(
				ignore_permissions=True
			)


# Date: 2026-10-09
def refresh_projects():
	"""Recalculate Stage, Site Status, Link ID etc. of every project without sending notifications."""
	for name in frappe.get_all("New Project", pluck="name"):
		doc = frappe.get_doc("New Project", name)
		doc.set_team_details()
		doc.set_link_id()
		doc.set_calculated_fields()
		values = {
			field: doc.get(field)
			for field in ("stage", "site_status", "link_id", "rfs_month", "distance_difference", "final_amount",
				"team", "manager", "supervisor_name")
		}
		values["stage"] = doc.get_stage()
		# Number columns can't be NULL; a normal save turns None into 0, a direct write doesn't.
		for field in ("distance_difference", "final_amount"):
			values[field] = values[field] or 0
		frappe.db.set_value("New Project", name, values, update_modified=False)
