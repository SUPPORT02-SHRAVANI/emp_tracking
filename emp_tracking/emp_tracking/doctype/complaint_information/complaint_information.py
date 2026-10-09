# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Complaint Information: server code
#
# How this file works
#   Runs on the server every time a complaint is saved, and serves the mobile app.
#     1. validate() fills empty fields from the chosen LINKID (Network Link) and Site, and
#        checks that both are on the complaint's node.
#     2. It then enforces the operator rules: only Airtel has an incident number, and each
#        operator allows only its own complaint types.
#     3. field_job_action() lets a Rider or Splicer accept or reject an assigned complaint
#        from the EmployeeTracker mobile app.
#
# Change log
#   2026-09-26  File created with the doctype.
#   2026-09-30  Complaint logic added (fill from link, operator rules, mobile accept/reject).
#               Date taken from the git commit "complaint type added".
#   2026-10-07  fill_from_site() added with the Site master (one node has many sites).
#   2026-10-07  Added this header, a description on every function, and a date on each.
#   2026-10-08  Node ID links to the Node master. The Site field is the Society / Building;
#               society_name is a hidden copy of the Site's name.
#   2026-10-09  OH maintenance flow (client's complaint sheet):
#               - Operators Gazon, GBPS, Powergrid, Jio, Sumashilp, Hathway, Other; link types
#                 ILL, LMC and Transport for Airtel and Vodafone.
#               - Registered By / Closed By (NOC executive) and the Team Leader filled in.
#               - Times stamped by the workflow: Call Assigned (team assigned), EVisions closed
#                 (Fiber Restored), Company closed (Confirm Restored, editable).
#               - Link Status follows the workflow step (NOC can still pick a finer status).
#               - Worked out on save: delay in aligning the team, EVisions / Company MTTR,
#                 SLA In/Out (4 hours), waiting for confirmation, aging.
#               - update_open_aging() runs hourly (hooks.py) for open complaints.
#   2026-10-09  Transport removed as a link type: the client counts it as Backbone.
# ---------------------------------------------------------------------------------------------

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.workflow import apply_workflow
from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds

# Workflow actions a Rider/Splicer can take from the EmployeeTracker mobile app.
APP_ACTIONS = ("Accept", "Reject")
AWAITING_ACCEPTANCE = "Assigned to Maintenance Team"

# Complaint types each operator uses. Only Airtel gives an incident number; Railtel has no type.
# Operators not listed here (Gazon, Jio, ...) may use any type.
# 2026-10-09: ILL and LMC added for Airtel and Vodafone (Transport = Backbone).
OPERATOR_TYPES = {
	"Airtel": ("Backbone", "FTTH", "ILL", "LMC"),
	"Vodafone": ("Backbone", "Small Cell", "ILL", "LMC"),
	"Railtel": (),
}

# EVisions and company SLA: restored within this many hours = "In".
SLA_HOURS = 4

# Link Status set when the complaint reaches a workflow step.
STATE_LINK_STATUS = {
	"New": "NEED TO ASSIGN",
	"NOC Verification": "NEED TO ASSIGN",
	"Assigned to Area Manager": "NEED TO ASSIGN",
	"Rejected": "NEED TO ASSIGN",
	"Assigned to Maintenance Team": "ASSIGNED",
	"Accepted": "ASSIGNED",
	"In Progress": "WIP",
	"Fiber Restored": "RESTORED",
	"Awaiting Operator Confirmation": "CONFIRMATION PENDING",
	"Resolved": "RESTORED",
}

# Steps after which the complaint is no longer open.
DONE_STATES = ("Resolved", "Closed")


