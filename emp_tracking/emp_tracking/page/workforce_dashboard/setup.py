# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""One-time install of the Workforce Dashboards: roles, custom fields, the page and its desk menus.

Safe to run again; every step only creates or updates what is missing.

	bench --site newsite.local execute emp_tracking.emp_tracking.page.workforce_dashboard.setup.install

How it works: install() / apply_access() create the custom fields, import the page, make the roles and
permissions, and build two desk tiles, each opening its own Workspace Sidebar:
	"Dashboard"         -> the Workforce Dashboards page
	"OverHead Project"  -> tasks, attendance, leave, claims, field tracking and team lists
Staff (employees with only self-service roles) get a module profile and see only these tiles plus
Leaves and Expenses.

Change log:
	2026-10-09  The "EVision" tile and sidebar are replaced by two: "Dashboard" (dashboards page) and
	            "OverHead Project" (workforce links). The old "EVision" tile/sidebar is deleted.
	            Helpdesk NOC (complaints) is untouched.
	2026-10-09  OverHead Project sidebar starts with an "OH Project" section: New Project, Network
	            Links, Fiber Pulling Teams, EVisions Teams, Vendors.
	2026-10-09  One menu everywhere (oh_menu): Dashboard, OverHead Project and Helpdesk NOC all show
	            Dashboards, OH Project, Complaints, Masters and the workforce lists, each tile with
	            its own section on top. Our own screens are DocType/Page links so the menu stays put
	            while moving between them. Tiles also shown to the OH and NOC roles (TILE_ROLES).
	2026-10-09  Menu keeps only OverHead screens: Dashboards, OH Project, Complaints, Masters. The
	            workforce lists (tasks, attendance, leave, claims, trips, employees) were removed.
	2026-10-09  One fixed order on every tile: Dashboards, New Project, Complaints, Network (Nodes,
	            Network Links, Sites), Masters.
