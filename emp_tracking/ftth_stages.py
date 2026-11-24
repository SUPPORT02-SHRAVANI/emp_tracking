# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# FTTH Work Order stages: same people and messages as New Project
#
# How it works
#   FTTH Tracker (ftth_tracker app) works out each work order's Stage on save
#   (ftth_tracker/logic.py compute_stage). This module adds what New Project already does:
#     - on_update (doc_events in hooks.py): when the Stage changes, a bell notification and a
#       WhatsApp message (WhatsApp Settings "project_stage_template") go to whoever acts next:
#         Area Manager stages  -> the work order's Area Manager (Login), else role Area Manager
#         Project Head stages  -> role Project Head
#         Fiber Work           -> the Fiber Team's contact number + role Fiber Team
#         Splicing             -> the splicers' / riders' contact numbers + role Splicing Team
#         Billing              -> roles Accounts User / Accounts Manager
#         Closed / Cancelled   -> WhatsApp to the Project Heads only
#       Rows saved by an FTTH Import are skipped, so a monthly sheet does not send hundreds of
#       messages.
#     - grant_permissions() (after_migrate, via after_migrate()): lets the New Project roles open and edit FTTH Work
#       Orders and pick the teams / staff / GIS / KMZ records they link to.
#
# Change log
#   2026-10-29  Created.
#   2026-10-29  Accounts User / Accounts Manager may edit FTTH Work Orders (Billing tab).
#   2026-10-29  Stage owners exactly as New Project.get_stage_owners: AT & HOTO -> Project Head,
#               Billing -> Accounts; Closed / Cancelled -> WhatsApp to Project Head, no bell.
#   2026-10-31  New Project merged into FTTH Work Order (New Project doctype removed, see
#               patches/remove_new_project.py). Moved here from new_project.py:
#                 - users_with_role / mobiles_of_users helpers;
#                 - the Network Link (maintenance handover) made when the HOTO Date is set,
#                   stored in the custom field custom_network_link (created in after_migrate),
#                   plus create_network_link() for the form's "Create Network Link" button.
#               The form's "Send Mail to Planning" button is in public/js/ftth_work_order.js.
#   2026-10-31  Field levels per role (FIELD_LEVELS / LEVEL_WRITERS, apply_field_levels): each
#               role edits only its own part of a work order, as New Project's tabs did; all
#               parts stay readable. Project Head and FTTH Manager / FTTH User edit everything.
# ---------------------------------------------------------------------------------------------

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

WORK_ORDER = "FTTH Work Order"
NETWORK_LINK_FIELD = "custom_network_link"

# Stage name -> who acts. Stage names come from ftth_tracker.logic (same wording as New Project).
AREA_MANAGER_STAGES = (
	"Survey by Area Manager",
	"Fiber Team Assignment by Area Manager",
	"Splicer Assignment by Area Manager",
)
PROJECT_HEAD_STAGES = ("B End Approval by Project Head", "Final Details by Project Head", "AT & HOTO by Project Head")
FIBER_WORK = "Fiber Work by Fiber Team"
SPLICING = "Splicing by Splicing Team"
BILLING = "Billing by Accounts"
FINISHED = ("Closed", "Cancelled")

# What each New Project role may do on FTTH Work Order.
WORK_ORDER_PERMS = {
	"Project Head": ("read", "write", "create", "report", "export", "print", "email", "share"),
	"Area Manager": ("read", "write", "report", "print", "email"),
	"Fiber Team": ("read", "write"),
	"Splicing Team": ("read", "write"),
	# 2026-10-29: Accounts fills the Billing tab, as on New Project
	"Accounts User": ("read", "write", "report", "export", "print"),
	"Accounts Manager": ("read", "write", "report", "export", "print"),
}
# Records a work order links to; the roles need to pick / open them.
LINKED_DOCTYPES = ("Fiber Team", "Field Staff", "IBD Team", "GIS Node", "KMZ Route", "KMZ Point", "FTTH Link")

