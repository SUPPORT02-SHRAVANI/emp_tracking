# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""Employee Home Location (created 2026-10-21 in this app; previously a hand-made custom DocType on the
cloud site). One record per employee (named by employee). Saved from the mobile app and approved by the
manager; an approved location lets the employee punch IN from home."""

# import frappe
from frappe.model.document import Document


class EmployeeHomeLocation(Document):
	pass