class ComplaintInformation(Document):
	# Date: 2026-09-30
	def validate(self):
		"""Runs before every save: fill from the link and site, then check the operator rules.

		2026-10-09: also records who registered / closed it, stamps the workflow times, moves
		the Link Status along and works out MTTR, SLA and aging.
		"""
		self.fill_from_link()
		self.fill_from_site()
		self.validate_operator_fields()
		self.set_people()
		self.stamp_workflow_times()
		self.set_times_and_sla()

	# Date: 2026-10-09
	def set_people(self):
		"""Registered By on creation, Closed By on closing (both the NOC user's name), and the team leader."""
		if not self.registered_by:
			self.registered_by = frappe.utils.get_fullname(self.owner or frappe.session.user)
		if self.workflow_state == "Closed" and not self.closed_by:
			self.closed_by = frappe.utils.get_fullname(frappe.session.user)
		self.team_leader_name = (
			frappe.db.get_value("Maintenance Team", self.maintenance_team, "team_leader_name") if self.maintenance_team else None
		)

	# Date: 2026-10-09
	def stamp_workflow_times(self):
		"""When the workflow step changes: stamp its time and move the Link Status along."""
		before = self.get_doc_before_save()
		previous = before.workflow_state if before else None
		if self.workflow_state == previous:
			return
		now = now_datetime()
		if self.workflow_state == AWAITING_ACCEPTANCE and not self.call_assigned_on:
			self.call_assigned_on = now
		if self.workflow_state == "Fiber Restored" and not self.evision_closed_on:
			self.evision_closed_on = now
		if self.workflow_state == "Resolved" and not self.company_closed_on:
			self.company_closed_on = now
		if self.workflow_state in STATE_LINK_STATUS:
			self.link_status = STATE_LINK_STATUS[self.workflow_state]
		if self.workflow_state == "Closed" and self.request_type == "Termination":
			self.link_status = "TERMINATION CLOSE"

	# Date: 2026-10-09
	def set_times_and_sla(self):
		"""Durations (in seconds) from the received time, and SLA In/Out against SLA_HOURS."""
		received = self.complaint_date_and_time
		self.delay_in_assigning = seconds_between(received, self.call_assigned_on)
		self.evision_mttr = seconds_between(received, self.evision_closed_on)
		self.company_mttr = seconds_between(received, self.company_closed_on)
		self.waiting_for_confirmation = seconds_between(self.evision_closed_on, self.company_closed_on)
		self.evision_sla = sla(self.evision_mttr)
		self.company_sla = sla(self.company_mttr)
		if self.workflow_state in DONE_STATES:
			self.aging = self.company_mttr or self.evision_mttr
		else:
			self.aging = seconds_between(received, now_datetime())
		if self.workflow_state == "Closed" and not (self.rfo and self.rfo_type):
			frappe.throw(_("Fill Reason for Outage (RFO) and RFO Type before closing"))

	# Date: 2026-10-07 (added with the Site master: one node has many sites)
	def fill_from_site(self):
		"""The Society / Building (Site) belongs to one node: check it against the Node ID.

		Stops the save if the site is on a different node than the complaint. Otherwise fills
		the Node ID when empty and copies the site's name into the hidden society_name.
		2026-10-08: with no Site, a building name from the LINKID that matches a site on the
		node sets it; society_name now always follows the Site.
		"""
		if not self.site and self.node_id and self.society_name:
			self.site = frappe.db.get_value("Site", {"node": self.node_id, "site_name": self.society_name}, "name")
		if not self.site:
			return
		site = frappe.db.get_value("Site", self.site, ["site_name", "node"], as_dict=True)
		if not site:
			return
		if self.node_id and (site.node or "").upper() != self.node_id:
			frappe.throw(
				_("Site {0} is on node {1}, but this complaint is for node {2}. Pick a site on node {2}.").format(
					site.site_name, site.node or _("(none)"), self.node_id
				)
			)
		if not self.node_id and site.node:
			self.node_id = site.node.upper()
		self.society_name = site.site_name

	# Date: 2026-09-30
	def fill_from_link(self):
		"""Copy what the LINKID's Network Link knows into fields NOC left empty."""
		if self.node_id:
			self.node_id = self.node_id.strip().upper()
		if self.linkid:
			link = frappe.db.get_value(
				"Network Link", self.linkid, ["network_type", "section", "society_building", "area", "node_id"], as_dict=True
			)
			if link:
				# The LINKID must be on the node named in the operator's message.
				if self.node_id and (link.node_id or "").upper() != self.node_id:
					frappe.throw(
						_("LINKID {0} is on node {1}, but this complaint is for node {2}. Pick a link on node {2}.").format(
							self.linkid, link.node_id or _("(none)"), self.node_id
						)
					)
				if not self.node_id and link.node_id:
					self.node_id = link.node_id.upper()
				allowed = OPERATOR_TYPES.get(self.operatorcustomer)
				if not self.complaint_type and link.network_type and (allowed is None or link.network_type in allowed):
					self.complaint_type = link.network_type
				if not self.section and link.section:
					self.section = link.section
				if not self.society_name and link.society_building:
					self.society_name = link.society_building
				if not self.area and link.area:
					self.area = link.area
		if self.area and not self.area_manager:
			self.area_manager = frappe.db.get_value("Area", self.area, "area_manager")

	# Date: 2026-09-30
	def validate_operator_fields(self):
		"""Airtel needs an incident number; other operators have none. The type must suit the operator."""
		allowed = OPERATOR_TYPES.get(self.operatorcustomer)
		if allowed is None:
			return
		if self.operatorcustomer == "Airtel":
			if not (self.incident_number or "").strip():
				frappe.throw(_("Airtel INC No. is required for Airtel complaints"))
		else:
			self.incident_number = None
		if not allowed:
			self.complaint_type = None
		elif self.complaint_type and self.complaint_type not in allowed:
			frappe.throw(
				_("Complaint Type for {0} must be {1}").format(self.operatorcustomer, _(" or ").join(allowed))
			)


