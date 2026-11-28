# ---------------------------------------------------------------------------------------------
# Patch: new Sites failed with "Duplicate entry SITE-34944" (found 2026-11-28 while checking the
# "add a new node / site / link from the start" flow). Site is named "format:SITE-{#####}"; Frappe
# keeps that number in the shared series row "" (empty name, also used by Complaint Information,
# KMZ Upload, FTTH Work Order ...), and match_network_to_master (2026-11-27) had moved only the
# "SITE-" row after inserting SITE-30894 ... SITE-40574. This moves "" past the highest SITE
# number in use (never down), so the next Site gets a free number. Other doctypes' next numbers
# simply jump forward too. Safe to run again.
# ---------------------------------------------------------------------------------------------

import frappe


def execute():
	last = frappe.db.sql("""select max(cast(substring(name, 6) as unsigned)) from `tabSite`
		where name like 'SITE-%%'""")[0][0] or 0
	if frappe.db.exists("DocType", "Node Site"):
		other = frappe.db.sql("""select max(cast(substring(name, 6) as unsigned)) from `tabNode Site`
			where name like 'SITE-%%'""")[0][0] or 0
		last = max(last, other)
	found = frappe.db.sql("select `current` from `tabSeries` where `name` = ''")
	if not found:
		frappe.db.sql("insert into `tabSeries` (`name`, `current`) values ('', %s)", last)
	elif (found[0][0] or 0) < last:
		frappe.db.sql("update `tabSeries` set `current` = %s where `name` = ''", last)
	frappe.db.commit()
