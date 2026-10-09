# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# New Project: server code
#
# How this file works
#   A New Project follows the project sheet from work order to RFS. Each colour block of the
#   sheet is one tab of the form and belongs to one owner. Field-level permissions (set in
#   new_project.json) decide who may edit which block:
#     permlevel 1 = Project Head, 2 = Area Manager, 3 = Fiber Team, 4 = Splicing Team.
#   Every time a project is saved, this file:
#     1. works out the B End Status (issue raised -> mail sent -> approved),
#     2. checks the Fiber Team has no employee twice,
#     3. works out the Stage, i.e. the first block of the sheet that is not filled yet,
#     4. sends a bell notification to whoever has to act when the Stage changes,
#        and a WhatsApp message to their mobile.
#   The functions at the bottom are called by the EmployeeTracker mobile app so the splicing
#   team can upload their photos from the phone.
#
# Change log
#   2026-10-07  Created with the 23 project fields.
#   2026-10-07  B End issue flow: status, notification to Project Head, then to Area Manager.
#   2026-10-07  Fiber Team table with duplicate-employee check.
#   2026-10-07  Stage field for the whole sheet; one notification per stage change.
#   2026-10-07  Mobile app endpoints: splicing_jobs and upload_splicing_snap.
#   2026-10-07  Rider moved from the Fiber Team to the Splicing Team.
#   2026-10-07  Added this header and a description on every function.
#   2026-10-08  WhatsApp message (Meta Cloud API, see WhatsApp Settings) to the next stage's
#               people each time the Stage changes.
#   2026-10-08  Added the project sheet's remaining columns: City, Link ID, Unique ID, Fiber
#               Type, Vendor Name, Evision Distance, Work Completed Date, Supervisor Available,
#               Remark, Suggestion for Future and two Re-work Required Dates.
#   2026-10-09  OH Project flow (client's project tracker sheet):
#               - Customer, Link Type, Project Type, WO details, survey date/type, site access,
#                 fiber dates, termination, AT & HOTO and Billing columns.
#               - Stages after RFS: "AT & HOTO by Project Head" -> "Billing by Accounts" -> "Closed";
#                 "Cancelled" when the Project Head ticks Project Cancelled. "RFS Done" is gone.
#               - Link ID made automatically from the Survey Date (YYYYMM + running number).
#               - Team, Manager and Supervisor copied from the chosen EVisions Team / Vendor.
#   2026-10-09  Area Manager = Supervisor: Supervisor shows the Area Manager; an EVisions Team's
#               leader becomes the Area Manager when none is chosen.
#   2026-10-09  Splicing Team is a table of Rider + Splicer pairs (row count = Splicing Team
#               Required No); the single Rider / Splicer / Assistant Splicer fields are removed.
#               Notifications, WhatsApp and the mobile app's splicing_jobs read the table.
#               - Worked out on save: Difference in Distance, RFS Month, Final Amount, Site Status.
#               - On the HOTO Date a Network Link (LINKID) is created so the link moves to
#                 maintenance.
# ---------------------------------------------------------------------------------------------

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document
from frappe.utils import flt, getdate

APPROVED = "Approved"

# The project moves through these stages in order; each one names who has to act.
SURVEY = "Survey by Area Manager"
B_END_APPROVAL = "B End Approval by Project Head"
FIBER_TEAM_ASSIGNMENT = "Fiber Team Assignment by Area Manager"
FIBER_WORK = "Fiber Work by Fiber Team"
SPLICER_ASSIGNMENT = "Splicer Assignment by Area Manager"
SPLICING = "Splicing by Splicing Team"
FINAL_DETAILS = "Final Details by Project Head"
AT_HOTO = "AT & HOTO by Project Head"
BILLING = "Billing by Accounts"
CLOSED = "Closed"
CANCELLED = "Cancelled"

# Payment statuses that end the Billing stage.
PAYMENT_DONE = ("Fully Received", "Cancelled/ Written Off")


