# Temporary helper: loads the NOC Dashboard page and the Helpdesk NOC sidebar into the site
# without a terminal `bench migrate`, and puts the Workforce icon on the caller's desk home.
# Open /api/method/emp_tracking.setup_noc_dashboard.run once as a System Manager, then delete this file.

import json
import os

import frappe
from frappe.modules.import_file import import_file_by_path

WORKFORCE_ICON = "Workforce"
ICON_FIELDS = [
	"label", "bg_color", "link", "link_type", "app", "icon_type", "parent_icon", "icon", "link_to", "idx",
	"standard", "logo_url", "hidden", "name", "restrict_removal", "icon_image",
]


@frappe.whitelist()
def run():
	frappe.only_for("System Manager")
	app_path = frappe.get_app_path("emp_tracking")
	for parts in (
		("emp_tracking", "page", "noc_dashboard", "noc_dashboard.json"),
		("workspace_sidebar", "helpdesk_noc.json"),
	):
		import_file_by_path(os.path.join(app_path, *parts), force=True)
	icon_note = show_workforce_icon()
	frappe.db.commit()  # nosemgrep: GET request, nothing else commits for us
	frappe.clear_cache()
	return {
		"result": "NOC Dashboard installed. " + icon_note + " Reload the desk page (Ctrl+Shift+R).",
		"check": icon_report(),
	}


def icon_report():
	"""What decides whether the Workforce icon shows on this user's home screen."""
	from frappe.desk.doctype.desktop_icon.desktop_icon import clear_desktop_icons_cache

	user = frappe.session.user
	clear_desktop_icons_cache(user)
	saved = frappe.db.get_value("Desktop Layout", user, "layout")
	layout = json.loads(saved) if saved else None
	return {
		"user": user,
		"icon": frappe.db.get_value(
			"Desktop Icon", WORKFORCE_ICON, ["owner", "hidden", "standard", "icon_type", "link_type", "link_to", "parent_icon", "app"], as_dict=True
		),
		"icon_roles": frappe.get_all("Has Role", filters={"parenttype": "Desktop Icon", "parent": WORKFORCE_ICON}, pluck="role"),
		"user_has_icon_role": bool(
			set(frappe.get_all("Has Role", filters={"parenttype": "Desktop Icon", "parent": WORKFORCE_ICON}, pluck="role"))
			& set(frappe.get_roles(user))
		),
		"sidebar_items": frappe.db.count("Workspace Sidebar Item", {"parent": WORKFORCE_ICON}),
		"saved_layout_labels": [i.get("label") for i in layout] if isinstance(layout, list) else layout and str(type(layout)),
	}


def show_workforce_icon():
	"""Make the Workforce icon appear on the caller's desk home screen."""
	if not frappe.db.exists("Desktop Icon", WORKFORCE_ICON):
		from emp_tracking.emp_tracking.page.workforce_dashboard.setup import make_navigation

		make_navigation()
	# The desk only lists non-standard icons owned by Administrator or by the viewer.
	frappe.db.set_value("Desktop Icon", WORKFORCE_ICON, {"owner": "Administrator", "hidden": 0}, update_modified=False)

	# A user who has rearranged their home screen has a saved layout, and the desk then shows
	# only the icons in it; an icon created later has to be added to that layout.
	user = frappe.session.user
	saved = frappe.db.get_value("Desktop Layout", user, "layout")
	if not saved:
		return "Workforce icon is enabled (no saved home layout for {0}).".format(user)
	layout = json.loads(saved)
	if not isinstance(layout, list) or not all(isinstance(i, dict) for i in layout):
		return "Workforce icon is enabled, but your saved home layout has an unexpected format and was left as is."
	if any(i.get("label") == WORKFORCE_ICON for i in layout):
		for i in layout:
			if i.get("label") == WORKFORCE_ICON:
				i["hidden"] = 0
	else:
		icon = frappe.db.get_value("Desktop Icon", WORKFORCE_ICON, ICON_FIELDS, as_dict=True)
		icon["idx"] = max([i.get("idx") or 0 for i in layout if not i.get("parent_icon")] or [0]) + 1
		layout.append(icon)
	frappe.db.set_value("Desktop Layout", user, "layout", json.dumps(layout), update_modified=False)
	return "Workforce icon added to the saved home layout of {0}.".format(user)