"""

import os

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.modules.import_file import import_file_by_path

from emp_tracking.emp_tracking.page.workforce_dashboard.access import CUSTOM_ROLES, TEAM_LEAD

PAGE_ROLES = ["Employee", "Team Lead", "HR Manager", "HR User", "Finance Manager", "Accounts Manager", "Management", "System Manager"]
# Desk tiles: everyone above plus the OH project and NOC roles (2026-10-09).
TILE_ROLES = PAGE_ROLES + [
	"Project Head", "Area Manager", "Fiber Team", "Splicing Team", "NOC Head", "Maintenance Agent", "Accounts User",
]
SIDEBAR = "OverHead Project"  # 2026-10-09: was "EVision"; holds the workforce links
DASHBOARD_SIDEBAR = "Dashboard"  # 2026-10-09: split out of "EVision"; holds the dashboards page
OLD_SIDEBARS = ("Workforce", "EVision")  # earlier names of the menu, deleted by make_navigation()
HOME_PAGE = "app/workforce-dashboard"
# After login Frappe sends a user to the first of their roles that has a home page; without one it falls
# back to the portal / website home page, which on this site is the Helpdesk portal.
HOME_ROLES = ["Employee", "Team Lead", "HR Manager", "HR User", "Finance Manager", "Management"]

CUSTOM_FIELDS = {
	"Task": [
		{"fieldname": "custom_assigned_to", "label": "Assigned Employee", "fieldtype": "Link", "options": "Employee",
			"insert_after": "priority", "in_list_view": 1, "in_standard_filter": 1},
		{"fieldname": "custom_assigned_employee_name", "label": "Assigned Employee Name", "fieldtype": "Data",
			"fetch_from": "custom_assigned_to.employee_name", "read_only": 1, "insert_after": "custom_assigned_to"},
		{"fieldname": "custom_work_category", "label": "Work Category", "fieldtype": "Select", "options": "\nProject\nMaintenance",
			"insert_after": "custom_assigned_employee_name", "in_standard_filter": 1},
		{"fieldname": "custom_site", "label": "Site / Location", "fieldtype": "Data", "insert_after": "custom_work_category"},
		{"fieldname": "custom_service_request", "label": "Service Request (SR)", "fieldtype": "Link", "options": "Complaint Information",
			"insert_after": "custom_site"},
	],
	"Employee": [
		{"fieldname": "custom_work_type", "label": "Work Type", "fieldtype": "Select", "options": "\nField\nOffice",
			"insert_after": "designation", "in_standard_filter": 1,
			"description": "Field: every working hour counts as field hours. Office: every working hour counts as office hours. "
				"Blank: decided from GPS trips in the last 30 days."},
	],
	"Employee Checkin": [
		{"fieldname": "custom_work_mode", "label": "Work Mode", "fieldtype": "Select", "options": "\nOffice\nField",
			"insert_after": "log_type", "in_list_view": 1},
	],
	"Expense Claim": [
		{"fieldname": "custom_petrol_section", "label": "Petrol / KM Details", "fieldtype": "Section Break", "insert_after": "expenses"},
		{"fieldname": "custom_claim_from", "label": "Claim Period From", "fieldtype": "Date", "insert_after": "custom_petrol_section"},
		{"fieldname": "custom_claim_to", "label": "Claim Period To", "fieldtype": "Date", "insert_after": "custom_claim_from"},
		{"fieldname": "custom_km_source", "label": "KM Source", "fieldtype": "Select", "options": "\nGPS\nManual", "insert_after": "custom_claim_to"},
		{"fieldname": "custom_petrol_col", "fieldtype": "Column Break", "insert_after": "custom_km_source"},
		{"fieldname": "custom_claimed_km", "label": "Claimed KM", "fieldtype": "Float", "insert_after": "custom_petrol_col"},
		{"fieldname": "custom_gps_km", "label": "GPS KM", "fieldtype": "Float", "insert_after": "custom_claimed_km",
			"description": "Distance recorded by GPS trips for the claim period"},
		{"fieldname": "custom_eligible_km", "label": "Eligible KM", "fieldtype": "Float", "insert_after": "custom_gps_km",
			"description": "Claimed KM, limited to GPS KM + 10%"},
		{"fieldname": "custom_rate_per_km", "label": "Rate per KM", "fieldtype": "Currency", "insert_after": "custom_eligible_km"},
	],
}


# Date: 2026-10-09
# Full install: custom fields, the page, then everything apply_access() does.
@frappe.whitelist(methods=["POST"])
def install():
	frappe.only_for("System Manager")
	create_custom_fields(CUSTOM_FIELDS, update=True)
	import_page()
	apply_access()
	return "Workforce Dashboards installed. Open /app/workforce-dashboard"


# Date: 2026-10-09
# Re-applies roles, permissions, the two desk tiles/sidebars, home pages and staff restrictions.
@frappe.whitelist(methods=["POST"])
def apply_access():
	"""Roles, desk permissions, sidebar and landing page. Safe to re-run after any change here."""
	frappe.only_for("System Manager")
	create_custom_fields({"Employee": CUSTOM_FIELDS["Employee"]}, update=True)
	import_page()
	make_roles()
	grant_permissions()
	grant_demo_roles()
	make_navigation()
	make_home_pages()
	restrict_staff_modules()
	restrict_desktop_icons()
	frappe.db.commit()  # nosemgrep: also runs from the browser, nothing else commits for us
	frappe.clear_cache()
	return "Roles, permissions, modules, sidebar and home page applied."


# ---- what staff see in the desk -------------------------------------------------
#
# Frappe shows a module's workspaces, sidebar and desktop icon to anyone who can read one
# document type in it. The Employee role can read its own Leave Application, Expense Claim,
# Employee, ... so out of the box every employee sees HR Setup, Recruitment, Payroll etc.
# (the data inside stays permission-checked; only the menus show).
#
# Staff = users whose roles are only the ones below. They get the standard Module Profile
# mechanism (blocked modules hide workspaces) and every desktop icon except these is
# limited to non-staff roles. Administrator has every role, so it still sees everything.

STAFF_ROLES = {
	"Employee", "Employee Self Service", "Team Lead", "Leave Approver", "Expense Approver", "Projects User",
	"All", "Guest", "Desk User",
}
STAFF_PROFILE = "Workforce Staff"
STAFF_MODULES = ("Emp Tracking",)  # modules staff keep
STAFF_ICONS = (DASHBOARD_SIDEBAR, SIDEBAR, "Leaves", "Expenses")  # self service: dashboard, workforce menu, apply leave, petrol claims


# Date: 2026-10-09
# True when the user has only self-service roles (see STAFF_ROLES).
def is_staff(user):
	return user != "Administrator" and set(frappe.get_roles(user)) <= STAFF_ROLES


# Date: 2026-10-09
# Gives staff users the "Workforce Staff" module profile (only Emp Tracking open) and takes it
# back from users promoted to HR / Finance / Management.
def restrict_staff_modules():
	if frappe.db.exists("Module Profile", STAFF_PROFILE):
		profile = frappe.get_doc("Module Profile", STAFF_PROFILE)
	else:
		profile = frappe.new_doc("Module Profile")
		profile.module_profile_name = STAFF_PROFILE
	profile.set("block_modules", [
		{"module": m} for m in frappe.get_all("Module Def", pluck="name", order_by="name") if m not in STAFF_MODULES
	])
	profile.save(ignore_permissions=True)

	employee_users = frappe.get_all("Employee", filters={"status": "Active", "user_id": ["is", "set"]}, pluck="user_id")
	for user in set(employee_users):
		current = frappe.db.get_value("User", user, "module_profile")
		if is_staff(user) and current != STAFF_PROFILE:
			doc = frappe.get_doc("User", user)
			doc.module_profile = STAFF_PROFILE
			doc.save(ignore_permissions=True)
		elif not is_staff(user) and current == STAFF_PROFILE:
			# Promoted to HR / Finance / Management: give the modules back.
			doc = frappe.get_doc("User", user)
			doc.module_profile = None
			doc.set("block_modules", [])
			doc.save(ignore_permissions=True)


RESTRICTED_ICONS_KEY = "workforce_restricted_desktop_icons"


# Date: 2026-10-09
def restrict_desktop_icons():
	"""Limit every open desktop icon (except the self-service ones) to non-staff roles."""
	import json

	open_icons = [
		name for name in frappe.get_all("Desktop Icon", pluck="name")
		if name not in STAFF_ICONS and not frappe.db.exists("Has Role", {"parenttype": "Desktop Icon", "parent": name})
	]
	roles = [r for r in frappe.get_all("Role", filters={"disabled": 0}, pluck="name") if r not in STAFF_ROLES]
	for name in open_icons:
		# Rows are written directly: saving a standard icon in developer mode would rewrite the
		# owning app's JSON files (hrms, erpnext, ...), which we must not touch.
		for idx, role in enumerate(roles, 1):
			frappe.get_doc({
				"doctype": "Has Role", "name": frappe.generate_hash(length=10), "parent": name,
				"parenttype": "Desktop Icon", "parentfield": "roles", "role": role, "idx": idx,
			}).db_insert()

	done = set(json.loads(frappe.db.get_default(RESTRICTED_ICONS_KEY) or "[]")) | set(open_icons)
	frappe.db.set_default(RESTRICTED_ICONS_KEY, json.dumps(sorted(done)))
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")


# Date: 2026-10-09
@frappe.whitelist(methods=["POST"])
def undo_staff_restrictions():
	"""Put desktop icons and staff users back the way Frappe ships them."""
	import json

	frappe.only_for("System Manager")
	names = json.loads(frappe.db.get_default(RESTRICTED_ICONS_KEY) or "[]")
	if names:
		frappe.db.delete("Has Role", {"parenttype": "Desktop Icon", "parent": ["in", names]})
	frappe.db.set_default(RESTRICTED_ICONS_KEY, "[]")
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
	for user in frappe.get_all("User", filters={"module_profile": STAFF_PROFILE}, pluck="name"):
		doc = frappe.get_doc("User", user)
		doc.module_profile = None
		doc.set("block_modules", [])
		doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep: also runs from the browser, nothing else commits for us
	frappe.clear_cache()
	return "Desktop icons and staff module access restored."


# What a team lead may do in the desk on their team's records. The dashboard itself checks the
# team scope on every call; these rules let "Open in desk" and the list views work for them too.
TEAM_LEAD_PERMS = {
	"Employee": ("read", "report"),
	"Attendance": ("read", "report", "export"),
	"Employee Checkin": ("read", "report", "export"),
	"Attendance Request": ("read", "write", "submit", "report"),
	"Leave Application": ("read", "write", "submit", "report"),
	"Leave Allocation": ("read", "report"),
	"Expense Claim": ("read", "write", "report", "export"),
	"Task": ("read", "write", "create", "report", "export"),
	"Project": ("read", "report"),
	"Trip 2": ("read", "report", "export"),
	"Trip Stop": ("read", "report"),
	"Location Ping": ("read", "report"),
	"Vehicles": ("read",),
}


# Date: 2026-10-09
# Adds the Team Lead role's desk permissions listed in TEAM_LEAD_PERMS.
def grant_permissions():
	from frappe.permissions import add_permission, update_permission_property

	for doctype, ptypes in TEAM_LEAD_PERMS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": TEAM_LEAD, "permlevel": 0}):
			add_permission(doctype, TEAM_LEAD, 0)
		for ptype in ptypes:
			if ptype == "submit" and not meta.is_submittable:
				continue
			update_permission_property(doctype, TEAM_LEAD, 0, ptype, 1, validate=False)


# Date: 2026-10-09
def grant_demo_roles():
	"""Re-apply the demo logins' roles, in case the demo ran before the custom roles existed."""
	from emp_tracking.emp_tracking.page.workforce_dashboard.demo import EMPLOYEES, OTHER_USERS, email

	for person in EMPLOYEES + OTHER_USERS:
		user = email(person["key"])
		if frappe.db.exists("User", user):
			frappe.get_doc("User", user).add_roles(*[r for r in person["roles"] if frappe.db.exists("Role", r)])
		if person.get("work_type"):
			emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
			if emp and not frappe.db.get_value("Employee", emp, "custom_work_type"):
				frappe.db.set_value("Employee", emp, "custom_work_type", person["work_type"])
	# The lead must see the team's records, not only their own Employee record.
	lead = frappe.db.get_value("Employee", {"user_id": email("amit")}, "name")
	if lead:
		frappe.db.set_value("Employee", lead, "create_user_permission", 0)
		frappe.db.delete("User Permission", {"user": email("amit"), "allow": "Employee"})