class NewProject(Document):
	# Date: 2026-10-07
	def validate(self):
		"""Runs before every save: refresh the B End Status, check the Fiber Team, set the Stage.

		2026-10-09: also copies the team details, makes the Link ID and works out the calculated
		fields (difference in distance, RFS month, final amount, site status).
		"""
		self.set_b_end_status()
		self.validate_fiber_team()
		self.validate_splicing_team()
		self.set_team_details()
		self.set_link_id()
		self.set_calculated_fields()
		self.stage = self.get_stage()

	# Date: 2026-10-07
	def on_update(self):
		"""Runs after every save: if the Stage changed, notify whoever has to act next.

		2026-10-09: on the HOTO Date the Network Link for maintenance is created.
		"""
		before = self.get_doc_before_save()
		if not before or before.stage != self.stage:
			self.notify_stage_owner()
			self.whatsapp_stage_owner(before.stage if before else None)
		if self.hoto_date and not self.network_link and not self.is_cancelled:
			self.make_network_link()

	# Date: 2026-10-09
	def set_team_details(self):
		"""Copy Team and Manager from the chosen EVisions Team, or the vendor's name.

		The Area Manager is the Supervisor (confirmed by the client 2026-10-09): an EVisions
		Team's leader becomes the Area Manager when none is chosen, and Supervisor always shows
		the Area Manager's name (also on vendor jobs, which an Area Manager supervises).
		"""
		leader_name = None
		if self.ownership == "EVisions" and self.evision_team:
			team = frappe.db.get_value(
				"Maintenance Team", self.evision_team, ["team_leader", "team_leader_name", "manager_name"], as_dict=True
			) or {}
			self.team = self.evision_team
			self.manager = team.get("manager_name") or self.manager
			leader_name = team.get("team_leader_name")
			if not self.area_manager and team.get("team_leader"):
				self.area_manager = frappe.db.get_value("Employee", team.team_leader, "user_id")
		elif self.ownership == "Vendor" and self.project_vendor:
			self.team = self.project_vendor
			self.vendor_name = self.vendor_name or self.project_vendor
		self.supervisor_name = frappe.utils.get_fullname(self.area_manager) if self.area_manager else leader_name

	# Date: 2026-10-09
	def set_link_id(self):
		"""Give the project its EVisions Link ID once the survey is dated.

		Format: YYYYMM of the Survey Date + running number in that month, e.g. 202610001.
		A Link ID typed in by hand is kept.
		"""
		if self.link_id or not self.survey_date:
			return
		prefix = getdate(self.survey_date).strftime("%Y%m")
		used = frappe.get_all("New Project", filters={"link_id": ["like", f"{prefix}%"]}, pluck="link_id")
		used += frappe.get_all("Network Link", filters={"name": ["like", f"{prefix}%"]}, pluck="name")
		numbers = [int(value[len(prefix):]) for value in used if value[len(prefix):].isdigit()]
		self.link_id = f"{prefix}{(max(numbers) if numbers else 0) + 1:03d}"

	# Date: 2026-10-09
	def set_calculated_fields(self):
		"""Fields worked out from others: Difference in Distance, RFS Month, Final Amount, Site Status."""
		# Number columns can't be empty in the database, so "not known yet" is 0.
		if self.final_distance and self.survey_distance_done_by_area_manager:
			self.distance_difference = flt(self.final_distance) - flt(self.survey_distance_done_by_area_manager)
		else:
			self.distance_difference = 0
		self.rfs_month = getdate(self.rfs_date).strftime("%b-%y") if self.rfs_date else None
		self.final_amount = flt(self.base_amount) + flt(self.gst_amount)
		if self.is_cancelled:
			self.site_status = "Cancelled"
		else:
			self.site_status = "Completed" if self.rfs_date else "WIP"

	# Date: 2026-10-09
	def make_network_link(self):
		"""Create the Network Link (LINKID) for this site so complaints can be traced to it.

		Runs on the HOTO Date. If something the Network Link needs is missing, the Project Head
		is told what to fill; the link is then created on the next save.
		"""
		if frappe.db.exists("Network Link", self.link_id or ""):
			self.db_set("network_link", self.link_id, update_modified=False)
			return
		network_type = self.link_type or "FTTH"
		responsibility = self.ownership or "EVisions"
		missing = []
		if not self.link_id:
			missing.append(_("Link ID (fill the Survey Date)"))
		if not self.area:
			missing.append(_("Area"))
		if responsibility == "EVisions" and not self.evision_team:
			missing.append(_("EVisions Team"))
		if responsibility == "Vendor" and not self.project_vendor:
			missing.append(_("Vendor"))
		if not self.end_location_name:
			missing.append(_("End Location Name"))
		if missing:
			frappe.msgprint(
				_("The Network Link for maintenance could not be created yet. Please fill: {0}").format(", ".join(missing)),
				title=_("Handover to Maintenance"),
				indicator="orange",
			)
			return

		lat, lng = parse_lat_long(self.end_location_lat_long)
		link = frappe.get_doc({
			"doctype": "Network Link",
			"linkid": self.link_id,
			"network_type": network_type,
			"status": "Active",
			"operator": operator_of(self.customer),
			"customer": self.customer,
			"project": self.name,
			"section": self.end_location_name if network_type != "FTTH" else None,
			"society_building": self.end_location_name,
			"location": self.end_location_name,
			"area": self.area,
			"latitude": lat,
			"longitude": lng,
			"maintenance_responsibility": responsibility,
			"maintenance_team": self.evision_team if responsibility == "EVisions" else None,
			"mapped_vendor": self.project_vendor if responsibility == "Vendor" else None,
			"operator_link_id": self.unique_id,
			"gis_node_id": self.gis,
		})
		# The Project Head may not have rights on Network Link; the checks above stand in for them.
		link.insert(ignore_permissions=True)
		self.db_set("network_link", link.name, update_modified=False)
		frappe.msgprint(
			_("Network Link {0} created: this site is now handed over to maintenance.").format(link.name),
			indicator="green",
			alert=True,
		)

	# Date: 2026-10-07
	def set_b_end_status(self):
		"""A B End / distance issue from the Area Manager sends the project back to the Project Head."""
		if not (self.b_end_issue_or_distance_issue or "").strip():
			self.b_end_status = ""
		elif self.planning_approval_date:
			self.b_end_status = APPROVED
		elif self.mail_sent_to_planning_date:
			self.b_end_status = "Mail Sent to Planning"
		else:
			self.b_end_status = "Pending with Project Head"

	# Date: 2026-10-07
	def validate_fiber_team(self):
		"""Stop the save if the same employee is in the Fiber Team more than once."""
		seen = set()
		for row in self.fiber_team:
			if row.employee in seen:
				frappe.throw(_("Row {0}: {1} is already in the Fiber Team").format(row.idx, row.employee_name or row.employee))
			seen.add(row.employee)

	# Date: 2026-10-09
	def validate_splicing_team(self):
		"""Splicing Team rows: no employee twice, and the row count matches "Splicing Team Required No"."""
		seen = set()
		for row in self.splicing_team:
			for employee, name in ((row.rider, row.rider_name), (row.splicer, row.splicer_name)):
				if not employee:
					continue
				if employee in seen:
					frappe.throw(_("Row {0}: {1} is already in the Splicing Team").format(row.idx, name or employee))
				seen.add(employee)
		if not self.splicing_team_required_no:
			self.splicing_team_required_no = len(self.splicing_team)
		elif self.splicing_team and len(self.splicing_team) != self.splicing_team_required_no:
			frappe.throw(
				_("Splicing Team Required No is {0}, but {1} Rider + Splicer rows are filled").format(
					self.splicing_team_required_no, len(self.splicing_team)
				)
			)

	# Date: 2026-10-07
	def get_stage(self):
		"""The first part of the sheet that is not filled yet.

		2026-10-09: after the RFS Date come AT & HOTO, Billing and Closed; a cancelled project
		stops at Cancelled.
		"""
		if self.is_cancelled:
			return CANCELLED
		if self.b_end_status and self.b_end_status != APPROVED:
			return B_END_APPROVAL
		survey_done = (
			self.survey_a_end_done_by_area_manager
			and self.survey_b_end_done_by_area_manager
			and self.survey_distance_done_by_area_manager
		)
		if not survey_done:
			return SURVEY
		if not self.fiber_team:
			return FIBER_TEAM_ASSIGNMENT
		if not (self.fiber_id_and_reading_a_end_snap and self.fiber_id_and_reading_b_end_snap):
			return FIBER_WORK
		if not self.splicing_team:  # 2026-10-09: was the single Splicer field
			return SPLICER_ASSIGNMENT
		if not (self.splicing_snap_a_end and self.splicing_snap_b_end):
			return SPLICING
		if not self.rfs_date:
			return FINAL_DETAILS
		if not (self.at_status == "Done" and self.hoto_date):
			return AT_HOTO
		if self.payment_status not in PAYMENT_DONE:
			return BILLING
		return CLOSED

	# Date: 2026-10-07
	def get_stage_owners(self):
		"""Users who have to act at the current stage.

		2026-10-09: AT & HOTO goes to the Project Head, Billing to Accounts.
		"""
		if self.stage in (B_END_APPROVAL, FINAL_DETAILS, AT_HOTO):
			return users_with_role("Project Head")
		if self.stage == BILLING:
			return users_with_role("Accounts User") + users_with_role("Accounts Manager")
		if self.stage in (SURVEY, FIBER_TEAM_ASSIGNMENT, SPLICER_ASSIGNMENT):
			return [self.area_manager] if self.area_manager else users_with_role("Area Manager")
		if self.stage == FIBER_WORK:
			employees = [row.employee for row in self.fiber_team]
			return users_of_employees(employees) or users_with_role("Fiber Team")
		if self.stage == SPLICING:
			return users_of_employees(self.get_splicing_team()) or users_with_role("Splicing Team")
		return []

	# Date: 2026-10-07
	def get_splicing_team(self):
		"""Employees assigned to the splicing work: every Rider and Splicer in the Splicing Team table.

		2026-10-09: read from the table (was Rider, Splicer and Assistant Splicer fields).
		"""
		return [employee for row in self.splicing_team for employee in (row.rider, row.splicer) if employee]

	# Date: 2026-10-07
	def notify_stage_owner(self):
		"""Send a bell notification about the new Stage to its owners, except the user who saved."""
		users = [user for user in self.get_stage_owners() if user != frappe.session.user]
		if not users:
			return
		enqueue_create_notification(
			users,
			{
				"type": "Alert",
				"document_type": self.doctype,
				"document_name": self.name,
				"subject": _("{0} ({1}) is now at: {2}").format(
					self.name, self.end_location_name or self.wo or "", self.stage
				),
				"email_content": self.b_end_issue_or_distance_issue if self.stage == B_END_APPROVAL else None,
				"from_user": frappe.session.user,
			},
		)


	# Date: 2026-10-08
	def get_stage_mobiles(self):
		"""Mobile numbers of whoever has to act at the current stage.

		Fiber and splicing teams use their Employee mobile, so team members without a login
		still get the message. At Closed / Cancelled the Project Heads are told.
		(2026-10-09: was "RFS Done"; that stage is now followed by AT & HOTO and Billing.)
		"""
		if self.stage == FIBER_WORK:
			return mobiles_of_employees([row.employee for row in self.fiber_team])
		if self.stage == SPLICING:
			return mobiles_of_employees(self.get_splicing_team())
		users = users_with_role("Project Head") if self.stage in (CLOSED, CANCELLED) else self.get_stage_owners()
		return mobiles_of_users(users)

	# Date: 2026-10-08
	def whatsapp_stage_owner(self, completed_stage):
		"""WhatsApp the next stage's people that the previous stage is completed."""
		from emp_tracking.emp_tracking.doctype.whatsapp_settings.whatsapp_settings import send_template

		template = frappe.db.get_single_value("WhatsApp Settings", "project_stage_template")
		send_template(
			self.get_stage_mobiles(),
			template,
			[self.name, self.end_location_name or self.wo, completed_stage or _("Project created"), self.stage],
			reference_doctype=self.doctype,
			reference_name=self.name,
		)


