# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.workflow import apply_workflow

# Workflow actions a Rider/Splicer can take from the EmployeeTracker mobile app.
APP_ACTIONS = ("Accept", "Reject")
AWAITING_ACCEPTANCE = "Assigned to Maintenance Team"

# Complaint types each operator uses. Only Airtel gives an incident number; Railtel has no type.
OPERATOR_TYPES = {
	"Airtel": ("Backbone", "FTTH"),
	"Vodafone": ("Backbone", "Small Cell"),
	"Railtel": (),
}


class ComplaintInformation(Document):
	def validate(self):
		self.fill_from_link()
		self.validate_operator_fields()

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

	def validate_operator_fields(self):
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