# 2026-10-31: who may edit which part of a work order, as New Project did with its tab levels
# (1 = Project Head, 2 = Area Manager, 3 = Fiber Team, 4 = Splicing Team; 5 = Accounts added).
# Only fields people type in are listed; calculated / read-only fields and Remarks stay at level
# 0, so the server can still set them on any save. A field FTTH Tracker adds later stays at 0.
FIELD_LEVELS = {
	1: (  # Project Head: the work order, locations, final details, AT & HOTO
		"wo_message", "extract_data", "wo_number", "unique_id", "wo_received_date", "communication_mode",
		"ibd_team", "hp", "city", "evisions_link_id", "ftth_link", "gis", "area_manager_user",
		"end_location", "end_lat_long", "end_point", "b_end", "b_end_lat_long", "b_end_point",
		"planning_distance", "final_distance", "distance_shared", "kmz_file", "kmz_done", "kmz_route",
		"mail_to_planning_date", "approval_date", "approval_snap", "approval_kmz", "approved_length",
		"required_length", "deviation_reason", "rsu", "pincode", "nearest_odf", "feeder_type",
		"work_completed_date", "ho_date", "rfs_date", "at_status", "at_paper_status", "hoto_no",
		"hoto_date", "hoto_signature_status", "billing_year", "billing_section_name",
	),
	2: (  # Area Manager: site status, survey, B End issue, team and splicer assignment
		"site_status", "issue_type", "rework_required_date", "issue_detail", "next_action",
		"survey_distance", "b_end_issue", "new_b_end", "fiber_team",
		"splicer", "assistant_splicer", "rider_1", "splicer_2", "rider_2",
	),
	3: (  # Fiber Team: fiber details and proof photos
		"fiber_type", "fiber_id", "fiber_reading_a", "fiber_reading_b", "route_video_done",
		"fiber_id_snap", "reading_a_snap", "reading_b_snap", "route_video",
	),
	4: ("splicing_snaps_done", "splicing_snap_a", "splicing_snap_b"),  # Splicing Team
	5: (  # Accounts: PO, invoice, amount, payment
		"billing_status", "po_no", "po_date", "invoice_no", "invoice_date", "invoice_sent", "arn",
		"airtel_approver", "base_amount", "gst_amount", "payment_due_date", "payment_status", "billing_remark",
	),
}
# Levels each role may edit (all roles with access may read every level). Project Head and the
# FTTH office / import roles keep editing everything, so imports and corrections still work.
ALL_LEVELS = tuple(FIELD_LEVELS)
LEVEL_WRITERS = {
	"System Manager": ALL_LEVELS,
	"Project Head": ALL_LEVELS,
	"FTTH Manager": ALL_LEVELS,
	"FTTH User": ALL_LEVELS,
	"Area Manager": (2,),
	"Fiber Team": (3,),
	"Splicing Team": (4,),
	"Accounts User": (5,),
	"Accounts Manager": (5,),
}


# Date: 2026-10-29
def on_update(doc, method=None):
	"""doc_events hook: when the Stage changed, tell whoever has to act next (bell + WhatsApp).

	2026-10-31: when the HOTO Date was just entered or changed, the Network Link for maintenance
	is made (as New Project did). Only on that change, so saving one of the older work orders
	that already had a HOTO Date does not create links unasked; the form button covers those.
	"""
	if doc.flags.from_ftth_import or frappe.flags.in_import or frappe.flags.in_patch:
		return
	before = doc.get_doc_before_save()
	if doc.get("hoto_date") and str(doc.hoto_date) != str(before.get("hoto_date") if before else None):
		make_network_link(doc)
	previous = before.stage if before else None
	if not doc.get("stage") or previous == doc.stage:
		return
	users = [u for u in stage_users(doc) if u != frappe.session.user]
	if users:
		enqueue_create_notification(
			users,
			{
				"type": "Alert",
				"document_type": doc.doctype,
				"document_name": doc.name,
				"subject": _("{0} ({1}) is now at: {2}").format(
					doc.name, doc.end_location or doc.wo_id or "", doc.stage
				),
				"email_content": doc.issue_detail if doc.stage == "B End Approval by Project Head" else None,
				"from_user": frappe.session.user,
			},
		)
	send_whatsapp(doc, previous)


# Date: 2026-10-29
def stage_users(doc):
	"""Login users who have to act at the work order's current stage."""
	if doc.stage in AREA_MANAGER_STAGES:
		return [doc.area_manager_user] if doc.get("area_manager_user") else users_with_role("Area Manager")
	if doc.stage in PROJECT_HEAD_STAGES:
		return users_with_role("Project Head")
	if doc.stage == FIBER_WORK:
		return users_with_role("Fiber Team")
	if doc.stage == SPLICING:
		return users_with_role("Splicing Team")
	if doc.stage == BILLING:
		return users_with_role("Accounts User") + users_with_role("Accounts Manager")
	return []  # Closed / Cancelled: nobody has to act (Project Heads get the WhatsApp only)