# Date: 2026-10-09
def parse_lat_long(value):
	"""'18.439858, 73.895388' (comma or space separated) -> (18.439858, 73.895388); (None, None) if unreadable."""
	parts = (value or "").replace(",", " ").split()
	try:
		return float(parts[0]), float(parts[1])
	except (IndexError, ValueError):
		return None, None


# Network Link "Operator" for each customer name (matched as lower-case text inside the name).
OPERATORS = (
	("airtel", "Airtel"), ("vil", "Vodafone"), ("vodafone", "Vodafone"), ("railtel", "Railtel"),
	("gazon", "Gazon"), ("gbps", "GBPS"), ("powergrid", "Powergrid"), ("jio", "Jio"),
	("sumashilp", "Sumashilp"), ("hathway", "Hathway"),
)


# Date: 2026-10-09
def operator_of(customer):
	"""Network Link Operator for a Customer, e.g. "VIL" -> "Vodafone". Defaults to Airtel."""
	name = (customer or "").lower()
	return next((operator for key, operator in OPERATORS if key in name), "Airtel")


# Date: 2026-10-08
def mobiles_of_employees(employees):
	"""Mobile numbers (Employee "Mobile") of the given employees."""
	employees = [employee for employee in employees if employee]
	if not employees:
		return []
	return frappe.get_all("Employee", filters={"name": ["in", employees]}, pluck="cell_number")


