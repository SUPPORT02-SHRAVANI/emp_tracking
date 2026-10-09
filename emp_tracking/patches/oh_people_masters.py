# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Patch: OH people from the client's "Complaint Data - drop downs" sheet
#
# How this file works
#   Runs once during `bench migrate`. Creates an Employee for every person in the drop-down
#   lists (NOC executives, team leaders, managers, splicers, riders) who is not an Employee
#   yet, so they can be picked as Rider / Splicer on complaints and projects:
#     - matched by name (case-insensitive) first, so nobody is created twice;
#     - Designation: NOC Executive, Team Leader, Manager, Splicer, Rider, or Rider / Splicer
#       for people in both lists;
#     - only the name, designation, company and status are known. Gender, date of birth and
#       date of joining are left empty for HR to complete (no made-up dates).
#   Then links each EVisions team (Team 1-5) to its team leader's Employee.
#   "OTHER" entries in the sheet are skipped.
#
# Change log
#   2026-10-09  Created.
# ---------------------------------------------------------------------------------------------

import frappe

NOC_EXECUTIVES = ["Aniket", "Nitesh", "Abhishek", "Rohit Shivale", "Rushikesh"]
MANAGERS = ["Shyam Morale", "Amol Jagadale"]  # the sheet also spells it "Amol Jagdale"
# Team leader -> EVisions team (from the "Team / Vendor Name" table); Vilas Gaikwad's team is not known yet.
TEAM_LEADERS = {
	"Rahul Dilliwala": "Team 1",
	"Sanket Kandhare": "Team 2",
	"Amar Belapurkar": "Team 3",
	"Akash Pardeshi": "Team 4",
	"Sachin Khude": "Team 5",
	"Vilas Gaikwad": None,
}
SPLICERS = [
	"Dhammadeep Jondhale", "Amol Waghmare", "Aakash Nawadi", "Rohan Tupe", "Akshay Chavhan",
	"Rameshwar Kedarkunte", "Ram Jamadar", "Arun Charhate", "Prakash Madke", "Dilip Pawaar",
	"Shamburaj Khilare", "Shubham Navgire", "Omkar Chavan", "Deepak", "Rahul Tupe", "Pramod Kalvankar",
	"Mahesh Khedekar", "Sanket Kotkar", "Chetan Kadam", "Sanket Kandhare",
]
RIDERS = [
	"Hemant Chaudhari", "Pravin Ghume", "Aditya Manjare", "Malik Arjun Talwar", "Ganesh Bansode",
	"Akshay Tandalekar", "Sherkhar Charhate", "Prakash Madke", "Sachin Khude", "Akash Pardeshi",
	"Rahul Dilliwala", "Amar Belapurkar", "Rahul Tupe", "Kunal Kohli", "Vilas Gaikwad", "Pravin Ghone",
	"Rutik Kakade", "Ashok Dolas", "Pratap Kachave", "Sanket Kandhare", "Ajay Hinge", "Kuldeep Kamathe",
	"Tejas", "Gaurav", "Tushar Waghmare", "Umesh Goled", "Dhiraj Darak", "Ganesh Kachve", "Anil Rathod",
]


# Date: 2026-10-09
def execute():
	"""Create the missing Employees with their designation, then link team leaders to Team 1-5."""
	company = frappe.defaults.get_global_default("company") or first_company()
	if not company:
		return
	for person, designation in people_with_designation().items():
		ensure_designation(designation)
		employee = find_employee(person)
		if employee:
			if not frappe.db.get_value("Employee", employee, "designation"):
				frappe.db.set_value("Employee", employee, "designation", designation, update_modified=False)
			continue
		first, _, last = person.partition(" ")
		try:
			frappe.get_doc({
				"doctype": "Employee",
				"first_name": first,
				"last_name": last or None,
				"designation": designation,
				"company": company,
				"status": "Active",
			}).insert(ignore_permissions=True, ignore_mandatory=True)
		except Exception:
			# One bad record must not stop the migrate; it is listed in the Error Log.
			frappe.log_error(title=f"OH people patch: could not create Employee {person}")

	for leader, team in TEAM_LEADERS.items():
		employee = find_employee(leader)
		if team and employee and frappe.db.exists("Maintenance Team", team):
			if not frappe.db.get_value("Maintenance Team", team, "team_leader"):
				frappe.db.set_value("Maintenance Team", team, {"team_leader": employee, "team_leader_name": leader},
					update_modified=False)


# Date: 2026-10-09
def people_with_designation():
	"""Every person once, with one designation: NOC / Manager / Team Leader win over field roles."""
	people = {}
	for name in RIDERS:
		people[name] = "Rider"
	for name in SPLICERS:
		people[name] = "Rider / Splicer" if people.get(name) == "Rider" else "Splicer"
	for name in TEAM_LEADERS:
		people[name] = "Team Leader"
	for name in MANAGERS:
		people[name] = "Manager"
	for name in NOC_EXECUTIVES:
		people[name] = "NOC Executive"
	return people


# Date: 2026-10-09
def find_employee(person):
	"""Employee whose full name matches (case-insensitive); None if there is none."""
	names = frappe.get_all("Employee", filters={"employee_name": person}, pluck="name", limit=1)
	if not names and person == "Amol Jagadale":
		names = frappe.get_all("Employee", filters={"employee_name": "Amol Jagdale"}, pluck="name", limit=1)
	return names[0] if names else None


# Date: 2026-10-09
def ensure_designation(designation):
	"""Create the Designation if this site does not have it yet."""
	if not frappe.db.exists("Designation", designation):
		frappe.get_doc({"doctype": "Designation", "designation_name": designation}).insert(ignore_permissions=True)


# Date: 2026-10-09
def first_company():
	"""The site's first Company, when no default company is set."""
	companies = frappe.get_all("Company", pluck="name", limit=1, order_by="creation asc")
	return companies[0] if companies else None
