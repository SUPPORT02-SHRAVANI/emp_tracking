app_name = "emp_tracking"
app_title = "Emp Tracking"
app_publisher = "milind"
app_description = "Tracking"
app_email = "support02@softworld.co.in"
app_license = "mit"

# Apps
# ------------------

# 2026-10-24: Site and Complaint Information link to GIS Node, which comes from FTTH Tracker
# (the Node master was merged into it), so FTTH Tracker must be installed first.
# 2026-11-24: the FTTH Tracker code now lives in this app (module "FTTH", emp_tracking/ftth/),
# so ftth_tracker is no longer a separate app and is not required.
# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "emp_tracking",
# 		"logo": "/assets/emp_tracking/logo.png",
# 		"title": "Emp Tracking",
# 		"route": "/emp_tracking",
# 		"has_permission": "emp_tracking.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# 2026-11-02: EVision design layer (tokens, skeleton / empty states, stage tracker) and its
# helpers. Plain files served from public/, so they need no bench build. emp_tracking is only
# installed on the Evision site, so other sites on the bench do not load them.
# 2026-11-02: "?v=" makes browsers fetch a changed file (assets are cached for 12 hours); raise
# EV_ASSET_VERSION whenever evision.css / evision.js change.
# 2026-11-26: "20261126a" dark-mode token fix; "20261126b" NOC report cell styles / formatter;
# "20261126c" light-mode tokens; "20261126d" month bands on charts;
# "20261126e" NOC reports full screen; "20261126f"/"g" report chart axis options; "20261126h" fluid report tables;
# "20261126i" SLA % colours on any _pct column; "20261126j" whole-number chart axis;
# "20261126k" fluid tables removed
EV_ASSET_VERSION = "20261126k"
app_include_css = f"/assets/emp_tracking/css/evision.css?v={EV_ASSET_VERSION}"
app_include_js = f"/assets/emp_tracking/js/evision.js?v={EV_ASSET_VERSION}"