# Date: 2026-10-08
def mobiles_of_users(users):
	"""Mobile number of each user: the User's Mobile No, else the linked Employee's Mobile."""
	numbers = []
	for user in users:
		number = frappe.db.get_value("User", user, "mobile_no") or frappe.db.get_value(
			"Employee", {"user_id": user}, "cell_number"
		)
		if number:
			numbers.append(number)
	return numbers


# Date: 2026-10-07
def users_with_role(role):
	"""All enabled users who have the given role."""
	users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent", distinct=True)
	return [user for user in users if frappe.db.get_value("User", user, "enabled")]


# Date: 2026-10-07
def users_of_employees(employees):
	"""Login users linked to the given employees (employees without a login are skipped)."""
	employees = [employee for employee in employees if employee]
	if not employees:
		return []
	users = frappe.get_all("Employee", filters={"name": ["in", employees]}, pluck="user_id")
	return [user for user in users if user]


# Which field holds the splicing photo of each end.
SPLICING_SNAP_FIELDS = {"A": "splicing_snap_a_end", "B": "splicing_snap_b_end"}


# Date: 2026-10-07
def get_splicing_project(project, employee):
	"""The project, after checking that `employee` is in its splicing team."""
	doc = frappe.get_doc("New Project", project)
	doc.check_permission("read")
	if employee not in doc.get_splicing_team():
		frappe.throw(_("{0} is not in the splicing team of {1}").format(employee, project), frappe.PermissionError)
	return doc