# Date: 2026-10-29
def stage_mobiles(doc):
	"""Mobile numbers for the WhatsApp message. Fiber and splicing staff have no login, so their
	numbers come from the Fiber Team / Field Staff records the work order points to."""
	numbers = []
	if doc.stage == FIBER_WORK and doc.get("fiber_team"):
		numbers.append(frappe.db.get_value("Fiber Team", doc.fiber_team, "contact_no"))
	if doc.stage == SPLICING:
		for field in ("splicer", "assistant_splicer", "splicer_2", "rider_1", "rider_2"):
			if doc.get(field):
				numbers.append(frappe.db.get_value("Field Staff", doc.get(field), "contact_no"))
	if doc.stage in AREA_MANAGER_STAGES and doc.get("area_manager_no") and not doc.get("area_manager_user"):
		numbers.append(doc.area_manager_no)
	users = users_with_role("Project Head") if doc.stage in FINISHED else stage_users(doc)
	numbers += mobiles_of_users(users)
	return [n for n in numbers if n]


# Date: 2026-10-29
def send_whatsapp(doc, completed_stage):
	"""WhatsApp the next stage's people, with New Project's stage template."""
	from emp_tracking.emp_tracking.doctype.whatsapp_settings.whatsapp_settings import send_template

	template = frappe.db.get_single_value("WhatsApp Settings", "project_stage_template")
	send_template(
		stage_mobiles(doc),
		template,
		[doc.name, doc.end_location or doc.wo_id, completed_stage or _("Work order created"), doc.stage],
		reference_doctype=doc.doctype,
		reference_name=doc.name,
	)


# Date: 2026-10-07 (moved from new_project.py on 2026-10-31)
def users_with_role(role):
	"""All enabled users who have the given role."""
	users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent", distinct=True)
	return [user for user in users if frappe.db.get_value("User", user, "enabled")]


# Date: 2026-10-08 (moved from new_project.py on 2026-10-31)
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


# Date: 2026-10-31
def make_network_link(doc):
	"""Create the Network Link (LINKID = the work order's Evisions Link ID) so complaints can be
	traced to this site after handover. Ported from New Project.make_network_link.

	An existing Network Link with that ID is linked instead of duplicated. If something the
	Network Link needs is missing, the user is told what to fill and nothing is created.
	"""
	if doc.get(NETWORK_LINK_FIELD) or doc.get("issue_type") == "Cancelled":
		return
	link_id = (doc.get("evisions_link_id") or "").strip()
	if link_id and frappe.db.exists("Network Link", link_id):
		doc.db_set(NETWORK_LINK_FIELD, link_id, update_modified=False)
		return
	# Area is plain text on the work order but a Link on Network Link: match it to an Area record
	area = find_area(doc.get("area"))
	missing = []
	if not link_id:
		missing.append(_("Evisions Link ID"))
	if not area:
		missing.append(_("Area (must match an Area record)"))
	if not doc.get("end_location"):
		missing.append(_("End Location Name"))
	if missing:
		frappe.msgprint(
			_("The Network Link for maintenance could not be created yet. Please fill: {0}").format(", ".join(missing)),
			title=_("Handover to Maintenance"),
			indicator="orange",
		)
		return

	team = doc.get("team") if doc.get("team") and frappe.db.exists("Maintenance Team", doc.team) else None
	link = frappe.get_doc({
		"doctype": "Network Link",
		"linkid": link_id,
		"network_type": "FTTH",
		"status": "Active",
		"operator": "Airtel",  # FTTH work orders are Airtel MWOs
		"customer": "Airtel" if frappe.db.exists("Customer", "Airtel") else None,
		"project": doc.name,
		"society_building": doc.end_location,
		"location": doc.end_location,
		"area": area,
		"latitude": doc.get("latitude") or None,
		"longitude": doc.get("longitude") or None,
		"maintenance_responsibility": "EVisions",
		"maintenance_team": team,
		"operator_link_id": doc.get("unique_id"),
		"gis_node_id": doc.get("gis"),
	})
	# The Project Head may not have rights on Network Link; the checks above stand in for them.
	link.insert(ignore_permissions=True)
	doc.db_set(NETWORK_LINK_FIELD, link.name, update_modified=False)
	frappe.msgprint(
		_("Network Link {0} created: this site is now handed over to maintenance.").format(link.name),
		indicator="green",
		alert=True,
	)


# Date: 2026-10-31
def find_area(text):
	"""Area record for the work order's Area text: exact name first, then a name containing it."""
	text = (text or "").strip()
	if not text:
		return None
	if frappe.db.exists("Area", text):
		return text
	return frappe.db.get_value("Area", {"area_name": ["like", f"%{text}%"]}, "name")


# Date: 2026-10-31
@frappe.whitelist(methods=["POST"])
def create_network_link(work_order):
	"""Form button "Create Network Link": for work orders whose HOTO Date was entered before this
	feature, or whose first attempt was missing data."""
	doc = frappe.get_doc(WORK_ORDER, work_order)
	doc.check_permission("write")
	if not doc.hoto_date:
		frappe.throw(_("Fill the HOTO Date first."))
	make_network_link(doc)
	return doc.get(NETWORK_LINK_FIELD)


