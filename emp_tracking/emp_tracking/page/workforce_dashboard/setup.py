# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""One-time install of the Workforce Dashboards: roles, custom fields, the page and its desk menus.

Safe to run again; every step only creates or updates what is missing.

	bench --site newsite.local execute emp_tracking.emp_tracking.page.workforce_dashboard.setup.install

How it works: install() / apply_access() create the custom fields, import the page, make the roles and
permissions, and build one desk tile, "EVision" (2026-10-24; was "Dashboard" + "OverHead Project"),
opening the EVision Workspace Sidebar: dashboards, FTTH work orders, OH projects, complaints,
network, teams and settings (see oh_menu()).
Staff (employees with only self-service roles) get a module profile and see only this tile plus
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
	2026-10-09  after_migrate() (hooks.py) rebuilds the roles, tiles and menu after every migrate,
	            so a Frappe Cloud deploy shows the menu without running apply_access by hand.
	            It also creates the dashboards' custom fields (Task, Employee, Employee Checkin,
	            Expense Claim); without them the dashboard says "not installed yet".
	2026-10-09  OverHead-only users (OH_ROLES) see only our tiles: restrict_desktop_icons limits
	            the other tiles to roles outside STAFF_ROLES and OH_ROLES (and rewrites icons
	            restricted before). grant_oh_link_permissions lets the OH roles pick Customer,
	            Company, Employee, Area, Teams, Vendors, Network Link, Node and Site.
	2026-10-09  One fixed order on every tile: Dashboards, New Project, Complaints, Network (Nodes,
	            Network Links, Sites), Masters.
	2026-10-21  Employee custom field "Allow Punch From Anywhere" (custom_allow_punch_from_anywhere),
	            used by overrides/employee_checkin.py to skip the Shift Location radius check.
	2026-10-21  Employee custom field "Punch-In Location" (custom_punch_in_location): Home or Office /
	            Home Only / Office Only / Anywhere. Shown in the Employee list; the mobile app enforces it
	            on punch IN. Created with the other CUSTOM_FIELDS on every migrate.
	2026-10-21  Mobile-app fields that existed only on the cloud site are now made here too: Employee
	            Photos Needed?, Employee Type, Photo Required at Punch, Expo Push Token; Employee Checkin
	            Photo and Punch Address. Employee Home Location and Employee Ticket are now app doctypes.
	2026-10-24  Menu: "Performance Leaderboard" report under Dashboards and "Leaderboard Settings"
	            under Masters. link_exists() also checks Report links.
	2026-10-24  Back to ONE desk tile, "EVision": the "Dashboard" and "OverHead Project" tiles and
	            sidebars are deleted, and the FTTH Tracker and empty WorkForce tiles are hidden
	            (HIDDEN_ICONS). The EVision menu follows the work: Dashboards -> FTTH Work Orders ->
	            OH Projects -> Complaints -> Network -> Teams & Vendors -> Settings, and includes
	            the FTTH Tracker screens when that app is installed. The Helpdesk NOC and FTTH
	            Tracker sidebars carry the same menu (MIRROR_SIDEBARS), so it never changes while
	            moving between screens. FTTH Manager / FTTH User also see the tile.
	2026-10-24  "Staff Monthly Performance" added to the Dashboards section of the menu.
	2026-10-24  Node merged into GIS Node: "Nodes" left the menu, OH roles get link rights on
	            GIS Node instead of Node (patches/merge_node_into_gis_node.py moves the data).
	2026-10-26  Dashboards: "Employee Performance" page instead of the Performance Leaderboard report.
	2026-10-26  "Fiber Store" menu section: dashboard, inward / outward entries, drum balance reports.
	2026-10-26  GIS Node "KMZ Files" section (KMZ File upload, KMZ Folder Path, imported KMZ list),
	            placed above the Site Diagram.
	2026-10-26  KMZ Route / KMZ Point custom fields (Matched By, Site, KMZ Upload) and "Upload KMZ"
	            in the Network menu.
	2026-10-26  KMZ Route / KMZ Point "KMZ Path" field (folder chain inside the KMZ) and the
	            "KMZ Map" page in the Network menu.
	2026-10-27  GIS Node "Fed From Node" (custom_fed_from) and the "Network Topology" page in the
	            Network menu.
	2026-10-27  "KMZ Site Check" page in the Network menu.
	2026-10-27  "KMZ Map Settings" in the Network menu.
	2026-10-27  KMZ Route Matched By gets the option "Drawn on Map" (KMZ Map Add Route).
	2026-10-27  KMZ Route / KMZ Point Matched By get the option "Nearest Node" (KMZ Map Assign Nodes).
	2026-10-29  EVision menu trimmed to the daily screens (37 -> 19 links); the rest still open from
	            the search bar. Links are now nested under their section headings (child = 1), so the
	            sidebar shows collapsible sections instead of one long flat list.
	2026-10-29  Menu grouped by module: OverHead Project, Emp Tracking, NOC.
	2026-10-29  The EVision tile is replaced by three desk tiles, one per module, each with its own
	            sidebar: OverHead Project (Projects, FTTH, Fiber Store, Network, Teams & Vendors),
	            Emp Tracking (dashboards) and NOC (complaints). The Helpdesk NOC tile is hidden (its
	            sidebar shows the NOC menu); the FTTH Tracker sidebar shows the OverHead menu.
	2026-10-29  Desk home keeps only OverHead Project, Emp Tracking, NOC and Milestone
	            (keep_only_desk_icons, undo: show_hidden_desk_icons); picture icons for the four
	            tiles in public/icons/desktop_icons (Milestone's in milestone_app).
	2026-10-31  New Project merged into FTTH Work Order: the OverHead Project menu loses its
	            "Projects" section and the FTTH link is labelled "Work Orders".
	2026-11-17  "EVision" desk tile back, next to the three module tiles (user's request): its
	            sidebar holds all three module menus (EVISION_MODULES); seen by TILE_ROLES.
	2026-11-23  "Allow Punch From Anywhere" checkbox retired: Punch-In Location = "Anywhere" is the one
	            setting (user's request). after_migrate() runs retire_allow_punch_from_anywhere(), which
	            moves ticked employees to "Anywhere" and then deletes the custom field.
	2026-11-25  "Milestone" (milestone_app) removed from DESK_ICONS, so keep_only_desk_icons() hides
	            its desk tile on migrate (user's request: not an EVision module).
	2026-11-26  OverHead Project and NOC get different workspace icons (user's request): each module
	            tile writes its own Frappe 16.54 `Sidebar` (make_shell) with its own header icon
	            (radio-tower / dashboard / monitor-cog) and menu, undoing Frappe's merge of the three
	            into one "Emp Tracking" Sidebar. The NOC tile is renamed "NOC Helpdesk" (NOC_TILE): the
	            shell name is its URL segment and "noc" is taken by the NOC DocType. The old "NOC"
	            tile/sidebars are deleted via OLD_SIDEBARS.
	2026-11-26  Saved Desktop Layouts get the missing DESK_ICONS tiles (add_desk_icons_to_saved_layouts),
	            because Frappe 16.54 draws only what a user's saved layout lists (user's request: show
	            OverHead Project and NOC Helpdesk on the desk home).
	2026-11-26  NOC Helpdesk menu: "NOC Reports" section with the five NOC workbook reports.
	2026-11-26  NOC Helpdesk menu: Cut Team Summary, and a "Performance & Teams" section (NOC Performance,
	            Team Availability, Field Staff Location Hours, Maintenance Teams).
	2026-11-26  OverHead Project Sidebar is the FTTH module's sidebar (SHELL_MODULES), so Frappe no
	            longer builds a second "FTTH" sidebar with the same screens.
	2026-11-27  Desk home shows only OverHead Project, NOC Helpdesk and Frappe HR (user's request for
	            the main site). Saved Desktop Layouts get every other top-level tile hidden
	            (hide_others_in_saved_layouts), since Frappe 16.54 uses the layout's hidden flags.
	2026-11-27  after_migrate() runs keep_only_desk_icons() in its own try block, so a failure in the
	            menu rebuild no longer skips it (Milestone still showed on the Frappe Cloud site).
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
	# 2026-10-24: FTTH Tracker roles (skipped by make_tile when the app is not installed)
	"FTTH Manager", "FTTH User",
]
# 2026-10-24: one tile and menu again, "EVision" (was "OverHead Project" + "Dashboard" since 2026-10-09)
# 2026-10-29: three module tiles instead of EVision: OverHead Project, Emp Tracking, NOC (user's
# request). SIDEBAR is the Emp Tracking one: staff keep it, and the Workforce Dashboard page shows it.
SIDEBAR = "Emp Tracking"
# Who sees each module tile (System Manager sees all). Emp Tracking keeps TILE_ROLES, as EVision had.
OH_TILE_ROLES = ["Project Head", "Area Manager", "Fiber Team", "Splicing Team", "Accounts User", "Accounts Manager",
	"FTTH Manager", "FTTH User", "Management", "System Manager"]
NOC_TILE_ROLES = ["NOC Head", "Maintenance Agent", "Management", "System Manager"]
# Earlier names of the menu; their tiles and sidebars are deleted by make_navigation()
# 2026-10-29: "EVision" added; "OverHead Project" removed (it is a module tile again).
# 2026-11-17: "EVision" taken out again: it is a tile once more (EVISION_TILE).
# 2026-11-26: + "NOC" (renamed to NOC_TILE); its tile, archived sidebar and Sidebar are deleted.
OLD_SIDEBARS = ("Workforce", "Dashboard", "NOC")
# 2026-11-17: the "EVision" tile, shown next to the module tiles. Its sidebar is all module menus
# together, in this order (section names in oh_menu() are unique across modules, so no clash).
EVISION_TILE = "EVision"
# 2026-11-26: the NOC tile is "NOC Helpdesk" (was "NOC"). Frappe 16.54 makes a tile's Sidebar name
# its URL segment, and "noc" is already the NOC DocType's URL, so /desk/noc/... would open NOC records.
NOC_TILE = "NOC Helpdesk"
EVISION_MODULES = ("Emp Tracking", "OverHead Project", NOC_TILE)
# 2026-10-24: tiles folded into EVision. They are made by Frappe for other workspaces/apps, so they
# are only hidden (hidden=1), never deleted, and re-hidden after every migrate.
# 2026-10-29: "Helpdesk NOC" hidden too; the NOC tile replaces it (its sidebar stays, with the NOC menu).
HIDDEN_ICONS = ("FTTH Tracker", "WorkForce", "Helpdesk NOC")
# 2026-10-29: the only tiles left on the desk home (user's request); every other Desktop Icon is
# hidden after each migrate by keep_only_desk_icons(). Their pictures are SVGs in
# <app>/public/icons/desktop_icons/{solid,subtle}/<scrubbed label>.svg (emp_tracking, milestone_app).
# 2026-11-17: + EVision.
# 2026-11-25: - Milestone (milestone_app / BNI, not part of EVision; user's request). Only its desk
# tile is hidden; the app and its data stay installed.
# 2026-11-26: "NOC" -> NOC_TILE.
# 2026-11-27: only OverHead Project, NOC Helpdesk and Frappe HR (hrms' App tile) stay (user's request
# for the main site). Emp Tracking and EVision tiles are still built (their sidebars and routes keep
# working, e.g. the Workforce Dashboard home page) but hidden from the desk home.
DESK_ICONS = ("OverHead Project", NOC_TILE, "Frappe HR")
# Icons hidden by keep_only_desk_icons(), kept so the change can be undone (show_hidden_desk_icons()).
DESK_HIDDEN_KEY = "emp_tracking_desk_hidden_icons"
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
		# 2026-11-23: "Allow Punch From Anywhere" (custom_allow_punch_from_anywhere, added 2026-10-21) removed
		# from here; Punch-In Location = "Anywhere" replaces it (see retire_allow_punch_from_anywhere()).
		# 2026-10-21: read by the mobile app (validatePunchAllowed) to decide where this employee may
		# punch IN from. Option strings must match PUNCH_IN_LOCATION_RULES in the app's src/api/config.ts.
		{"fieldname": "custom_punch_in_location", "label": "Punch-In Location", "fieldtype": "Select",
			"options": "\nHome or Office\nHome Only\nOffice Only\nAnywhere",
			"insert_after": "custom_work_type", "in_list_view": 1, "in_standard_filter": 1,
			"description": "Where this employee may punch IN from in the mobile app. Home: the manager-approved "
				"Employee Home Location. Office: the Shift Location. Blank: field employees home or office, "
				"others the shift location."},
		# 2026-10-21: fields the mobile app needs, until now made by hand only on the cloud site. Same
		# fieldnames / options as there, so update=True just keeps the existing cloud fields as they are.
		{"fieldname": "custom_photos_needed", "label": "Photos Needed?", "fieldtype": "Select", "options": "YES\nNO",
			"insert_after": "employee"},
		{"fieldname": "custom_employee_type", "label": "Employee Type", "fieldtype": "Select",
			"options": "Field Employee\nOffice Employee", "insert_after": "custom_photos_needed", "in_standard_filter": 1},
		{"fieldname": "custom_photo_required", "label": "Photo Required at Punch", "fieldtype": "Check",
			"insert_after": "custom_employee_type"},
		{"fieldname": "custom_expo_push_token", "label": "Expo Push Token", "fieldtype": "Data", "read_only": 1,
			"insert_after": "user_id", "description": "Set by the mobile app; used to send it push notifications."},
	],
	"Employee Checkin": [
		{"fieldname": "custom_work_mode", "label": "Work Mode", "fieldtype": "Select", "options": "\nOffice\nField",
			"insert_after": "log_type", "in_list_view": 1},
		# 2026-10-21: written by the mobile app on every punch. "photo" keeps the cloud site's existing
		# fieldname (no custom_ prefix) because the app already saves into it.
		{"fieldname": "photo", "label": "Photo", "fieldtype": "Attach Image", "insert_after": "custom_work_mode"},
		{"fieldname": "custom_address", "label": "Punch Address", "fieldtype": "Small Text", "insert_after": "photo",
			"description": "Address / real GPS position sent by the mobile app."},
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
	# 2026-10-24: Site Diagram moved here from the Node form (Node merged into GIS Node);
	# drawn by public/js/gis_node.js (doctype_js in hooks.py).
	"GIS Node": [
		# 2026-10-27: upstream node, for the Network Topology page: if it stops, this node stops too
		{"fieldname": "custom_fed_from", "label": "Fed From Node", "fieldtype": "Link", "options": "GIS Node",
			"insert_after": "area", "description": "The node this node gets its fiber from (Network Topology)"},
		# 2026-10-26: "KMZ Files" section: the node's own KMZ file (upload) and its folder path on
		# the shared drive, plus a list of the KMZ files FTTH Tracker imported for this node
		# (drawn by public/js/gis_node.js). It sits above the Site Diagram.
		{"fieldname": "custom_kmz_section", "label": "KMZ Files", "fieldtype": "Section Break",
			"insert_after": "area_manager_no", "collapsible": 1},
		{"fieldname": "custom_kmz_file", "label": "KMZ File", "fieldtype": "Attach",
			"insert_after": "custom_kmz_section", "description": "Upload this node's .kmz / .kml file"},
		{"fieldname": "custom_kmz_column", "fieldtype": "Column Break", "insert_after": "custom_kmz_file"},
		{"fieldname": "custom_kmz_path", "label": "KMZ Folder Path", "fieldtype": "Data", "length": 500,
			"insert_after": "custom_kmz_column",
			"description": "Where the node's KMZ is kept on the shared drive, e.g. GIS/D1J/D1J.kmz"},
		{"fieldname": "custom_kmz_imported", "label": "Imported KMZ Files", "fieldtype": "HTML",
			"insert_after": "custom_kmz_path", "depends_on": "eval:!doc.__islocal"},
		{"fieldname": "custom_site_diagram_section", "label": "Site Diagram", "fieldtype": "Section Break",
			"insert_after": "custom_kmz_imported", "depends_on": "eval:!doc.__islocal"},
		{"fieldname": "custom_site_diagram", "label": "Site Diagram", "fieldtype": "HTML",
			"insert_after": "custom_site_diagram_section"},
	],
	"KMZ Route": [
		# 2026-10-26: how KMZ Upload (doctype kmz_upload) filed this row under its GIS Node
		# 2026-10-27: "Drawn on Map" = drawn with the KMZ Map's Add Route button (kmz_map.add_route)
		# 2026-10-27: "Nearest Node" = node given by the KMZ Map's Assign Nodes (kmz_map.apply_nearest)
		{"fieldname": "custom_kmz_matched_by", "label": "Matched By", "fieldtype": "Select", "insert_after": "gis",
			"options": "\nNode Name\nBuilding Name\nSame Folder\nDrawn on Map\nNearest Node","read_only": 1, "in_standard_filter": 1},
		{"fieldname": "custom_site", "label": "Site", "fieldtype": "Link", "options": "Site",
			"insert_after": "custom_kmz_matched_by", "read_only": 1},
		{"fieldname": "custom_kmz_upload", "label": "KMZ Upload", "fieldtype": "Link", "options": "KMZ Upload",
			"insert_after": "custom_site", "read_only": 1},
		# 2026-10-26: full folder chain inside the KMZ ("My Places / C1U / Icon Residency ..."), for the KMZ Map
		{"fieldname": "custom_kmz_path", "label": "KMZ Path", "fieldtype": "Small Text",
			"insert_after": "custom_kmz_upload", "read_only": 1},
	],
	"KMZ Point": [
		# 2026-10-26: how KMZ Upload (doctype kmz_upload) filed this row under its GIS Node
		# 2026-10-27: "Nearest Node" = node given by the KMZ Map's Assign Nodes (kmz_map.apply_nearest)
		{"fieldname": "custom_kmz_matched_by", "label": "Matched By", "fieldtype": "Select", "insert_after": "gis",
			"options": "\nNode Name\nBuilding Name\nSame Folder\nNearest Node","read_only": 1, "in_standard_filter": 1},
		{"fieldname": "custom_site", "label": "Site", "fieldtype": "Link", "options": "Site",
			"insert_after": "custom_kmz_matched_by", "read_only": 1},
		{"fieldname": "custom_kmz_upload", "label": "KMZ Upload", "fieldtype": "Link", "options": "KMZ Upload",
			"insert_after": "custom_site", "read_only": 1},
		# 2026-10-26: full folder chain inside the KMZ ("My Places / C1U / Icon Residency ..."), for the KMZ Map
		{"fieldname": "custom_kmz_path", "label": "KMZ Path", "fieldtype": "Small Text",
			"insert_after": "custom_kmz_upload", "read_only": 1},
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
def after_migrate():
	"""Runs after every `bench migrate` (hooks.py), also on Frappe Cloud where nobody can run
	`bench execute`: makes the dashboards' custom fields and the roles, and rebuilds the desk
	tiles and the one OverHead menu. The heavier staff restrictions stay in apply_access(),
	run by hand when needed.
	"""
	# 2026-11-23: own try block, so a failure here never stops the menu rebuild below (and vice versa).
	try:
		retire_allow_punch_from_anywhere()
	except Exception:
		frappe.log_error(title="emp_tracking: retiring 'Allow Punch From Anywhere' failed")
	try:
		# Only for doctypes this site has (Task / Expense Claim come from ERPNext / HRMS).
		create_custom_fields(
			{dt: fields for dt, fields in CUSTOM_FIELDS.items() if frappe.db.exists("DocType", dt)}, update=True
		)
		make_roles()
		grant_oh_link_permissions()
		make_navigation()
		frappe.clear_cache()
	except Exception:
		# A menu problem must never fail a deploy; it is listed in the Error Log instead.
		frappe.log_error(title="emp_tracking: rebuilding the desk menu after migrate failed")
	# 2026-11-27: the desk home clean-up in its own try block. It is also the last step of
	# make_navigation(), so any earlier failure in the block above skipped it, and the Frappe Cloud
	# site still showed Milestone after a deploy. Running it twice is harmless.
	try:
		keep_only_desk_icons()
	except Exception:
		frappe.log_error(title="emp_tracking: hiding desk tiles after migrate failed")


# Date: 2026-11-23
# One punch-location setting instead of two (user's request): "Allow Punch From Anywhere" (checkbox,
# 2026-10-21) did the same job as Punch-In Location = "Anywhere" (the field the mobile app reads), so an
# admin had to set both. Employees with the box ticked are first given Punch-In Location = "Anywhere"
# (no access is lost), then the custom field is deleted. Idempotent: does nothing once the field is gone.
# Runs after fixtures are synced, so Punch-In Location exists by then.
RETIRED_ANYWHERE_FIELD = "custom_allow_punch_from_anywhere"
PUNCH_IN_LOCATION_FIELD = "custom_punch_in_location"


def retire_allow_punch_from_anywhere():
	cf_name = frappe.db.get_value("Custom Field", {"dt": "Employee", "fieldname": RETIRED_ANYWHERE_FIELD})
	if not cf_name:
		return
	if not frappe.get_meta("Employee").has_field(PUNCH_IN_LOCATION_FIELD):
		# Without the replacement field, deleting the checkbox would take away access; keep it for now.
		return
	if frappe.db.has_column("Employee", RETIRED_ANYWHERE_FIELD):
		for name in frappe.get_all("Employee", filters={RETIRED_ANYWHERE_FIELD: 1}, pluck="name"):
			frappe.db.set_value("Employee", name, PUNCH_IN_LOCATION_FIELD, "Anywhere", update_modified=False)
	frappe.delete_doc("Custom Field", cf_name, ignore_permissions=True, force=True)


# Date: 2026-10-09
# Re-applies roles, permissions, the desk tiles/sidebars, home pages and staff restrictions.
@frappe.whitelist(methods=["POST"])
def apply_access():
	"""Roles, desk permissions, sidebar and landing page. Safe to re-run after any change here."""
	frappe.only_for("System Manager")
	create_custom_fields({"Employee": CUSTOM_FIELDS["Employee"]}, update=True)
	import_page()
	make_roles()
	grant_permissions()
	grant_oh_link_permissions()
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
# self service: Emp Tracking (dashboards; was EVision until 2026-10-29), apply leave, petrol claims
STAFF_ICONS = (SIDEBAR, "Leaves", "Expenses")

# 2026-10-09: OverHead roles. A user whose roles are only these and STAFF_ROLES sees only the
# OverHead tiles (Dashboard, OverHead Project, Helpdesk NOC) on the desk, not ERPNext's.
# Accounts User is left out on purpose: accountants need the Accounting tiles.
OH_ROLES = {"Project Head", "Area Manager", "Fiber Team", "Splicing Team", "NOC Head", "Maintenance Agent"}


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
	"""Limit every open desktop icon (except ours) to roles outside STAFF_ROLES and OH_ROLES.

	2026-10-09: OverHead-only users (Project Head, Area Manager, Fiber / Splicing Team, NOC)
	now see only our tiles too. Icons restricted on an earlier run get their roles rewritten,
	so the new rule also reaches them. Only icons that had no roles of their own are touched.
	"""
	import json

	ours = set(STAFF_ICONS) | {NOC_SIDEBAR} | set(module_tiles())  # 2026-10-29: + the module tiles
	icons = set(frappe.get_all("Desktop Icon", pluck="name"))
	earlier = set(json.loads(frappe.db.get_default(RESTRICTED_ICONS_KEY) or "[]")) & icons
	open_icons = [
		name for name in icons
		if name not in ours and not frappe.db.exists("Has Role", {"parenttype": "Desktop Icon", "parent": name})
	]
	targets = sorted((earlier | set(open_icons)) - ours)
	limited_to = STAFF_ROLES | OH_ROLES
	roles = [r for r in frappe.get_all("Role", filters={"disabled": 0}, pluck="name") if r not in limited_to]
	for name in targets:
		# Rows are written directly: saving a standard icon in developer mode would rewrite the
		# owning app's JSON files (hrms, erpnext, ...), which we must not touch.
		frappe.db.delete("Has Role", {"parenttype": "Desktop Icon", "parent": name})
		for idx, role in enumerate(roles, 1):
			frappe.get_doc({
				"doctype": "Has Role", "name": frappe.generate_hash(length=10), "parent": name,
				"parenttype": "Desktop Icon", "parentfield": "roles", "role": role, "idx": idx,
			}).db_insert()

	done = earlier | set(targets)
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


# What the OverHead roles may do on the lists their forms link to (2026-10-09). Without these a
# Project Head could not pick a Customer, Area, Team or Vendor on New Project ("no permission").
# (2026-10-31: New Project is merged into FTTH Work Order; the Network Link it makes still needs these.)
# Employee / Customer / Company only get "select": enough to pick one, without opening the record.
OH_LINK_PERMS = {
	"Customer": ("select",),
	"Company": ("select",),
	"Employee": ("select",),
	"Area": ("select", "read"),
	"Maintenance Team": ("select", "read"),
	"Maintenance Vendor": ("select", "read"),
	"Fiber Pulling Team": ("select", "read"),
	"Network Link": ("select", "read"),
	"GIS Node": ("select", "read"),  # 2026-10-24: was Node, merged into GIS Node
	"Site": ("select", "read"),
}


# Date: 2026-10-09
# Gives every OverHead role (OH_ROLES) the OH_LINK_PERMS rights, adding a permission rule where
# the role has none yet. Doctypes this site does not have are skipped.
def grant_oh_link_permissions():
	from frappe.permissions import setup_custom_perms, update_permission_property

	for doctype, ptypes in OH_LINK_PERMS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		for role in OH_ROLES:
			if not frappe.db.exists("Role", role):
				continue
			if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
				# 2026-10-24: inserted directly instead of frappe.permissions.add_permission, which
				# re-validates the doctype's standard rows and fails for GIS Node (FTTH Tracker ships
				# "import" ticked on a non-importable doctype). The new row only grants what
				# OH_LINK_PERMS lists below.
				setup_custom_perms(doctype)
				frappe.get_doc({"doctype": "Custom DocPerm", "parent": doctype, "parenttype": "DocType",
					"parentfield": "permissions", "role": role, "permlevel": 0}).insert(ignore_permissions=True)
			for ptype in ptypes:
				update_permission_property(doctype, role, 0, ptype, 1, validate=False)


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
# 2026-10-24: sidebars that carry the EVision menu besides EVision itself. Frappe may open the
# FTTH Tracker sidebar for an FTTH screen, so it gets the same menu and nothing changes on screen.
# 2026-10-29: sidebar -> the module tile whose menu it copies.
MIRROR_SIDEBARS = {NOC_SIDEBAR: NOC_TILE, "FTTH Tracker": "OverHead Project"}


# Date: 2026-10-09
# The one EVision menu, as {section: [items]}. The EVision tile and the MIRROR_SIDEBARS show
# this same menu, so moving between dashboards, work orders, projects and complaints never
# switches menus.
# Entries are DocType / Page / Report / Workspace links: Frappe shows each only to users who can
# open it, and keeps the current menu when one is opened (it matches the link to the page).
# Links to apps that are not installed (e.g. FTTH Tracker) are dropped by link_exists().
def oh_menu():
	def doctype(label, name):
		return {"type": "Link", "label": label, "link_type": "DocType", "link_to": name}

	def page(label, name):
		return {"type": "Link", "label": label, "link_type": "Page", "link_to": name}

	def report(label, name):
		return {"type": "Link", "label": label, "link_type": "Report", "link_to": name}

	def workspace(label, name):
		return {"type": "Link", "label": label, "link_type": "Workspace", "link_to": name}

	def url(label, path, needs_doctype):
		# needs_doctype: the link is kept only when this DocType exists (see link_exists)
		return {"type": "Link", "label": label, "link_type": "URL", "url": path, "needs_doctype": needs_doctype}

	# 2026-10-09: only OverHead screens in the menu (client's request); the HR / workforce lists
	# (tasks, attendance, leave, claims, trips, employees) were taken out. Staff still reach leave
	# and petrol claims through their own "Leaves" and "Expenses" tiles.
	# 2026-10-24: sections follow the work, from the overview down to setup:
	#   Dashboards -> FTTH Work Orders (WO received -> import -> map -> GIS summary)
	#   -> OH Projects (survey to billing) -> Complaints (maintenance after HOTO)
	#   -> Network (GIS / nodes, links, sites, KMZ) -> Teams & Vendors -> Settings
	# 2026-10-29: only the screens used every day (user's request). Taken off the menu but still
	#   reachable from the search bar: Staff Monthly Performance, Work Order Map, FTTH GIS Summary,
	#   Drum Balance, Fiber Stock Balance, Drums, Network Links, Node Sites, KMZ Routes / Points,
	#   Network Topology, KMZ Site Check, KMZ Map Settings, IBD / Fiber Pulling / Fiber Teams,
	#   FTTH Settings, Leaderboard Settings.
	# 2026-10-29: one desk tile per module (user's request), each with its own sidebar sections:
	#   {tile: {section: [items]}}. The tile order here is the order on the desk.
	return {
		"OverHead Project": {
			# 2026-10-31: "Projects" (New Project) section removed: New Project was merged into
			#             FTTH Work Order, listed here as "Work Orders".
			"FTTH": [
				workspace("FTTH Dashboard", "FTTH Tracker"),  # FTTH number cards and charts
				doctype("Work Orders", "FTTH Work Order"),
				doctype("FTTH Imports", "FTTH Import"),
			],
			# 2026-10-26: cable drum register on ERPNext stock (emp_tracking/fiber_store.py)
			"Fiber Store": [
				url("Fiber Dashboard", "/app/dashboard-view/Fiber%20Store", "Stock Entry"),
				url("Cable Inward / Outward", "/app/stock-entry?custom_fiber_direction=%5B%22is%22%2C%22set%22%5D", "Stock Entry"),
			],
			"Network": [
				doctype("GIS Nodes", "GIS Node"),  # 2026-10-24: the one node master (Node merged in)
				doctype("Link Register", "FTTH Link"),
				doctype("Sites", "Site"),
				page("KMZ Map", "kmz-map"),  # 2026-10-26: routes and pins on a map, with filters
				doctype("Upload KMZ", "KMZ Upload"),  # 2026-10-26: whole KMZ, matched to nodes
			],
			"Teams & Vendors": [
				doctype("Areas", "Area"),
				doctype("EVisions Teams", "Maintenance Team"),
				doctype("Vendors", "Maintenance Vendor"),
				doctype("Field Staff", "Field Staff"),
			],
		},
		"Emp Tracking": {
			"Dashboards": [
				page("Workforce Dashboards", "workforce-dashboard"),
				# 2026-10-26: visual Employee Performance page replaces the Performance Leaderboard
				#             report link (the report still works by URL and feeds the page's FTTH view)
				page("Employee Performance", "employee-performance"),
			],
		},
		NOC_TILE: {
			"Complaints": [
				page("NOC Dashboard", "noc-dashboard"),
				doctype("Complaints", "Complaint Information"),
			],
			# 2026-11-26: the NOC workbook's tabs as reports (emp_tracking/noc_reports.py)
			"NOC Reports": [
				report("Pending Summary", "NOC Pending Summary"),
				# 2026-11-26: every SR counted per team and day, with who closed
				report("Cut Team Summary", "NOC Cut Team Summary"),
				report("Unique Cut Summary", "NOC Unique Cut Summary"),
				report("Unique Cut Master", "NOC Unique Cut Master"),
				report("Major Outage Closure", "NOC Major Outage Closure"),
				report("SLA / TAT Summary", "NOC SLA TAT Summary"),
			],
			# 2026-11-26: performance (month / day, day and night calls) and people
			"Performance & Teams": [
				report("Performance (Day / Night)", "NOC Performance"),
				report("Team Availability", "NOC Team Availability"),
				report("Field Staff Location Hours", "Field Staff Location Hours"),
				doctype("Maintenance Teams", "Maintenance Team"),
			],
		},
	}


# Date: 2026-10-29
# Desk tile settings per module: (icon, roles that see the tile).
# 2026-11-17: + the EVision tile (every module), seen by TILE_ROLES like the old EVision tile.
# 2026-11-26: OverHead Project and NOC get their own Lucide icons (radio-tower: overhead fiber
# routes; monitor-cog: network operations centre), used as the header icon of their own Sidebar
# (make_shell), so the two workspaces no longer look alike (user's request).
def module_tiles():
	return {
		"OverHead Project": ("radio-tower", OH_TILE_ROLES),
		"Emp Tracking": ("dashboard", TILE_ROLES),
		NOC_TILE: ("monitor-cog", NOC_TILE_ROLES),
		EVISION_TILE: ("dashboard", TILE_ROLES),
	}


# Date: 2026-10-09
# The menu as sidebar rows, in the order of oh_menu() (the same on every tile).
# 2026-10-29: takes one tile's {section: [items]} (oh_menu() now has one menu per module tile).
def oh_menu_items(menu):
	items = []
	for name in menu:
		links = [item for item in menu[name] if link_exists(item)]
		for item in links:
			item.pop("needs_doctype", None)  # helper key only, not a sidebar field
		if links:
			items.append({"type": "Section Break", "label": name})
			items.extend(links)
	return items


# Date: 2026-10-09
# A DocType / Page / Report / Workspace link is kept only if it exists on this site; a URL link
# only if the DocType it opens exists (Report added 2026-10-24, Workspace and URL 2026-10-24).
def link_exists(item):
	if item["link_type"] in ("DocType", "Page", "Report", "Workspace"):
		return bool(frappe.db.exists(item["link_type"], item["link_to"]))
	if item.get("needs_doctype"):
		return bool(frappe.db.exists("DocType", item["needs_doctype"]))
	return True


# Date: 2026-10-09
# Builds the one desk tile "EVision" and gives the MIRROR_SIDEBARS the same menu, in the same
# order. Deletes the tiles/sidebars the menu had before (OLD_SIDEBARS) and hides the tiles that
# EVision replaces (HIDDEN_ICONS).
# 2026-10-24: was two tiles ("Dashboard" and "OverHead Project") plus Helpdesk NOC.
# 2026-10-29: three module tiles (OverHead Project, Emp Tracking, NOC), each with its own menu;
# each mirror sidebar copies the menu of its module.
# 2026-11-17: plus the EVision tile, whose menu is all three module menus.
def make_navigation():
	tiles = module_tiles()
	for old in OLD_SIDEBARS:
		if old in tiles:
			continue
		if frappe.db.exists("Desktop Icon", old):
			frappe.delete_doc("Desktop Icon", old, force=True, ignore_permissions=True)
		if frappe.db.exists("Workspace Sidebar", old):
			frappe.delete_doc("Workspace Sidebar", old, force=True, ignore_permissions=True)
		# 2026-11-26: Frappe 16.54 Sidebar of the same name (e.g. the old "NOC" shell)
		if frappe.db.exists("DocType", "Sidebar") and frappe.db.exists("Sidebar", old):
			frappe.delete_doc("Sidebar", old, force=True, ignore_permissions=True)

	menus = {}
	for idx, (tile, menu) in enumerate(oh_menu().items()):
		menus[tile] = oh_menu_items(menu)
		icon, roles = tiles[tile]
		# 2026-11-26: the Sidebar (Frappe 16.54+) gets a copy, made before make_tile adds layout keys
		make_shell(tile, [dict(i) for i in menus[tile]], icon)
		make_tile(tile, menus[tile], icon=icon, color="blue", roles=roles, idx=idx)
	# 2026-11-17: the EVision tile, after the module tiles; copies, since set_sidebar_items adds
	# layout keys to each row.
	icon, roles = tiles[EVISION_TILE]
	evision_items = [dict(i) for module in EVISION_MODULES for i in menus.get(module, [])]
	make_tile(EVISION_TILE, evision_items, icon=icon, color="blue", roles=roles, idx=len(menus))
	for name, tile in MIRROR_SIDEBARS.items():
		if frappe.db.exists("Workspace Sidebar", name):
			# copies: set_sidebar_items adds layout keys to each row
			set_sidebar_items(frappe.get_doc("Workspace Sidebar", name), [dict(i) for i in menus[tile]])
	hide_replaced_icons()
	keep_only_desk_icons()


# Date: 2026-11-26
# Frappe 16.54 draws the desk sidebar, its header icon and the tile's route from `Sidebar`
# documents (one "shell" each, named by title) and no longer reads Workspace Sidebar. Its
# migration merged our OverHead Project, Emp Tracking and NOC sidebars into one "Emp Tracking"
# Sidebar (merged_from), so all three tiles showed that one "dashboard" icon and menu. Each module
# tile gets its own Sidebar again (module Emp Tracking, which allows several), with its own header
# icon and menu.
# Not used for EVision: a Sidebar title may not be a Module Def name, and Frappe has "Evision".
# Sidebar only accepts writes in developer mode or during migrate/install (after_migrate runs
# under in_migrate), so a failure is logged and the other shells are still written.
# 2026-11-26: OverHead Project belongs to module FTTH (SHELL_MODULES). A module without a Sidebar
# document gets one computed by Frappe, so FTTH had its own "FTTH" sidebar (hammer icon) listing
# the same work-order screens as OverHead Project (user: "why overhead and ftth is same?").
# With OverHead Project as FTTH's sidebar that copy is gone, and FTTH screens open in OverHead.
SHELL_MODULES = {"OverHead Project": "FTTH"}


def make_shell(name, items, icon):
	if not frappe.db.exists("DocType", "Sidebar"):
		return  # older Frappe: the Workspace Sidebar made by make_tile() is what the desk shows
	module = SHELL_MODULES.get(name)
	if not (module and frappe.db.exists("Module Def", module)):
		module = SIDEBAR
	try:
		shell = frappe.get_doc("Sidebar", name) if frappe.db.exists("Sidebar", name) else frappe.new_doc("Sidebar")
		shell.update({"title": name, "module": module, "header_icon": icon, "standard": 0})
		set_sidebar_items(shell, items)
	except Exception:
		frappe.log_error(title=f"emp_tracking: writing the {name} Sidebar failed")


# Date: 2026-10-29
# Hides every Desktop Icon except DESK_ICONS (and their own child icons), so the desk home shows
# only the module tiles. Runs after every migrate, so icons another app adds later are hidden too.
# Written straight to the database, like hide_replaced_icons(), so no app's icon JSON is rewritten.
# The names hidden here are remembered under DESK_HIDDEN_KEY for show_hidden_desk_icons().
def keep_only_desk_icons():
	import json

	keep = set(DESK_ICONS)
	hidden_before = set(json.loads(frappe.db.get_default(DESK_HIDDEN_KEY) or "[]"))
	icons = frappe.get_all("Desktop Icon", fields=["name", "parent_icon", "hidden"])
	to_hide = [i.name for i in icons if i.name not in keep and i.parent_icon not in keep and not i.hidden]
	for name in to_hide:
		frappe.db.set_value("Desktop Icon", name, "hidden", 1, update_modified=False)
	# 2026-11-27: a tile that joins DESK_ICONS later (Frappe HR) may have been hidden here before;
	# it and its own child icons are shown again. Only icons this function hid are touched.
	to_show = {i.name for i in icons if i.name in hidden_before and (i.name in keep or i.parent_icon in keep)}
	for name in to_show:
		frappe.db.set_value("Desktop Icon", name, "hidden", 0, update_modified=False)
	frappe.db.set_default(DESK_HIDDEN_KEY, json.dumps(sorted((hidden_before | set(to_hide)) - to_show)))
	add_desk_icons_to_saved_layouts()
	hide_others_in_saved_layouts()
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")


# Date: 2026-11-26
# Frappe 16.54 draws a user's desk home only from their saved Desktop Layout once they have one;
# icons created later are never appended (desktop_icons.bundle.js, arrange_layout). Administrator's
# layout of 2026-11-24 had "Emp Tracking" but not OverHead Project / NOC Helpdesk / EVision, so
# those tiles never showed. Each missing DESK_ICONS tile is added as a visible top-level entry,
# right after the user's "Emp Tracking" entry (or at the end). Nothing else in the layout changes:
# the user's own order and hidden flags stay. Old "NOC" entries (renamed NOC_TILE) are removed.
LAYOUT_KEYS = ("label", "bg_color", "link", "link_type", "app", "icon_type", "parent_icon", "icon", "link_to",
	"idx", "standard", "logo_url", "hidden", "name", "restrict_removal", "icon_image")


def add_desk_icons_to_saved_layouts():
	import json

	if not frappe.db.exists("DocType", "Desktop Layout"):
		return
	for name in frappe.get_all("Desktop Layout", pluck="name"):
		try:
			layout = json.loads(frappe.db.get_value("Desktop Layout", name, "layout") or "[]")
		except ValueError:
			continue  # a layout we cannot read is left as it is
		layout = [i for i in layout if not (i.get("name") == "NOC" and i.get("app") == "emp_tracking")]
		present = {i.get("name") for i in layout} | {i.get("label") for i in layout}
		missing = [n for n in DESK_ICONS if n not in present and frappe.db.exists("Desktop Icon", n)]
		if not missing:
			continue
		at = next((k + 1 for k, i in enumerate(layout) if i.get("name") == SIDEBAR), len(layout))
		for n in missing:
			icon = frappe.get_doc("Desktop Icon", n)
			entry = {key: icon.get(key) for key in LAYOUT_KEYS}
			entry.update({"hidden": 0, "parent_icon": None, "child_icons": []})
			layout.insert(at, entry)
			at += 1
		# Written straight to the database: the layout belongs to the user, no controller logic applies
		frappe.db.set_value("Desktop Layout", name, "layout", json.dumps(layout), update_modified=False)


# Date: 2026-11-27
# Frappe 16.54 takes the hidden flags of a user's saved Desktop Layout, not the Desktop Icon's
# (desktop_icons.bundle.js: "its order, folders and hidden flags are the user's"), so a tile hidden
# by keep_only_desk_icons() still showed for anyone who had saved a layout (e.g. Milestone).
# Every entry that is not in DESK_ICONS is hidden in each saved layout, and DESK_ICONS entries are
# shown, with the modules inside them (Frappe HR's Leaves, Payroll, ... had been hidden while Frappe
# HR was not kept). Entries inside a hidden app are hidden too, since Frappe draws them loose on
# the desk home once their app tile is hidden (seen on newsite.local: Accounting, Users, Build, ...).
# The user can still un-hide a tile in edit mode; the next migrate hides it again.
def hide_others_in_saved_layouts():
	import json

	if not frappe.db.exists("DocType", "Desktop Layout"):
		return
	keep = set(DESK_ICONS)
	for name in frappe.get_all("Desktop Layout", pluck="name"):
		try:
			layout = json.loads(frappe.db.get_value("Desktop Layout", name, "layout") or "[]")
		except ValueError:
			continue  # a layout we cannot read is left as it is
		changed = False
		for entry in layout:
			kept = entry.get("name") in keep or entry.get("label") in keep or entry.get("parent_icon") in keep
			hidden = 0 if kept else 1
			if entry.get("hidden") != hidden:
				entry["hidden"] = hidden
				changed = True
		if changed:
			# Written straight to the database, like add_desk_icons_to_saved_layouts()
			frappe.db.set_value("Desktop Layout", name, "layout", json.dumps(layout), update_modified=False)


# Date: 2026-10-29
# Undo for keep_only_desk_icons(): shows again every icon it hid. Remove the keep_only_desk_icons()
# call in make_navigation() first, or the next migrate hides them again.
#   bench --site newsite.local execute emp_tracking.emp_tracking.page.workforce_dashboard.setup.show_hidden_desk_icons
def show_hidden_desk_icons():
	import json

	for name in json.loads(frappe.db.get_default(DESK_HIDDEN_KEY) or "[]"):
		if frappe.db.exists("Desktop Icon", name):
			frappe.db.set_value("Desktop Icon", name, "hidden", 0, update_modified=False)
	frappe.db.set_default(DESK_HIDDEN_KEY, "[]")
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")


# Date: 2026-10-24
# Hides the desk tiles that EVision replaces. Written straight to the database (like
# restrict_desktop_icons) so a standard icon's JSON in another app is never rewritten.
def hide_replaced_icons():
	for name in HIDDEN_ICONS:
		if frappe.db.exists("Desktop Icon", name):
			frappe.db.set_value("Desktop Icon", name, "hidden", 1, update_modified=False)
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")


# Date: 2026-10-09
# Replaces a sidebar's rows (adding the layout defaults every row needs) and saves it.
def set_sidebar_items(sidebar, items):
	for item in items:
		# 2026-10-29: links are children of the Section Break above them (child = 1); with child = 0
		# Frappe drew every link at the top level, so the section headings never showed.
		item.update({"child": 0 if item.get("type") == "Section Break" else 1, "collapsible": 1,
			"indent": 0, "keep_closed": 0, "show_arrow": 0})
	sidebar.set("items", items)
	sidebar.save(ignore_permissions=True)


# Date: 2026-10-09
# Creates/updates one Workspace Sidebar with the given items and the desktop tile that opens it,
# visible to TILE_ROLES.
# 2026-10-29: `roles` (default TILE_ROLES) and `idx` (place on the desk) per module tile.
def make_tile(name, items, icon, color, roles=None, idx=None):
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
	if idx is not None and tile.meta.has_field("idx"):
		tile.idx = idx
	tile.set("roles", [{"role": r} for r in (roles or TILE_ROLES) if frappe.db.exists("Role", r)])
	tile.save(ignore_permissions=True)