# Date: 2026-10-09
# Creates the app's custom roles (CUSTOM_ROLES) that do not exist yet.
def make_roles():
	for role in CUSTOM_ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


# Date: 2026-10-09
@frappe.whitelist(methods=["POST"])
def make_home_pages():
	"""Land dashboard users on the dashboard page instead of the portal after login."""
	frappe.only_for("System Manager")
	for role in HOME_ROLES:
		if frappe.db.exists("Role", role):
			frappe.db.set_value("Role", role, {"home_page": HOME_PAGE, "desk_access": 1})

	# Desk access is decided by user type; make sure the demo logins are desk users.
	for user in frappe.get_all("User", filters={"name": ["like", "%@demo.local"]}, pluck="name"):
		frappe.db.set_value("User", user, "user_type", "System User")
	frappe.cache.delete_key("home_page")
	frappe.clear_cache()
	return "Dashboard users now land on /" + HOME_PAGE


# Date: 2026-10-09
# Re-imports the page definition (workforce_dashboard.json) into the site.
def import_page():
	path = os.path.join(os.path.dirname(__file__), "workforce_dashboard.json")
	import_file_by_path(path, force=True)


# The complaints sidebar from the Helpdesk NOC fixture; it gets the same one menu (2026-10-09).
NOC_SIDEBAR = "Helpdesk NOC"