# Date: 2026-10-31
def make_custom_fields():
	"""after_migrate: the Network Link field on FTTH Work Order (Billing tab, after HOTO).
	A Custom Field because FTTH Tracker can be installed without this app's Network Link."""
	if not frappe.db.exists("DocType", WORK_ORDER):
		return
	create_custom_fields({WORK_ORDER: [{
		"fieldname": NETWORK_LINK_FIELD, "label": "Network Link (Maintenance)", "fieldtype": "Link",
		"options": "Network Link", "insert_after": "hoto_signature_status", "read_only": 1, "no_copy": 1,
		"description": "Made when the HOTO Date is entered; complaints are traced to this link.",
	}]}, update=True)


# Date: 2026-10-29
def grant_permissions():
	"""after_migrate: give the New Project roles their rights on FTTH Work Order (WORK_ORDER_PERMS)
	and select / read on the records it links to. Skipped when FTTH Tracker is not installed.
	Same approach as workforce_dashboard.setup.grant_oh_link_permissions: the standard rows are
	copied to Custom DocPerm first, so FTTH Manager / FTTH User keep their rights."""
	if not frappe.db.exists("DocType", WORK_ORDER):
		return
	for role, ptypes in WORK_ORDER_PERMS.items():
		_grant(WORK_ORDER, role, ptypes)
	for doctype in LINKED_DOCTYPES:
		for role in ("Project Head", "Area Manager", "Fiber Team", "Splicing Team"):
			_grant(doctype, role, ("select", "read"))


# Date: 2026-10-29
def _grant(doctype, role, ptypes):
	"""Add a level-0 permission row for the role (if missing) and tick the given rights."""
	from frappe.permissions import setup_custom_perms, update_permission_property

	if not frappe.db.exists("DocType", doctype) or not frappe.db.exists("Role", role):
		return
	if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
		setup_custom_perms(doctype)
		frappe.get_doc({"doctype": "Custom DocPerm", "parent": doctype, "parenttype": "DocType",
			"parentfield": "permissions", "role": role, "permlevel": 0}).insert(ignore_permissions=True)
	for ptype in ptypes:
		update_permission_property(doctype, role, 0, ptype, 1, validate=False)


# Date: 2026-10-31
def apply_field_levels():
	"""after_migrate: put each editable field on its role's permission level (FIELD_LEVELS) with
	Property Setters, then give every role that can open work orders read on all levels and write
	on its own (LEVEL_WRITERS). Re-applied on every migrate, so an FTTH Tracker update that
	rewrites the doctype JSON does not undo it. Runs after grant_permissions(), which made the
	level-0 rows."""
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter
	from frappe.permissions import update_permission_property

	if not frappe.db.exists("DocType", WORK_ORDER):
		return
	existing = set(frappe.get_all("DocField", filters={"parent": WORK_ORDER}, pluck="fieldname"))
	for level, fieldnames in FIELD_LEVELS.items():
		for fieldname in fieldnames:
			if fieldname in existing:
				make_property_setter(WORK_ORDER, fieldname, "permlevel", level, "Int", validate_fields_for_doctype=False)

	# Everyone who can read work orders at level 0 (also roles added later by hand) reads every level
	readers = set(frappe.get_all("Custom DocPerm", filters={"parent": WORK_ORDER, "permlevel": 0, "read": 1}, pluck="role"))
	for role in readers | set(LEVEL_WRITERS):
		if not frappe.db.exists("Role", role):
			continue
		for level in ALL_LEVELS:
			if not frappe.db.exists("Custom DocPerm", {"parent": WORK_ORDER, "role": role, "permlevel": level}):
				frappe.get_doc({"doctype": "Custom DocPerm", "parent": WORK_ORDER, "parenttype": "DocType",
					"parentfield": "permissions", "role": role, "permlevel": level}).insert(ignore_permissions=True)
			update_permission_property(WORK_ORDER, role, level, "read", 1, validate=False)
			# Explicit 0 too, so taking a level away in LEVEL_WRITERS takes effect on the next migrate
			can_write = 1 if level in LEVEL_WRITERS.get(role, ()) else 0
			update_permission_property(WORK_ORDER, role, level, "write", can_write, validate=False)
	frappe.clear_cache(doctype=WORK_ORDER)


# Date: 2026-10-29
def after_migrate():
	"""hooks.py after_migrate: grant_permissions(), never failing the deploy (errors go to the Error Log).
	2026-10-31: also make_custom_fields() (Network Link field) and apply_field_levels()."""
	try:
		make_custom_fields()
		grant_permissions()
		apply_field_levels()
	except Exception:
		frappe.log_error(title="emp_tracking: FTTH Work Order permissions after migrate failed")
