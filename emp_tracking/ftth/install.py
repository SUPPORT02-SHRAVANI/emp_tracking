# Copyright (c) 2026, Softworld and contributors
# For license information, please see license.txt

"""FTTH module setup: FTTH roles and the FTTH Settings defaults.

Change log:
	2026-11-24  Moved from the separate ftth_tracker app into emp_tracking (module "FTTH").
	            The settings defaults are now in apply_settings_defaults(), so the patch
	            emp_tracking.ftth.patches.ftth_settings_defaults can set them on sites where
	            emp_tracking was already installed (after_install does not run there).
"""

import frappe

ROLES = ("FTTH Manager", "FTTH User")
SETTINGS_DEFAULTS = {"company": "Airtel", "wo_received_mode": "Telegram", "splicing_team_size": 1,
	"survey_diff_pct": 50, "kmz_diff_pct": 30, "auto_match_kmz": 1}


def ensure_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


def apply_settings_defaults():
	"""Fill FTTH Settings fields that are still empty; values already set are kept."""
	settings = frappe.get_single("FTTH Settings")
	for key, value in SETTINGS_DEFAULTS.items():
		if not settings.get(key):
			settings.set(key, value)
	settings.flags.ignore_permissions = True
	settings.save()


def before_install():
	ensure_roles()


def after_install():
	ensure_roles()
	apply_settings_defaults()
	frappe.db.commit()