# Date: 2026-10-09
def seconds_between(start, end):
	"""Seconds from start to end (None if either is missing or end is before start)."""
	if not (start and end):
		return None
	seconds = time_diff_in_seconds(get_datetime(end), get_datetime(start))
	return int(seconds) if seconds >= 0 else None


# Date: 2026-10-09
def sla(seconds):
	"""'In' if restored within SLA_HOURS, 'Out' if later, empty while not restored."""
	if seconds is None:
		return None
	return "In" if seconds <= SLA_HOURS * 3600 else "Out"


# Date: 2026-10-09
def update_open_aging():
	"""Hourly (hooks.py): refresh Aging of complaints that are still open, without touching 'modified'."""
	now = now_datetime()
	open_complaints = frappe.get_all(
		"Complaint Information",
		filters={"workflow_state": ["not in", DONE_STATES], "complaint_date_and_time": ["is", "set"]},
		fields=["name", "complaint_date_and_time"],
	)
	for row in open_complaints:
		frappe.db.set_value(
			# Duration columns can't be NULL (a received time in the future gives None).
			"Complaint Information", row.name, "aging", seconds_between(row.complaint_date_and_time, now) or 0,
			update_modified=False,
		)


# Date: 2026-09-30
@frappe.whitelist(methods=["POST"])
def field_job_action(complaint, employee, action, reason=None):
	"""Accept or reject a complaint from the mobile app on behalf of its Rider or Splicer."""
	if action not in APP_ACTIONS:
		frappe.throw(_("Unknown action {0}").format(action))

	doc = frappe.get_doc("Complaint Information", complaint)
	doc.check_permission("read")
	if employee not in (doc.rider, doc.splicer):
		frappe.throw(_("{0} is not the Rider or Splicer on {1}").format(employee, complaint), frappe.PermissionError)
	if doc.workflow_state != AWAITING_ACCEPTANCE:
		frappe.throw(_("{0} is no longer waiting for acceptance (now: {1})").format(complaint, doc.workflow_state))

	reason = (reason or "").strip()
	if action == "Reject":
		if not reason:
			frappe.throw(_("A rejection reason is required"))
		doc.db_set("rejection_reason", reason)

	# The workflow lets only the Maintenance Agent role press Accept/Reject, but the app signs in
	# as one shared API user. The checks above stand in for that role, so run the transition as
	# Administrator and record who actually did it.
	session_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		doc = apply_workflow(frappe.get_doc("Complaint Information", complaint), action)
	finally:
		frappe.set_user(session_user)

	role = _("Splicer") if employee == doc.splicer else _("Rider")
	note = _("{0} from the mobile app by {1} ({2})").format(action, employee, role)
	doc.add_comment("Info", note + (f": {reason}" if reason else ""))
	return {"workflow_state": doc.workflow_state, "assignment_status": doc.assignment_status}