# Date: 2026-10-09
# The one EVisions menu, as {section: [items]}. Every tile (Dashboard, OverHead Project,
# Helpdesk NOC) shows this same menu, so moving between dashboards, projects and complaints
# never switches menus.
# All entries are DocType / Page links of our own module: Frappe shows each only to users who
# can open it, and keeps the current menu when one is opened (it matches the link to the page).
def oh_menu():
	def doctype(label, name):
		return {"type": "Link", "label": label, "link_type": "DocType", "link_to": name}

	def page(label, name):
		return {"type": "Link", "label": label, "link_type": "Page", "link_to": name}

	# 2026-10-09: only OverHead screens in the menu (client's request); the HR / workforce lists
	# (tasks, attendance, leave, claims, trips, employees) were taken out. Staff still reach leave
	# and petrol claims through their own "Leaves" and "Expenses" tiles.
	# 2026-10-09: fixed order asked by the client: Dashboards, New Project, Complaints, Nodes,
	# then the other masters.
	return {
		"Dashboards": [page("Workforce Dashboards", "workforce-dashboard"), page("NOC Dashboard", "noc-dashboard")],
		"OH Project": [doctype("New Project", "New Project")],
		"Complaints": [doctype("Complaints", "Complaint Information")],
		"Network": [
			doctype("Nodes", "Node"),
			doctype("Network Links (LINKID)", "Network Link"),
			doctype("Sites", "Site"),
		],
		"Masters": [
			doctype("Areas", "Area"),
			doctype("EVisions Teams", "Maintenance Team"),
			doctype("Vendors", "Maintenance Vendor"),
			doctype("Fiber Pulling Teams", "Fiber Pulling Team"),
		],
	}


