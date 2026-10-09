# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""Who may open which dashboard, and whose data each user may see.

Every dashboard query goes through `get_scope`, so a user can never read
employees outside it, whatever filters the browser sends.
"""

import frappe
from frappe import _

TEAM_LEAD = "Team Lead"
FINANCE_MANAGER = "Finance Manager"
MANAGEMENT = "Management"
CUSTOM_ROLES = (TEAM_LEAD, FINANCE_MANAGER, MANAGEMENT)

ADMIN_ROLES = {"System Manager", "Administrator"}
HR_ROLES = {"HR Manager", "HR User"}
FINANCE_ROLES = {FINANCE_MANAGER, "Accounts Manager"}
# Roles that see every active employee; everyone else sees their team or only themselves.
COMPANY_WIDE_ROLES = ADMIN_ROLES | HR_ROLES | FINANCE_ROLES | {MANAGEMENT}

LEADERS = {TEAM_LEAD, MANAGEMENT} | HR_ROLES | ADMIN_ROLES

# Display order is the order of this dict. `roles=None` means every desk user.
DASHBOARDS = {
	"employee": {"label": "My Dashboard", "roles": None},
	"team": {"label": "Team", "roles": LEADERS},
	"hr": {"label": "HR", "roles": HR_ROLES | ADMIN_ROLES | {MANAGEMENT}},
	"field": {"label": "Field Operations", "roles": LEADERS},
	"tasks": {"label": "Tasks", "roles": LEADERS | {"Projects Manager"}},
	"claims": {"label": "Petrol & Claims", "roles": LEADERS | FINANCE_ROLES},
	"performance": {"label": "Performance", "roles": LEADERS},
	"management": {"label": "Management", "roles": ADMIN_ROLES | {MANAGEMENT}},
	"exceptions": {"label": "Exceptions", "roles": LEADERS | FINANCE_ROLES},
}

# Where each kind of user lands when they open the page without picking a dashboard.
LANDING = (
	(ADMIN_ROLES | {MANAGEMENT}, "management"),
	(HR_ROLES, "hr"),
	(FINANCE_ROLES, "claims"),
	({TEAM_LEAD}, "team"),
)

# Which approvals each role may decide. Team leads decide only for their own team,
# because every action also checks the record's employee against the user's scope.
APPROVERS = {
	"Leave Application": {TEAM_LEAD, "Leave Approver"} | HR_ROLES | ADMIN_ROLES,
	"Expense Claim": {TEAM_LEAD, "Expense Approver"} | FINANCE_ROLES | ADMIN_ROLES,
	"Attendance Request": {TEAM_LEAD} | HR_ROLES | ADMIN_ROLES,
	"Task": {TEAM_LEAD, MANAGEMENT, "Projects Manager"} | ADMIN_ROLES,
}


def roles_of(user=None):
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	if user == "Administrator":
		roles.add("Administrator")
	return roles


def allowed_dashboards(roles):
	return [key for key, d in DASHBOARDS.items() if d["roles"] is None or roles & d["roles"]]


def landing_dashboard(roles):
	allowed = allowed_dashboards(roles)
	for role_set, key in LANDING:
		if roles & role_set and key in allowed:
			return key
	return "employee"


def check_dashboard(key, roles):
	if key not in DASHBOARDS:
		frappe.throw(_("Unknown dashboard {0}").format(key))
	if key not in allowed_dashboards(roles):
		frappe.throw(
			_("You are not permitted to open the {0} dashboard").format(_(DASHBOARDS[key]["label"])),
			frappe.PermissionError,
		)


def own_employee(user=None):
	return frappe.db.get_value("Employee", {"user_id": user or frappe.session.user, "status": "Active"}, "name")


def get_scope(user=None):
	"""Return (level, own employee, employee ids the user may see)."""
	user = user or frappe.session.user
	roles = roles_of(user)
	own = own_employee(user)

	if roles & COMPANY_WIDE_ROLES:
		return "all", own, frappe.get_all("Employee", filters={"status": "Active"}, pluck="name")
	if TEAM_LEAD in roles and own:
		return "team", own, [own, *team_of(own)]
	return "self", own, [own] if own else []


def team_of(leader):
	"""Everyone reporting to `leader`, directly or through other leads."""
	children = {}
	for r in frappe.get_all("Employee", filters={"status": "Active"}, fields=["name", "reports_to"]):
		children.setdefault(r.reports_to, []).append(r.name)

	out, queue = [], list(children.get(leader, []))
	while queue:
		emp = queue.pop()
		if emp in out or emp == leader:
			continue
		out.append(emp)
		queue.extend(children.get(emp, []))
	return out


def can_approve(doctype, roles):
	return bool(roles & APPROVERS.get(doctype, set()))