# include js, css files in header of web template
# web_include_css = "/assets/emp_tracking/css/emp_tracking.css"
# web_include_js = "/assets/emp_tracking/js/emp_tracking.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "emp_tracking/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# 2026-10-24: Site Diagram on the GIS Node form (moved from the merged Node doctype)
# 2026-10-31: FTTH Work Order gets New Project's "Send Mail to Planning" / "Create Network Link"
# 2026-11-20: Employee form shows the company-wise Employee Code (IPT-/AUT-/INF-) when a company is picked
doctype_js = {
	"GIS Node": "public/js/gis_node.js",
	"FTTH Work Order": "public/js/ftth_work_order.js",
	"Employee": "public/js/employee.js",
}
# 2026-11-02: FTTH Work Order list: stage pipeline strip and clearer columns (extends FTTH
# Tracker's own list settings; runs after them).
# 2026-11-25: Shift Assignment list: "Weekly Roster" button (keeps HRMS's own list onload).
doctype_list_js = {
	"FTTH Work Order": "public/js/ftth_work_order_list.js",
	"Shift Assignment": "public/js/shift_assignment_list.js",
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "emp_tracking/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "emp_tracking.utils.jinja_methods",
# 	"filters": "emp_tracking.utils.jinja_filters"
# }

# Installation
# ------------

# 2026-11-24: FTTH roles and FTTH Settings defaults (moved here from the ftth_tracker app)
before_install = "emp_tracking.ftth.install.before_install"
after_install = "emp_tracking.ftth.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "emp_tracking.uninstall.before_uninstall"
# after_uninstall = "emp_tracking.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "emp_tracking.utils.before_app_install"
# after_app_install = "emp_tracking.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "emp_tracking.utils.before_app_uninstall"
# after_app_uninstall = "emp_tracking.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "emp_tracking.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "emp_tracking.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["emp_tracking.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"emp_tracking.tasks.all"
# 	],
# 	"daily": [
# 		"emp_tracking.tasks.daily"
# 	],
# 	"hourly": [
# 		"emp_tracking.tasks.hourly"
# 	],
# 	"weekly": [
# 		"emp_tracking.tasks.weekly"
# 	],
# 	"monthly": [
# 		"emp_tracking.tasks.monthly"
# 	],
# }

# 2026-10-09: after every migrate (also on Frappe Cloud) rebuild the roles, desk tiles and the
# OverHead menu, so nobody has to run apply_access by hand after a deploy.
after_migrate = [
	"emp_tracking.emp_tracking.page.workforce_dashboard.setup.after_migrate",
	# 2026-10-26: Fiber Store (cable drum inward / outward on ERPNext stock) and its dashboard
	"emp_tracking.fiber_store.after_migrate",
	# 2026-10-29: New Project roles (Project Head, Area Manager, Fiber / Splicing Team) on FTTH Work Order
	"emp_tracking.ftth_stages.after_migrate",
	# 2026-11-20: Company "Employee Code Prefix" field + IPT / AUT / INF defaults (Employee Code series)
	"emp_tracking.overrides.employee.after_migrate",
	# 2026-11-23: Shift Types for attendance from mobile-app punches (HRMS Auto Attendance)
	"emp_tracking.app_attendance.after_migrate",
	# 2026-11-23: Remarks field on Additional Salary (salary Advance entries, like the Excel)
	"emp_tracking.payroll_advance.after_migrate",
	# 2026-11-24: Company "Name on Payslip" + "Company Stamp" fields (RKBG Payslip Classic print format)
	"emp_tracking.payslip_print.after_migrate",
	# 2026-11-24: HR setup shipped as JSON (Salary Components, Leave Types, Salary Structures,
	# HR / Payroll Settings, RKBG IPTECH Letter Head); only created where missing
	"emp_tracking.hr_setup.after_migrate",
	# 2026-11-24: FTTH Manager / FTTH User roles (was ftth_tracker's after_migrate)
	"emp_tracking.ftth.install.ensure_roles",
]

# 2026-10-26: Fiber Store stock entries: check drum readings, fill the metres the dashboard sums
doc_events = {
	"Stock Entry": {"validate": "emp_tracking.fiber_store.stock_entry_validate"},
	# 2026-10-29: FTTH Work Order stage changes notify the next person, like New Project
	# 2026-10-31: the same hook makes the Network Link when the HOTO Date is entered
	"FTTH Work Order": {"on_update": "emp_tracking.ftth_stages.on_update"},
	# 2026-11-20: company-wise Employee Code (IPT-####, AUT-####, INF-####) given on insert
	# 2026-11-23: Mode of Attendance "Mobile App" sets / clears the Default Shift (app_attendance.py)
	"Employee": {
		"before_insert": "emp_tracking.overrides.employee.before_insert",
		"before_save": "emp_tracking.app_attendance.employee_before_save",
	},
	# 2026-11-21: leave encashment per day = Gross / 30 when left blank (field staff encash leaves)
	"Salary Structure Assignment": {
		"before_validate": "emp_tracking.overrides.salary_structure_assignment.before_validate"
	},
}

# 2026-10-09: refresh the Aging of open complaints every hour.
scheduler_events = {
	"hourly": [
		"emp_tracking.emp_tracking.doctype.complaint_information.complaint_information.update_open_aging"
	],
}

# Testing
# -------

# before_tests = "emp_tracking.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "emp_tracking.custom.task.CustomTaskMixin"
# }

# 2026-10-21: employees with "Allow Punch From Anywhere" skip the shift location radius check.
extend_doctype_class = {
	"Employee Checkin": ["emp_tracking.overrides.employee_checkin.EmployeeCheckinMixin"],
}

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "emp_tracking.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# 2026-10-24: Sites and Complaints in GIS Node's Connections panel (Node merged into GIS Node)
override_doctype_dashboards = {
	"GIS Node": ["emp_tracking.overrides.gis_node.get_dashboard_data"],
}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["emp_tracking.utils.before_request"]
# after_request = ["emp_tracking.utils.after_request"]

# Job Events
# ----------
# before_job = ["emp_tracking.utils.before_job"]
# after_job = ["emp_tracking.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"emp_tracking.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


# Fixtures
# --------
# HD Ticket "Complaint Information" custom fields and the Default ticket template rows
# that expose them in the Helpdesk UI. Exported to emp_tracking/fixtures/ so they are
# stored in git and re-created on any install/migrate.
# 2026-11-24: doctypes whose Customize Form changes (Property Setters, module "Emp Tracking") ship as fixtures
HR_FORM_DOCTYPES = [
    "Employee", "Attendance", "Expense Claim", "Expense Claim Detail", "Expense Taxes and Charges", "Gratuity",
    "Leave Allocation", "Leave Application", "Leave Encashment", "Payroll Entry", "Salary Slip",
]

fixtures = [
    {"dt": "Role", "filters": [["name", "in", ["NOC Head", "Area Manager", "Maintenance Agent", "Project Head", "Fiber Team",
        "Splicing Team"]]]},
    {"dt": "Workflow State", "filters": [["name", "in", [
        "New", "NOC Verification", "Assigned to Area Manager", "Assigned to Maintenance Team", "Accepted",
        "Rejected", "In Progress", "Restoration", "Fiber Restored", "Awaiting Operator Confirmation",
        "Resolved", "Closed"]]]},
    {"dt": "Workflow Action Master", "filters": [["name", "in", [
        "Start Verification", "Assign to Area Manager", "Assign Maintenance Team", "Accept", "Reject", "Reassign",
        # 2026-10-09: restoration and closure steps.
        "Start Work", "Fiber Restored", "Inform Operator", "Confirm Restored", "Not Restored", "Close"]]]},
    {"dt": "Workflow", "filters": [["name", "=", "OHP Maintenance Workflow"]]},
    {"dt": "Workspace Sidebar", "filters": [["name", "=", "Helpdesk NOC"]]},
    {"dt": "Desktop Icon", "filters": [["name", "=", "Helpdesk NOC"]]},
    # 2026-11-20: Employee form laid out in the 13 sections of the employee master sheet, made with
    # Customize Form (Custom Fields + Property Setters, module "Emp Tracking"). After changing the
    # Employee form in Customize Form, set Module = Emp Tracking on new rows and re-export fixtures.
    {"dt": "Custom Field", "filters": [["dt", "=", "Employee"], ["module", "=", "Emp Tracking"]]},
    # 2026-11-24: + the HR / Payroll form and list settings made in Customize Form (naming series,
    # Salary Slip / Payroll Entry list columns, track changes, hidden accounting dimensions). Their
    # Property Setters carry module "Emp Tracking" too. Masters and settings: see hr_setup.py.
    {"dt": "Property Setter", "filters": [["doc_type", "in", HR_FORM_DOCTYPES], ["module", "=", "Emp Tracking"]]},
]