# Date: 2026-10-07
@frappe.whitelist()
def splicing_jobs(employee):
	"""Projects waiting for splicing photos from this employee, for the EmployeeTracker mobile app.

	2026-10-09: the team comes from the Splicing Team table. The reply keeps the old keys
	(splicing_rider_name, splicer_name, assistant_splicer_name = this employee's pair) so the
	app keeps working, and adds "splicing_team" with every pair.
	"""
	rows = frappe.get_all(
		"Project Splicing Team Member",
		filters={"parenttype": "New Project"},
		or_filters={"rider": employee, "splicer": employee},
		fields=["parent", "rider_name", "splicer_name"],
	)
	if not rows:
		return []
	own_pair = {row.parent: row for row in rows}
	projects = frappe.get_all(
		"New Project",
		filters={"stage": SPLICING, "name": ["in", list(own_pair)]},
		fields=[
			"name", "wo", "end_location_name", "end_location_lat_long", "new_b_end_location",
			"splicing_snap_a_end", "splicing_snap_b_end",
		],
		order_by="modified desc",
	)
	for project in projects:
		pair = own_pair[project.name]
		project.splicing_rider_name = pair.rider_name
		project.splicer_name = pair.splicer_name
		project.assistant_splicer_name = None
		project.splicing_team = frappe.get_all(
			"Project Splicing Team Member",
			filters={"parent": project.name, "parenttype": "New Project"},
			fields=["rider_name", "splicer_name"],
			order_by="idx",
		)
	return projects


# Date: 2026-10-07
@frappe.whitelist(methods=["POST"])
def upload_splicing_snap(project, employee, end, filename=None, filedata=None):
	"""Attach a splicing photo taken on the phone to the A or B end of a project.

	Send the photo as multipart form field `file`, or as base64 text in `filedata`.
	"""
	import base64

	end = (end or "").strip().upper()
	if end not in SPLICING_SNAP_FIELDS:
		frappe.throw(_("End must be A or B"))
	doc = get_splicing_project(project, employee)
	if doc.stage != SPLICING:
		frappe.throw(_("{0} is not waiting for splicing photos (now: {1})").format(project, doc.stage))

	upload = frappe.request.files.get("file") if frappe.request else None
	if upload:
		content, filename = upload.stream.read(), filename or upload.filename
	elif filedata:
		content = base64.b64decode(filedata.split(",", 1)[-1])
	else:
		frappe.throw(_("No photo received"))

	fieldname = SPLICING_SNAP_FIELDS[end]
	# The app signs in as one shared API user, which has no Splicing Team role. The checks above
	# stand in for that role, so save as Administrator and record who actually uploaded.
	session_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": filename or f"{project}-splicing-{end}-end.jpg",
				"content": content,
				"is_private": 1,
				"attached_to_doctype": "New Project",
				"attached_to_name": project,
				"attached_to_field": fieldname,
			}
		).insert()
		doc.set(fieldname, file.file_url)
		doc.save()
	finally:
		frappe.set_user(session_user)

	doc.add_comment("Info", _("Splicing photo for {0} End uploaded from the mobile app by {1}").format(end, employee))
	return {"stage": doc.stage, "file_url": file.file_url}
