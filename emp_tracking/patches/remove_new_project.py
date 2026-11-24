# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Patch: remove New Project (merged into FTTH Work Order)
#
# How this file works
#   New Project and FTTH Work Order tracked the same job (work order -> survey -> fiber ->
#   splicing -> RFS -> AT & HOTO -> billing) with the same stages and roles. FTTH Work Order is
#   kept: it holds the real data (3,012 rows on newsite.local against 4 New Project test rows
#   made by Administrator on 7-9 Oct 2026, which the user chose to drop). The New Project
#   behaviour that FTTH Work Order lacked moved to emp_tracking/ftth_stages.py and
#   public/js/ftth_work_order.js.
#   The New Project code folders are deleted, so this patch removes what is left in the database:
#     1. the New Project rows and their Fiber Team / Splicing Team child rows;
#     2. rows elsewhere that point at New Project (comments, communications, notification logs,
#        files, sidebar links, permissions, customizations ...);
#     3. the three DocType records (New Project, Project Fiber Team Member, Project Splicing Team
#        Member) and their tables. Frappe's own orphan clean-up would leave the tables behind.
#   Runs after the doctypes are synced (post_model_sync), so Network Link.project already links
#   to FTTH Work Order. Safe to run twice: everything is skipped once the tables are gone.
#
# Change log
#   2026-10-31  Created.
#   2026-11-24  Before anything is deleted, every New Project row, its team rows, comments and
#               attachment list are written to <site>/private/backups/new_project_backup_<time>.json
#               (backup_rows()). Other sites (Frappe Cloud) may hold real New Projects, unlike the
#               4 test rows on newsite.local, so the data must stay recoverable.
# ---------------------------------------------------------------------------------------------

import json
import os

import frappe
from frappe.utils import now_datetime

NEW_PROJECT = "New Project"
CHILD_DOCTYPES = ("Project Fiber Team Member", "Project Splicing Team Member")

# Other doctypes' rows that point at a New Project (doctype -> field holding the doctype name).
# File is handled separately so the attached files are removed from disk too.
REFERENCES = {
	"Comment": "reference_doctype",
	"Communication": "reference_doctype",
	"Version": "ref_doctype",
	"Notification Log": "document_type",
	"ToDo": "reference_type",
	"Activity Log": "reference_doctype",
	"DocShare": "share_doctype",
	"Document Follow": "ref_doctype",
	"Tag Link": "document_type",
	"WhatsApp Message": "reference_doctype",
}


# Date: 2026-11-24
def backup_rows():
	"""Write all New Project data to a JSON file in the site's private backups folder.

	Raw SQL, because the New Project controller code is gone. Nothing is written when there are no
	rows. An error here (e.g. disk not writable) stops the patch, so nothing is deleted unsaved.
	"""
	if not frappe.db.table_exists(NEW_PROJECT):
		return
	data = {NEW_PROJECT: frappe.db.sql(f"select * from `tab{NEW_PROJECT}`", as_dict=True)}
	if not data[NEW_PROJECT]:
		return
	for child in CHILD_DOCTYPES:
		if frappe.db.table_exists(child):
			data[child] = frappe.db.sql(f"select * from `tab{child}`", as_dict=True)  # nosemgrep: fixed names
	data["Comment"] = frappe.get_all("Comment", filters={"reference_doctype": NEW_PROJECT}, fields=["*"])
	data["File"] = frappe.get_all("File", filters={"attached_to_doctype": NEW_PROJECT}, fields=["*"])

	folder = frappe.get_site_path("private", "backups")
	os.makedirs(folder, exist_ok=True)
	path = os.path.join(folder, f"new_project_backup_{now_datetime():%Y%m%d_%H%M%S}.json")
	with open(path, "w", encoding="utf-8") as f:
		json.dump(data, f, indent=1, default=str, ensure_ascii=False)
	print(f"New Project: {len(data[NEW_PROJECT])} row(s) saved to {path} before removal")


# Date: 2026-10-31
def execute():
	"""Delete the New Project data, the rows pointing at it, its DocTypes and its tables."""
	doctypes = (NEW_PROJECT, *CHILD_DOCTYPES)

	# 0: keep a copy first (2026-11-24); stops the patch if the copy cannot be written
	backup_rows()

	# 1 + 2: data. Plain SQL / File deletes: the New Project controller code no longer exists,
	# so frappe.delete_doc on a New Project row would fail to import it.
	if frappe.db.table_exists(NEW_PROJECT):
		for name in frappe.get_all("File", filters={"attached_to_doctype": NEW_PROJECT}, pluck="name"):
			frappe.delete_doc("File", name, ignore_permissions=True, force=True)
		for doctype, field in REFERENCES.items():
			if frappe.db.table_exists(doctype) and frappe.db.has_column(doctype, field):
				frappe.db.delete(doctype, {field: NEW_PROJECT})
		frappe.db.delete(NEW_PROJECT)
	for child in CHILD_DOCTYPES:
		if frappe.db.table_exists(child):
			frappe.db.delete(child)

	# Menu links and customizations that name these doctypes. The menu itself is rebuilt by
	# workforce_dashboard.setup.after_migrate, which no longer lists New Project.
	if frappe.db.table_exists("Workspace Sidebar Item"):
		frappe.db.delete("Workspace Sidebar Item", {"link_to": NEW_PROJECT})
	for doctype, field in (("Workspace Link", "link_to"), ("Workspace Shortcut", "link_to")):
		if frappe.db.table_exists(doctype):
			frappe.db.delete(doctype, {field: NEW_PROJECT})
	frappe.db.delete("Custom DocPerm", {"parent": ("in", doctypes)})
	frappe.db.delete("Property Setter", {"doc_type": ("in", doctypes)})
	frappe.db.delete("Custom Field", {"dt": ("in", doctypes)})

	# 3: DocType records, then the tables (deleting a DocType keeps its table in Frappe v16)
	for doctype in doctypes:
		if frappe.db.exists("DocType", doctype):
			frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True)
		if frappe.db.table_exists(doctype):
			frappe.db.sql_ddl(f"drop table if exists `tab{doctype}`")  # nosemgrep: fixed names above