# Date: 2026-10-09
# The menu as sidebar rows, in the order of oh_menu() (the same on every tile).
def oh_menu_items():
	menu = oh_menu()
	items = []
	for name in menu:
		links =[item for item in menu[name] if link_exists(item)]
		if links:
			items.append({"type": "Section Break", "label": name})
			items.extend(links)
	return items


# Date: 2026-10-09
# A DocType / Page link is kept only if that DocType / Page exists on this site.
def link_exists(item):
	if item["link_type"] in ("DocType", "Page"):
		return bool(frappe.db.exists(item["link_type"], item["link_to"]))
	return True


# Date: 2026-10-09
# Builds the desk tiles and gives all of them the same one menu, in the same order:
#   "Dashboard", "OverHead Project", and "Helpdesk NOC" (tile and roles from its fixture)
# and deletes the sidebars/tiles the menu had before ("Workforce", then "EVision").
def make_navigation():
	for old in OLD_SIDEBARS:
		if old in (SIDEBAR, DASHBOARD_SIDEBAR):
			continue
		if frappe.db.exists("Desktop Icon", old):
			frappe.delete_doc("Desktop Icon", old, force=True, ignore_permissions=True)
		if frappe.db.exists("Workspace Sidebar", old):
			frappe.delete_doc("Workspace Sidebar", old, force=True, ignore_permissions=True)

	make_tile(DASHBOARD_SIDEBAR, oh_menu_items(), icon="dashboard", color="blue")
	make_tile(SIDEBAR, oh_menu_items(), icon="users", color="blue")
	if frappe.db.exists("Workspace Sidebar", NOC_SIDEBAR):
		set_sidebar_items(frappe.get_doc("Workspace Sidebar", NOC_SIDEBAR), oh_menu_items())


# Date: 2026-10-09
# Replaces a sidebar's rows (adding the layout defaults every row needs) and saves it.
def set_sidebar_items(sidebar, items):
	for item in items:
		item.update({"child": 0, "collapsible": 1, "indent": 0, "keep_closed": 0, "show_arrow": 0})
	sidebar.set("items", items)
	sidebar.save(ignore_permissions=True)


# Date: 2026-10-09
# Creates/updates one Workspace Sidebar with the given items and the desktop tile that opens it,
# visible to TILE_ROLES.
def make_tile(name, items, icon, color):
	sidebar = frappe.get_doc("Workspace Sidebar", name) if frappe.db.exists("Workspace Sidebar", name) else frappe.new_doc("Workspace Sidebar")
	sidebar.update({"title": name, "header_icon": icon, "module": "Emp Tracking", "app": "emp_tracking", "standard": 0})
	set_sidebar_items(sidebar, items)

	tile = frappe.get_doc("Desktop Icon", name) if frappe.db.exists("Desktop Icon", name) else frappe.new_doc("Desktop Icon")
	tile.update({
		"label": name,
		"app": "emp_tracking",
		"icon": icon,
		"bg_color": color,
		"icon_type": "Link",
		"link_type": "Workspace Sidebar",
		"link_to": name,
		"sidebar": name,
		"hidden": 0,
		"standard": 0,
	})
	tile.set("roles", [{"role": r} for r in TILE_ROLES if frappe.db.exists("Role", r)])
	tile.save(ignore_permissions=True)
