# ---------------------------------------------------------------------------------------------
# Patch: splicers and riders of EVision TEAM 1-6, from the user's team sheet (2026-11-27,
# "assign these splicer and rider according to the team"). Created 2026-11-27.
#
# The sheet's names were matched to Employee records on newsite.local; spellings differ:
#   Shambhuraj Khilare = Shamburaj Khilare, Rameshwar Kedarkun = Rameshwar Kedarkunte,
#   Khuldeep Kamthe = Kuldeep Kamathe, Kunal Kolhi = Kunal Kohli, Dilip Pawar = Dilip Pawaar,
#   Malik Arjun = Malik Arjun Talwar, Arun Charate = Arun Charhate,
#   Shekhar Charate = Sherkhar Charhate; "Gaurav" and "Deepak" (first name only) are taken as
#   Gaurav Thorat and Deepak Lad. Pramod Mali (TEAM 2 rider) and Alok (TEAM 4 splicer) have no
#   Employee record and are left out.
# Each person is found by Employee name (any case), so a site with other Employee IDs still works;
# a name not found is skipped and printed. Members already in the team are kept. Safe to run again.
# ---------------------------------------------------------------------------------------------

import frappe

TEAMS = {
	"TEAM 1": {"Splicer": ["Rahul Tupe", "Rohan Tupe", "Shamburaj Khilare"], "Rider": ["Kuldeep Kamathe"]},
	"TEAM 2": {"Splicer": ["Rameshwar Kedarkunte", "Sanket Kotkar", "Mahesh Khedekar"],
		"Rider": ["Pravin Ghone", "Akshay Tandalekar"]},
	"TEAM 3": {"Splicer": ["Amol Waghmare", "Akshay Chavhan", "Deepak"], "Rider": ["Kunal Kohli", "Gaurav"]},
	"TEAM 4": {"Splicer": ["Dhammadeep Jondhale", "Dilip Pawaar"], "Rider": ["Aditya Manjare"]},
	"TEAM 5": {"Splicer": ["Omkar Chavan", "Shubham Navgire"], "Rider": ["Ganesh Kachve", "Malik Arjun Talwar"]},
	"TEAM 6": {"Splicer": ["Arun Charhate", "Aakash Nawadi", "Chetan Kadam"],
		"Rider": ["Umesh Goled", "Rutik Kakade", "Sherkhar Charhate"]},
}


def execute():
	missing = []
	for team_name, roles in TEAMS.items():
		team = frappe.db.get_value("Maintenance Team", {"team_name": team_name}, "name")
		if not team:
			missing.append(team_name)
			continue
		doc = frappe.get_doc("Maintenance Team", team)
		have = {m.employee for m in doc.members}
		for role, names in roles.items():
			for person in names:
				# an active Employee of that exact name; HR-EMP-... first when there are two
				emp = frappe.db.get_value("Employee", {"employee_name": person, "status": "Active"}, "name",
					order_by="name asc")
				if not emp:
					missing.append(f"{team_name} {role} {person}")
					continue
				if emp not in have:
					doc.append("members", {"employee": emp, "role": role, "active": 1})
					have.add(emp)
		doc.save(ignore_permissions=True)
	frappe.db.commit()
	print("Team members set;", f"not found: {', '.join(missing)}" if missing else "all found")
