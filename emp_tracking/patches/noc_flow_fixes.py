# ---------------------------------------------------------------------------------------------
# Patch: NOC flow check fixes for existing complaints (2026-11-28, user: "make sure the whole NOC
# flow is valid and connected"). Same rules as Complaint Information.validate now has:
#   1. An empty Link Status takes its workflow step's one (STATE_LINK_STATUS).
#   2. An open complaint with no team and no vendor gets the EVisions team of its team area.
#   3. A closed complaint with a Team SR closed time but no SLA In / Out gets it (EVision Settings
#      SLA hours / formula), with its MTTR.
# Nothing else in old complaints is changed. Safe to run again.
# ---------------------------------------------------------------------------------------------

import frappe

from emp_tracking.emp_tracking.doctype.complaint_information.complaint_information import (
	STATE_LINK_STATUS,
	seconds_between,
	sla,
)

OPEN_DONE = ("Closed", "Resolved", "Rejected", "Fiber Restored", "Awaiting Operator Confirmation")


def execute():
	frappe.reload_doc("emp_tracking", "doctype", "complaint_information")
	C = "`tabComplaint Information`"
	for state, status in STATE_LINK_STATUS.items():
		frappe.db.sql(f"update {C} set link_status = %s where workflow_state = %s and coalesce(link_status, '') = ''",
			(status, state))

	teams = dict(frappe.db.sql("""select area, name from `tabMaintenance Team`
		where team_type = 'EVisions' and status = 'Active' and area like 'Area %%'"""))
	for area, team in teams.items():
		frappe.db.sql(f"""update {C} set maintenance_team = %s where team_area = %s and workflow_state not in %s
			and coalesce(maintenance_team, '') = '' and coalesce(mapped_vendor, '') = ''""", (team, area, OPEN_DONE))

	for r in frappe.db.sql(f"""select name, complaint_date_and_time, evision_closed_on from {C}
			where workflow_state in ('Closed', 'Resolved') and evision_closed_on is not null
			and coalesce(evision_sla, '') = ''""", as_dict=True):
		mttr = seconds_between(r.complaint_date_and_time, r.evision_closed_on)
		if mttr is not None:
			frappe.db.set_value("Complaint Information", r.name, {"evision_mttr": mttr, "evision_sla": sla(mttr)},
				update_modified=False)
	frappe.db.commit()
