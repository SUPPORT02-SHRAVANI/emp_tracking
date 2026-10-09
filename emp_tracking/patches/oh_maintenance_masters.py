# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Patch: OH maintenance masters (client's "Complaint Data - drop downs" sheet)
#
# How this file works
#   Runs once during `bench migrate` and loads:
#     1. Areas: every Pune area from the sheet, with its PIN code as the Area Code.
#     2. "Maintained By" names that are not yet vendors (Gujarwadi Area, Vendor Lonavala, Dighi
#        Group, Vendor Shitole, Ravet Cluster, Santosh Dagade, and the joint vendors).
#     3. Cable team "Kaku Bharadwaj" as a Fiber Pulling Team.
#   Only missing records are created; existing ones are left as they are.
#
# Change log
#   2026-10-09  Created.
# ---------------------------------------------------------------------------------------------

import frappe

# (area, PIN) from the sheet's "Area" column.
AREAS = [
	("9 DRD", "411014"), ("AFMC", "411040"), ("Airport (Pune)", "411032"), ("Akurdi", "411035"),
	("Ammunition Factory Khadki", "411003"), ("Bhosari I.E.", "411026"), ("Bhosarigoan", "411039"),
	("Bibvewadi", "411037"), ("C D A (O)", "411001"), ("C M E", "411031"), ("Chinchwad East", "411019"),
	("Chinchwadgaon", "411033"), ("Dapodi Bazar", "411012"), ("Dapodi", "411012"), ("Dhanori", "411015"),
	("Dighi Camp", "411015"), ("Dr.B.A. Chowk", "411001"), ("Dukirkline", "411014"), ("East Khadki", "411003"),
	("Ghorpuri Bazar", "411001"), ("H.E. Factory", "411003"), ("Hadapsar", "411028"), ("Hadpsar I.E.", "411013"),
	("Iaf Station", "411032"), ("Indrayaninagar", "411026"), ("Kalewadi", "411017"), ("Kasarwadi", "411034"),
	("Khadki Bazar", "411003"), ("Khadki", "411003"), ("Khondhwa KH", "411048"), ("Kondhwa BK", "411048"),
	("Kondhwa Lh", "411048"), ("Lohogaon", "411047"), ("M.Phulenagar", "411019"), ("Market Yard (Pune)", "411037"),
	("Masulkar Colony", "411018"), ("Mohamadwadi", "411060"), ("Mundhva AV", "411036"), ("Mundhva", "411036"),
	("N I B M", "411048"), ("N.W. College", "411001"), ("Nehrunagar (Pune)", "411018"), ("P.C.N.T.", "411044"),
	("Pimpri Colony", "411017"), ("Pimpri P F", "411018"), ("Pimpri Waghire", "411017"), ("Punawale", "411033"),
	("Pune Cantt East", "411001"), ("Pune", "411001"), ("Pune New Bazar", "411001"), ("Rupeenagar", "411062"),
	("Sachapir Street", "411001"), ("Salisbury Park", "411037"), ("Sangavi", "411027"), ("Sasanenagar", "411028"),
	("Srpf", "411022"), ("T.V. Nagar", "411037"), ("Talwade", "411062"), ("Thathawade", "411033"),
	("Thergaon", "411033"), ("Vadgaon Sheri", "411014"), ("Vidyanagar (Pune)", "411032"), ("Vishrantwadi", "411015"),
	("Wakad", "411057"), ("Wanowarie", "411040"), ("Yamunanagar", "411044"), ("Yerwada", "411006"),
	("Yerwada T.S.", "411006"), ("A.R. Shala", "411004"), ("Anandnagar (Pune)", "411051"), ("Armament", "411021"),
	("Aundh T.S.", "411007"), ("Bajirao Road", "411002"), ("Baner Road", "411008"), ("Bhavani Peth", "411042"),
	("Bhusari Colony", "411038"), ("Botanical Garden (Pune)", "411020"), ("Congress House Road", "411005"),
	("Deccan Gymkhana", "411004"), ("Dhankawadi", "411043"), ("Ex. Serviceman Colony", "411038"),
	("Film Institute", "411004"), ("Ganeshkhind", "411007"), ("Ghorpade Peth", "411042"),
	("Govt. Polytechnic", "411016"), ("Guruwar Peth", "411042"), ("Kapad Ganj", "411002"), ("Karvenagar", "411052"),
	("Kasba Peth", "411011"), ("Katraj", "411046"), ("Khadakwasla R.S.", "411024"), ("Kothrud", "411038"),
	("Lokmanyanagar", "411030"), ("Mangalwar Peth (Pune)", "411011"), ("Model Colony", "411016"),
	("N.C.L. Pune", "411008"), ("N.D.A. Khadakwasla", "411023"), ("N.I.A.", "411045"), ("Nana Peth", "411002"),
	("Narayan Peth", "411030"), ("Navsahyadri", "411052"), ("Parvati Gaon", "411009"), ("Parvati", "411009"),
	("Pune City", "411002"), ("Range Hills", "411020"), ("Rashtra Bhasha Bhavan", "411030"), ("Rasta Peth", "411011"),
	("Raviwar Peth", "411002"), ("S.P. College", "411030"), ("S.S.C.Exam Board", "411005"), ("Sadashiv Peth", "411030"),
	("Shaniwar Peth (Pune)", "411030"), ("Shivaji Housing Society", "411016"), ("Shivajinagar (Pune)", "411005"),
	("Shukrawar Peth (Pune)", "411002"), ("Swargate Chowk", "411042"), ("Swargate", "411042"),
	("Vadgaon Budruk", "411041"), ("Warje", "411058"),
]

# "Maintained By" names from the sheet that are not in the vendor list loaded by oh_project_masters.
EXTRA_VENDORS = [
	"Gujarwadi Area", "Vendor Lonavala", "Dighi Group", "Vendor Shitole", "Ravet Cluster", "Santosh Dagade",
	"Spine Teleinfra / Hyperband", "Swarad / Hyperband",
]

EXTRA_FIBER_PULLING_TEAMS = ["Kaku Bharadwaj"]


# Date: 2026-10-09
def execute():
	"""Create the missing Areas, vendors and fiber pulling teams."""
	frappe.reload_doc("emp_tracking", "doctype", "fiber_pulling_team")
	for area, pin in AREAS:
		if not frappe.db.exists("Area", area):
			frappe.get_doc({"doctype": "Area", "area_name": area, "area_code": pin, "status": "Active"}).insert(
				ignore_permissions=True, ignore_mandatory=True
			)
	for name in EXTRA_VENDORS:
		if not frappe.db.exists("Maintenance Vendor", name):
			frappe.get_doc({"doctype": "Maintenance Vendor", "vendor_name": name, "status": "Active"}).insert(
				ignore_permissions=True, ignore_mandatory=True
			)
	for name in EXTRA_FIBER_PULLING_TEAMS:
		if not frappe.db.exists("Fiber Pulling Team", name):
			frappe.get_doc({"doctype": "Fiber Pulling Team", "fpt_name": name, "status": "Active"}).insert(
				ignore_permissions=True
			)
