# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Network Topology dashboard (Desk page /app/network-topology): data
#
# How this file works
#   Topology comes from data already kept:
#   * inside a node, the Site ETIPL codes: "D1J.2.4.1" is fed from "D1J.2.4", which is fed from
#     "D1J.2", which is fed from node D1J. A site whose feeder code has no Site is hung under
#     the nearest code above it that has one (else under the node). A site without an ETIPL
#     code hangs under the site named in its B Location, as on the GIS Node Site Diagram;
#   * between nodes, the GIS Node Custom Field "Fed From Node" (custom_fed_from, setup.py): if
#     a node stops, the nodes it feeds stop too;
#   * live faults: open Complaint Information rows on a site or node (workflow state not closed).
#   get_overview: one row per node for the overview cards (sites, depth, open faults, the site
#     whose failure cuts off the most others).
#   get_topology: one node's tree, its open faults and the nodes it feeds, for the page to draw
#     and to work out what a failure affects (the page does that part in the browser).
#
# Change log
#   2026-10-27  Created.
# ---------------------------------------------------------------------------------------------

import frappe
from frappe.utils import cint

# Complaint workflow ("OHP Maintenance Workflow") states that mean the fault is over
CLOSED_STATES = ("Closed", "Resolved", "Fiber Restored", "Rejected")


def site_parents(sites, node):
	"""{site name: parent site name or None (= fed straight from the node)}."""
	by_code = {s.etipl_code.strip().upper(): s.name for s in sites if s.etipl_code}
	by_name = {(s.site_name or "").strip().lower(): s.name for s in sites}
	parents = {}
	for s in sites:
		parent = None
		if s.etipl_code:
			parts = s.etipl_code.strip().upper().split(".")
			# walk up the code until a level that has a Site; "D1J.2" (2 parts) is first level
			while len(parts) > 2 and not parent:
				parts = parts[:-1]
				parent = by_code.get(".".join(parts)) if len(parts) >= 2 else None
		elif s.b_location:
			parent = by_name.get(s.b_location.strip().lower())
		parents[s.name] = parent if parent != s.name else None
	# a loop in bad data (A under B under A) would hang the page: cut it at the node
	for name in parents:
		seen, p = {name}, parents[name]
		while p:
			if p in seen:
				parents[name] = None
				break
			seen.add(p)
			p = parents.get(p)
	return parents


def open_faults(filters):
	if not frappe.db.exists("DocType", "Complaint Information"):
		return []
	return frappe.get_list("Complaint Information", filters=filters + [["workflow_state", "not in", CLOSED_STATES],
		["docstatus", "<", 2]], fields=["name", "site", "node_id", "workflow_state", "complaint_date_and_time",
		"link_status", "society_name", "linkid"], order_by="complaint_date_and_time desc", limit_page_length=500)


def downstream_counts(parents):
	"""{site: number of sites fed through it} and the tree depth."""
	children = {}
	for site, parent in parents.items():
		children.setdefault(parent, []).append(site)
	counts, depth = {}, 0

	def walk(site, level):
		nonlocal depth
		depth = max(depth, level)
		total = 0
		for child in children.get(site, []):
			total += 1 + walk(child, level + 1)
		counts[site] = total
		return total

	for top in children.get(None, []):
		walk(top, 1)
	return counts, depth


def fed_nodes(node, fed_from):
	"""Every node fed through `node`, directly or further down: [(node, level)]."""
	out, frontier, seen = [], [node], {node}
	while frontier:
		nxt = []
		for n in frontier:
			for child, parent in fed_from.items():
				if parent == n and child not in seen:
					seen.add(child)
					nxt.append(child)
					out.append(child)
		frontier = nxt
	return out


def fed_from_map():
	if not frappe.db.has_column("GIS Node", "custom_fed_from"):
		return {}
	return {r.name: r.custom_fed_from for r in frappe.get_all("GIS Node", filters={"custom_fed_from": ["is", "set"]},
		fields=["name", "custom_fed_from"])}


# Date: 2026-10-27
@frappe.whitelist()
def get_overview():
	sites = frappe.get_list("Site", filters={"node": ["is", "set"]}, fields=["name", "site_name", "etipl_code",
		"b_location", "node"], limit_page_length=0)
	by_node = {}
	for s in sites:
		by_node.setdefault(s.node, []).append(s)
	faults = open_faults([])
	fault_nodes = {}
	for f in faults:
		node = f.node_id or (frappe.db.get_value("Site", f.site, "node") if f.site else None)
		if node:
			fault_nodes[node] = fault_nodes.get(node, 0) + 1
	fed_from = fed_from_map()
	nodes = set(by_node) | set(fault_nodes) | set(fed_from) | set(fed_from.values())
	info = {r.name: r for r in frappe.get_all("GIS Node", filters={"name": ["in", list(nodes)]},
		fields=["name", "area", "team", "is_active"])} if nodes else {}
	rows = []
	for node in nodes:
		node_sites = by_node.get(node, [])
		counts, depth = downstream_counts(site_parents(node_sites, node))
		names = {s.name: s for s in node_sites}
		critical = max(counts, key=counts.get) if counts else None
		rows.append({
			"node": node, "area": info.get(node, {}).get("area"), "team": info.get(node, {}).get("team"),
			"sites": len(node_sites), "depth": depth, "faults": fault_nodes.get(node, 0),
			"fed_from": fed_from.get(node), "feeds": len(fed_nodes(node, fed_from)),
			"critical_site": critical and names[critical].site_name, "critical_code": critical and names[critical].etipl_code,
			"critical_count": counts.get(critical, 0) if critical else 0,
		})
	rows.sort(key=lambda r: (-r["sites"], r["node"]))
	return {"nodes": rows, "open_faults": len(faults)}


# Date: 2026-10-27
@frappe.whitelist()
def get_topology(node):
	frappe.has_permission("GIS Node", "read", node, throw=True)
	gis = frappe.db.get_value("GIS Node", node, ["name", "area", "team", "manager", "area_manager", "is_active"], as_dict=True)
	sites = frappe.get_list("Site", filters={"node": node}, fields=["name", "site_name", "etipl_code", "b_location",
		"vendor_name"], limit_page_length=0)
	parents = site_parents(sites, node)
	counts, depth = downstream_counts(parents)
	faults = open_faults([["node_id", "=", node]]) + [f for f in open_faults([["site", "in", [s.name for s in sites] or [""]]])
		if f.node_id != node]
	fed_from = fed_from_map()
	feeds = fed_nodes(node, fed_from)
	feed_sites = {r.node: cint(r.n) for r in frappe.get_list("Site", filters={"node": ["in", feeds]},
		fields=["node", {"COUNT": "*", "as": "n"}], group_by="node")} if feeds else {}
	return {
		"node": {**gis, "fed_from": fed_from.get(node)},
		"sites": [{**s, "parent": parents[s.name], "downstream": counts.get(s.name, 0)} for s in sites],
		"depth": depth, "faults": faults,
		"feeds": [{"node": n, "fed_from": fed_from.get(n), "sites": feed_sites.get(n, 0)} for n in feeds],
	}
