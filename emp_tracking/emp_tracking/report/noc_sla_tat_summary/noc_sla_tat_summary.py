# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# NOC SLA TAT Summary (Script Report)
#
# How this file works
#   The NOC workbook's ALL TEAM SUMMARY pivots: SRs received in the range, grouped by the chosen
#   rows (month / team / splicer / date, the workbook's pivot layouts), counted against TAT
#   bucket x SLA (In / Out), plus still open, totals, unique cuts, In-SLA % and average MTTR in
#   hours. Built by emp_tracking/noc_reports.py (sla_tat_summary).
#   The chart adds the rows up by the first row key (e.g. per month), In vs Out of SLA.
#
# Change log
#   2026-11-26  Created.
#   2026-11-26  Readable look: plain bucket names that fit the header ("Same day In" instead of
#               "Within 1 Day · IN"), summary columns first, chart per first key with whole numbers.
# ---------------------------------------------------------------------------------------------

from collections import OrderedDict

from frappe import _

from emp_tracking.noc_reports import IN, KEY_LABELS, OUT, TAT_BUCKETS, column_key, empty_message, sla_tat_summary

BUCKET_NAMES = {"Within 1 Day": "Same day", "1 Day": "Next day", "2 Days": "2 days", "3+ Days": "3+ days"}


# Date: 2026-11-26
def execute(filters=None):
	filters = filters or {}
	keys, rows = sla_tat_summary(filters, filters.get("group_by") or "Month, Team")
	for r in rows:
		if "month" in r:
			r.month = r.month.strftime("%b %Y")
		if "team" in r:
			r.team = r.team.title()
		if "splicer" in r:
			r.splicer = r.splicer.title()

	columns = []
	for k in keys:
		columns.append({"fieldname": k, "label": _(KEY_LABELS[k]), "fieldtype": "Date" if k == "date" else "Data",
			"width": 170 if k == "splicer" else 100})
	# the totals a manager reads first, then the TAT x SLA breakdown of the workbook's pivots
	columns += [
		{"fieldname": "total", "label": _("SRs"), "fieldtype": "Int", "width": 70},
		{"fieldname": "cuts", "label": _("Cuts"), "fieldtype": "Int", "width": 70},
		{"fieldname": "in_sla", "label": _("In SLA"), "fieldtype": "Int", "width": 80},
		{"fieldname": "out_sla", "label": _("Out of SLA"), "fieldtype": "Int", "width": 110},
		{"fieldname": "sla_pct", "label": _("In SLA %"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "avg_mttr", "label": _("Avg MTTR (h)"), "fieldtype": "Float", "precision": 1, "width": 130},
	]
	for bucket in TAT_BUCKETS:
		for sla in (IN, OUT):
			columns.append({"fieldname": column_key(bucket, sla), "label": f"{_(BUCKET_NAMES[bucket])} {_(sla.title())}",
				"fieldtype": "Int", "width": 130})
	columns.append({"fieldname": "open", "label": _("Still open"), "fieldtype": "Int", "width": 90})
	# 2026-11-26: empty period -> message instead of an empty table
	return columns, rows, None if rows else empty_message(filters), chart(keys, rows)


# Date: 2026-11-26
def chart(keys, rows):
	"""In vs Out of SLA added up per value of the first row key (month, team, splicer or date) that
	has more than one value, so one month shows its teams instead of a single block."""
	if not rows:
		return None
	first = next((k for k in keys if len({r[k] for r in rows}) > 1), keys[0])
	sums = OrderedDict()
	for r in rows:
		label = r[first].strftime("%d %b") if first == "date" else str(r[first])
		s = sums.setdefault(label, [0, 0])
		s[0] += r.in_sla
		s[1] += r.out_sla
	if first == "splicer":
		# splicers: the 20 with the most closed SRs, most first
		sums = OrderedDict(sorted(sums.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:20])
	return {
		"data": {
			"labels": list(sums),
			"datasets": [
				{"name": _("In SLA"), "values": [v[0] for v in sums.values()]},
				{"name": _("Out of SLA"), "values": [v[1] for v in sums.values()]},
			],
		},
		"type": "bar",
		"height": 240,
		"fieldtype": "Int",
		"barOptions": {"stacked": 1, "spaceRatio": 0.45},
		"colors": ["#22c55e", "#ef4444"],
	}
