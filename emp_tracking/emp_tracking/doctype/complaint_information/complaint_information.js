// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

// ---------------------------------------------------------------------------------------------
// Complaint Information: form script
//
// How this file works
//   NOC logs an operator's complaint (Airtel, Vodafone or Railtel) on this form.
//     1. NOC picks the operator, then pastes the operator's message or attaches a screenshot.
//        A screenshot is read to text in the browser (Tesseract.js) and treated as pasted text.
//     2. parse_complaint_message() pulls out the incident number, priority, complaint type,
//        section, down time, node and so on, and the form fields are filled from it.
//     3. The LINKID (Network Link) is found from the node or from the link name in the message;
//        area, location, team and vendor then come from that link.
//     4. For FTTH, NOC picks the Node (from the GIS Node master), then the Society / Building (a Site
//        from the Site master); only that node's buildings are listed.
//     5. Before saving, open complaints with the same incident number or LINKID are shown so a
//        follow-up message is not logged as a new complaint.
//
// Change log
//   2026-09-26  File created with the doctype.
//   2026-09-30  Complaint form logic added (operator types, paste/screenshot parsing, LINKID
//               matching, duplicate check). Date taken from the git commit "complaint type added".
//   2026-10-07  Site picker added: filtered by Node ID, fills Society / Building and Node ID.
//   2026-10-07  Added this header, a description on every function, and a date on each.
//   2026-10-08  Node ID is now a link to the Node master. The Site field is the Society /
//               Building field; the old free-text name is hidden and copied from the Site.
//   2026-10-08  Airtel PON TT messages: port, society and customer count read in any order
//               (e.g. node 24W from "24W-G1/1/15" placed before the count).
//   2026-10-09  OH maintenance flow: ILL / LMC / Transport types for Airtel and Vodafone; other
//               operators (Gazon, Jio, ...) get every link type. Resolved complaints no longer
//               count as open in the duplicate check. Restoration, RFO, MTTR and SLA fields are
//               on the form (worked out by the server).
//   2026-10-09  Transport removed from the link types: it is the same as Backbone.
//   2026-10-24  Node ID links to the GIS Node master (FTTH Tracker); the separate Node master
//               was merged into it.
//   2026-11-02  Workflow stage tracker at the top of the form (complaint_stage_tracker, drawn by
//               evision.stepper from public/js/evision.js).
//   2026-11-02  Card layout for the form (evision.form_style).
//   2026-11-26  Picking a vendor empties Rider / Splicer / 2nd Rider / 2nd Splicer (hidden then).
//   2026-11-27  Airtel PON TT messages: the society line ("DAD COMPLEX ..., BIBWEWADI") is read
//               too (society_hint) and matched to the node's Sites and Network Links by words
//               (match_building / best_building_match), so Society / Building and LINKID fill
//               themselves when one building on the node clearly matches (user's request).
//   2026-11-27  Reading no longer stops at the down time: in messages where the date comes first,
//               the port (node) and society after it were lost.
//   2026-11-27  Node or LINKID chosen: Area and Area Manager from the node's team area, Area 1-6
//               (fill_team_area_manager; user's request "assign area manager according to area").
//   2026-11-27  A customer account line ("02036688293_wifi") is no longer taken as the building
//               (user's message: "D1J / date / 9 / 02036688293_wifi / D1J-L2/1/3 / NAMDEV SRUSHTI").
//   2026-11-27  Rider / Splicer pickers list the chosen team's riders / splicers; a team's only
//               rider / splicer is filled in (load_team_people).
//   2026-11-28  No team and no vendor: the EVisions team of the node's team area is filled in.
// ---------------------------------------------------------------------------------------------

// Workflow states after which a complaint no longer counts as open (for the duplicate check).
const CLOSED_STATES = ["Resolved", "Closed"];

// Date: 2026-11-02
// The OHP Maintenance Workflow's main path (fixtures/workflow.json), with short tracker labels.
// "Rejected" is not on the path: the Maintenance Team sent it back and the Area Manager reassigns
// it, so the tracker shows it at the Maintenance Team step in the stopped (red) style.
const COMPLAINT_STEPS = [
	{ key: "New", label: "New" },
	{ key: "NOC Verification", label: "NOC Verification" },
	{ key: "Assigned to Area Manager", label: "Area Manager" },
	{ key: "Assigned to Maintenance Team", label: "Maintenance Team" },
	{ key: "Accepted", label: "Accepted" },
	{ key: "In Progress", label: "In Progress" },
	{ key: "Fiber Restored", label: "Fiber Restored" },
	{ key: "Awaiting Operator Confirmation", label: "Operator Confirmation" },
	{ key: "Resolved", label: "Resolved" },
	{ key: "Closed", label: "Closed" },
];

// Date: 2026-11-02
// Draws the stage tracker for the complaint's workflow state. Who acts at a step is read from the
// workflow's own transitions (the roles allowed to move a record out of that state), so the
// tracker follows any later change to the workflow without editing this file.
function complaint_stage_tracker(frm) {
	if (!window.evision || frm.is_new()) return;
	const state = frm.doc.workflow_state;
	if (!state) return;
	let transitions = [];
	try {
		transitions = frappe.workflow.get_all_transitions(frm.doctype) || [];
	} catch (e) {
		transitions = []; // no workflow loaded: the tracker just shows no owner
	}
	const roles_from = (s) => [...new Set(transitions.filter((t) => t.state === s).map((t) => t.allowed))];
	const steps = COMPLAINT_STEPS.map((s) => Object.assign({ title: s.key, owner: roles_from(s.key).join(" / ") }, s));
	const roles = roles_from(state);
	const owner = roles.join(" / ") || null;

	if (state === "Rejected") {
		evision.stepper(frm, {
			steps,
			current: "Assigned to Maintenance Team",
			state: "stopped",
			state_label: __("Rejected by Maintenance Team"),
			owner,
			roles,
		});
		return;
	}
	if (!steps.some((s) => s.key === state)) return;
	evision.stepper(frm, {
		steps,
		current: state,
		state: state === "Closed" ? "finished" : "active",
		owner: state === "Closed" ? null : owner,
		roles,
	});
}

// Every link type, for operators without their own list (2026-10-09).
const ALL_TYPES = ["Backbone", "FTTH", "Small Cell", "ILL", "LMC"];

// What NOC should paste, per operator.
const PASTE_HINTS = {
	Airtel: "Paste the Airtel WhatsApp message, or attach a screenshot of it on the right. Everything fills automatically.",
	Vodafone: "Attach the Vodafone HPSM screenshot on the right: its text is read and fills priority, alarm time, fault and location. Or paste the ticket text here.",
	Railtel: "Paste the Railtel message, or attach a screenshot of it. The link name/number is used to find the LINKID.",
};

// Complaint types per operator (the server enforces the same rule). Railtel has none,
// and only Airtel gives an incident number.
const OPERATOR_TYPES = {
	Airtel: ["Backbone", "FTTH", "ILL", "LMC"],
	Vodafone: ["Backbone", "Small Cell", "ILL", "LMC"],
	Railtel: [],
};

frappe.ui.form.on("Complaint Information", {
	// Date: 2026-11-26
	// A vendor sends its own people: picking a vendor empties Rider / Splicer / 2nd Rider /
	// 2nd Splicer (the fields are hidden while a vendor is set; the server does the same on save).
	mapped_vendor(frm) {
		if (!frm.doc.mapped_vendor) return;
		["rider", "splicer", "second_rider", "second_splicer"].forEach((f) => {
			if (frm.doc[f]) frm.set_value(f, null);
		});
	},

	// Date: 2026-09-30
	// Runs once when the form is built: set which LINKIDs and Sites can be picked.
	setup(frm) {
		// With a Node ID, only links on that node can be picked as LINKID.
		frm.set_query("linkid", () => (frm.doc.node_id ? { filters: { node_id: frm.doc.node_id } } : {}));
		// 2026-10-07: added with the Site master.
		// One node has many sites: with a Node ID, only that node's sites can be picked.
		frm.set_query("site", () => (frm.doc.node_id ? { filters: { node: frm.doc.node_id } } : {}));
		// 2026-11-27: with a team chosen, Rider / Splicer list only that team's riders / splicers
		const team_query = (role) => () => {
			const ids = (frm.__team_people || {})[role];
			return ids && ids.length ? { filters: { name: ["in", ids] } } : {};
		};
		frm.set_query("rider", team_query("Rider"));
		frm.set_query("second_rider", team_query("Rider"));
		frm.set_query("splicer", team_query("Splicer"));
		frm.set_query("second_splicer", team_query("Splicer"));
	},

	// Date: 2026-11-27
	// Team chosen: its riders / splicers become the choices, and a team's only rider or only
	// splicer is filled in (user's request "assign splicer and rider according to the team").
	maintenance_team(frm) {
		load_team_people(frm, true);
	},

	// Date: 2026-09-30
	// Form opened or reloaded: set the paste hint and type options for the chosen operator.
	// 2026-11-02: also draws the workflow stage tracker.
	refresh(frm) {
		// 2026-11-02: card layout for the form (evision.css section 5)
		if (window.evision) evision.form_style(frm);
		complaint_stage_tracker(frm);
		set_paste_hint(frm);
		set_type_options(frm);
		load_team_people(frm, false);   // 2026-11-27: Rider / Splicer choices from the team
		if (frm.is_new() && frm.doc.message_attachment) {
			frm.add_custom_button(__("Read Screenshot Again"), () => read_screenshot_text(frm));
		}
	},

	// Date: 2026-09-30
	// Operator changed: update the paste hint and type options; only Airtel keeps an INC number.
	operatorcustomer(frm) {
		set_paste_hint(frm);
		set_type_options(frm);
		if (frm.doc.operatorcustomer !== "Airtel" && frm.doc.incident_number) frm.set_value("incident_number", "");
	},

	// Date: 2026-09-30
	// Message pasted: parse it, fill the fields it contains, find the LINKID, check for duplicates.
	paste_message(frm) {
		const text = (frm.doc.paste_message || "").trim();
		if (!text) return;
		const p = emp_tracking.parse_complaint_message(text, frm.doc.operatorcustomer);

		if (p.operator && frm.doc.operatorcustomer && p.operator !== frm.doc.operatorcustomer) {
			frappe.msgprint(__("This message looks like {0}, but Operator is set to {1}. Please check the operator.", [p.operator, frm.doc.operatorcustomer]));
		}
		if (p.operator && !frm.doc.operatorcustomer) frm.set_value("operatorcustomer", p.operator);
		const op = frm.doc.operatorcustomer || p.operator;
		if (p.incident_number && op === "Airtel") frm.set_value("incident_number", p.incident_number);
		if (p.priority) frm.set_value("priority", p.priority);
		if (p.complaint_type && (OPERATOR_TYPES[op] || []).includes(p.complaint_type)) {
			frm.set_value("complaint_type", p.complaint_type);
		}
		if (p.section) frm.set_value("section", p.section);
		if (p.down_time) frm.set_value("complaint_date_and_time", p.down_time);
		for (const f of ["link_as_reported", "operator_site_name", "fault_reported", "operator_district",
			"operator_latitude", "operator_longitude", "operator_due_date", "customers_affected", "node_id"]) {
			if (p[f]) frm.set_value(f, p[f]);
		}
		frm.set_value("received_via", "WhatsApp");
		if (!frm.doc.complaint_details) frm.set_value("complaint_details", text);
		// 2026-11-27: the building named in the message, used to pick the node's Site and LINKID
		frm.__society_hint = p.society_hint || null;
		if (p.node_id && p.society_hint) match_building(frm, p.node_id, p.society_hint);

		const filled = Object.entries(p).filter(([, v]) => v).map(([k]) => k.replace(/_/g, " "));
		frappe.show_alert({
			message: filled.length ? __("Filled from message: {0}", [filled.join(", ")]) : __("Nothing recognised. Please fill the form by hand."),
			indicator: filled.length ? "green" : "orange",
		});

		// 2026-10-08: Node ID is a link now; a node missing from the master is dropped.
		// 2026-10-24: the master is GIS Node (Node was merged into it).
		if (p.node_id) {
			frappe.db.exists("GIS Node", p.node_id).then((found) => {
				if (!found) frappe.msgprint(__("Node {0} from the message is not in the GIS Node master. Add it there, or pick the node by hand.", [p.node_id]));
			});
		}
		if (p.node_id && !frm.doc.linkid) pick_link_by_node(frm, p.node_id);
		else if (p.link_hint && !frm.doc.linkid) suggest_link(frm, p.link_hint);
		check_duplicates(frm, false);
	},

	// Date: 2026-09-30
	// A screenshot was attached: read its text into the paste box, which then fills the form.
	message_attachment(frm) {
		if (frm.doc.message_attachment && frm.is_new()) read_screenshot_text(frm);
	},

	// Date: 2026-09-30
	// Incident number changed: warn if an open complaint already has it.
	incident_number(frm) {
		check_duplicates(frm, false);
	},

	// Date: 2026-09-30
	// Node ID changed: upper-case it, drop a Site or LINKID from another node, pick the node's link.
	node_id(frm) {
		const node = (frm.doc.node_id || "").trim().toUpperCase();
		if (node !== frm.doc.node_id) {
			frm.set_value("node_id", node);
			return;
		}
		if (!node) return;
		fill_team_area_manager(frm, node); // 2026-11-27
		// 2026-10-07: clear the Site when the Node ID changes to a different node.
		if (frm.doc.site) {
			// A site from another node is no longer valid.
			frappe.db.get_value("Site", frm.doc.site, "node").then((r) => {
				if ((r.message || {}).node !== node) frm.set_value("site", "");
			});
		}
		if (frm.doc.linkid) {
			// A LINKID from another node is no longer valid.
			frappe.db.get_value("Network Link", frm.doc.linkid, "node_id").then((r) => {
				if ((r.message || {}).node_id !== node) frm.set_value("linkid", "");
			});
		} else {
			pick_link_by_node(frm, node);
		}
	},

	// Date: 2026-10-07
	// Society / Building (Site) picked: copy its name, and fill the Node ID if empty.
	async site(frm) {
		if (!frm.doc.site) {
			frm.set_value("society_name", "");
			return;
		}
		// ETIPL Code and B Location arrive through fetch_from. Here: the node and society name.
		const site = await frappe.db.get_value("Site", frm.doc.site, ["site_name", "node"]);
		const s = site?.message || {};
		if (!frm.doc.node_id && s.node) await frm.set_value("node_id", s.node);
		if (s.site_name && frm.doc.society_name !== s.site_name) await frm.set_value("society_name", s.site_name);
	},

	// Date: 2026-09-30
	// LINKID picked: fill node, type, section, society and Area Manager from the Network Link.
	async linkid(frm) {
		check_duplicates(frm, false);
		if (!frm.doc.linkid) return;
		// Area, location, coordinates, team, vendor and node info arrive through fetch_from.
		// Here: the editable fields NOC hasn't filled yet, plus the Area Manager.
		const link = await frappe.db.get_value("Network Link", frm.doc.linkid,
			["network_type", "section", "society_building", "area", "node_id"]);
		const l = link?.message || {};
		if (!frm.doc.node_id && l.node_id) await frm.set_value("node_id", l.node_id);
		const allowed = OPERATOR_TYPES[frm.doc.operatorcustomer];
		if (!frm.doc.complaint_type && l.network_type && (!allowed || allowed.includes(l.network_type))) {
			await frm.set_value("complaint_type", l.network_type);
		}
		if (!frm.doc.section && l.section) await frm.set_value("section", l.section);
		if (!frm.doc.society_name && l.society_building) await frm.set_value("society_name", l.society_building);
		// 2026-11-27: the team area's manager (Field Staff) comes from the node; the login below
		// stays as before for areas that have one
		if (l.node_id && await fill_team_area_manager(frm, l.node_id)) return;
		if (l.area) {
			const am = await frappe.db.get_value("Area", l.area, "area_manager");
			const manager = am?.message?.area_manager;
			if (manager && !frm.doc.area_manager) await frm.set_value("area_manager", manager);
			if (!manager && !frm.doc.area_manager_staff) {
				frappe.show_alert({ message: __("Area {0} has no Area Manager set. Please choose one.", [l.area]), indicator: "orange" });
			}
		}
	},

	// Date: 2026-09-30
	// Before save: if an open complaint matches, ask NOC to confirm before saving a new one.
	async validate(frm) {
		if (frm.__duplicate_ok) return;
		const dups = await find_duplicates(frm);
		if (!dups.length) return;
		frappe.validated = false;
		frappe.confirm(
			duplicate_message(dups) + "<br><br>" + __("Save this as a new complaint anyway?"),
			() => {
				frm.__duplicate_ok = true;
				frm.save();
			}
		);
	},
});

// Field labels that change with the operator.
const OPERATOR_LABELS = {
	Airtel: { complaint_date_and_time: "Down Time" },
	Vodafone: { complaint_date_and_time: "Alarm Occurred Time" },
	Railtel: { complaint_date_and_time: "Complaint Received On" },
};
const DEFAULT_LABELS = { complaint_date_and_time: "Complaint Received On" };

// Screenshot reading (OCR) runs in the NOC's browser with Tesseract.js, so the image never
// leaves the NOC's computer. The library and its English data (~10 MB) download on first use.
const TESSERACT_URL = "https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js";

// Date: 2026-09-30
// Loads the Tesseract.js text-reading library once; resolves when it is ready to use.
function load_tesseract() {
	if (window.Tesseract) return Promise.resolve();
	return new Promise((resolve, reject) => {
		const s = document.createElement("script");
		s.src = TESSERACT_URL;
		s.onload = resolve;
		s.onerror = () => reject(new Error(__("Could not load the text reader. Check the internet connection.")));
		document.head.appendChild(s);
	});
}

// Date: 2026-09-30
// Small or phone-photo screenshots read far better when enlarged and greyscaled first.
async function prepare_image(url) {
	const blob = await (await fetch(url, { credentials: "same-origin" })).blob();
	const bitmap = await createImageBitmap(blob);
	const scale = Math.max(1, Math.min(3, 1800 / bitmap.width));
	const canvas = document.createElement("canvas");
	canvas.width = Math.round(bitmap.width * scale);
	canvas.height = Math.round(bitmap.height * scale);
	const ctx = canvas.getContext("2d");
	ctx.filter = "grayscale(1) contrast(1.3)";
	ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
	return canvas;
}

// Date: 2026-09-30
// Reads the text of the attached screenshot and puts it in the paste box, which fills the form.
async function read_screenshot_text(frm) {
	frappe.dom.freeze(__("Reading text from the screenshot…"));
	try {
		await load_tesseract();
		const image = await prepare_image(frm.doc.message_attachment);
		const { data } = await window.Tesseract.recognize(image, "eng");
		const text = (data.text || "").trim();
		if (!text) {
			frappe.msgprint(__("No text could be read from this image. Please fill the form by hand."));
			return;
		}
		// Setting the paste box runs the same parser as pasted text.
		await frm.set_value("paste_message", text);
		frappe.show_alert({
			message: __("Text read from the screenshot. Please check the filled fields: photos can be misread."),
			indicator: "blue",
		}, 8);
	} catch (e) {
		frappe.msgprint(e.message || String(e));
	} finally {
		frappe.dom.unfreeze();
	}
}

// Date: 2026-09-30
// Limits Complaint Type to the types the chosen operator uses, clearing a type that no longer fits.
// 2026-10-09: operators without their own list (Gazon, Jio, ...) get every type.
function set_type_options(frm) {
	const types = OPERATOR_TYPES[frm.doc.operatorcustomer] || ALL_TYPES;
	frm.set_df_property("complaint_type", "options", ["", ...types].join("\n"));
	if (frm.doc.complaint_type && !types.includes(frm.doc.complaint_type)) frm.set_value("complaint_type", "");
}

// Date: 2026-09-30
// Sets the paste box label and hint, and the date field's label, for the chosen operator.
function set_paste_hint(frm) {
	const op = frm.doc.operatorcustomer;
	frm.set_df_property("paste_message", "description", PASTE_HINTS[op] || "");
	frm.set_df_property("paste_message", "label", op ? __("Paste {0} Message", [op]) : __("Paste Message"));
	const labels = OPERATOR_LABELS[op] || DEFAULT_LABELS;
	for (const [field, label] of Object.entries(labels)) frm.set_df_property(field, "label", __(label));
}

// Date: 2026-09-30
// Returns open complaints (other than this one) with the same incident number or LINKID.
async function find_duplicates(frm) {
	const or_filters = [];
	if (frm.doc.incident_number) or_filters.push(["incident_number", "=", frm.doc.incident_number]);
	if (frm.doc.linkid) or_filters.push(["linkid", "=", frm.doc.linkid]);
	if (!or_filters.length) return [];
	const filters = [["workflow_state", "not in", CLOSED_STATES]];
	if (!frm.is_new()) filters.push(["name", "!=", frm.doc.name]);
	return frappe.db.get_list("Complaint Information", {
		filters,
		or_filters,
		fields: ["name", "incident_number", "linkid", "workflow_state", "complaint_date_and_time"],
		limit: 10,
	});
}

// Date: 2026-09-30
// Shows an "Already open" message when find_duplicates() finds any.
async function check_duplicates(frm) {
	const dups = await find_duplicates(frm);
	if (dups.length) frappe.msgprint({ title: __("Already open"), indicator: "orange", message: duplicate_message(dups) });
}

// Date: 2026-09-30
// Builds the HTML list of duplicate complaints shown to NOC.
function duplicate_message(dups) {
	const rows = dups
		.map(
			(d) =>
				`<li><a href="/desk/complaint-information/${encodeURIComponent(d.name)}">${frappe.utils.escape_html(d.name)}</a>` +
				` · ${frappe.utils.escape_html(d.incident_number || "-")} · ${frappe.utils.escape_html(d.linkid || "-")}` +
				` · <b>${frappe.utils.escape_html(d.workflow_state || "")}</b></li>`
		)
		.join("");
	return __("An open complaint already exists for this incident number or LINKID:") + `<ul>${rows}</ul>` +
		__("If this is a follow-up (\"share ETR\", \"expedite\"), update that complaint instead.");
}

// Date: 2026-09-30
// Airtel FTTH: the LINKID is the Network Link on the message's node (e.g. MPJ).
async function pick_link_by_node(frm, node) {
	// 2026-11-27: society_building too, and up to 500 links, so the message's building can pick one
	const links = await frappe.db.get_list("Network Link", { filters: { node_id: node }, fields: ["name", "society_building"], limit: 500 });
	const by_name = links.length > 1 && frm.__society_hint ? best_building_match(frm.__society_hint, links, "society_building") : null;
	if (by_name) {
		await frm.set_value("linkid", by_name.name);
		frappe.show_alert({ message: __("LINKID {0} matched to {1}", [by_name.name, by_name.society_building]), indicator: "green" });
	} else if (links.length === 1) {
		await frm.set_value("linkid", links[0].name);
		frappe.show_alert({ message: __("LINKID {0} is on node {1}", [links[0].name, node]), indicator: "green" });
	} else if (links.length > 1) {
		frappe.show_alert({ message: __("Several links are on node {0}. Please pick the LINKID.", [node]), indicator: "orange" });
	} else {
		frappe.msgprint(__("No Network Link has Node ID {0}. Add it to the right link first, or check the node name.", [node]));
	}
}

// Date: 2026-11-27
// The chosen Maintenance Team's active members by role, for the Rider / Splicer pickers. With
// fill set (team just chosen), an empty Rider / Splicer gets the team's only rider / splicer.
async function load_team_people(frm, fill) {
	frm.__team_people = null;
	if (!frm.doc.maintenance_team) return;
	const team = await frappe.db.get_doc("Maintenance Team", frm.doc.maintenance_team).catch(() => null);
	if (!team) return;
	const people = { Rider: [], Splicer: [] };
	(team.members || []).forEach((m) => {
		if (m.active && m.employee && people[m.role]) people[m.role].push(m.employee);
	});
	frm.__team_people = people;
	if (!fill || frm.doc.mapped_vendor) return;   // a vendor sends its own people
	if (!frm.doc.rider && people.Rider.length === 1) await frm.set_value("rider", people.Rider[0]);
	if (!frm.doc.splicer && people.Splicer.length === 1) await frm.set_value("splicer", people.Splicer[0]);
}

// Date: 2026-11-27
// Area and Area Manager from the node's EVision team area (Area 1-6): the manager follows the
// area, the login only fills an empty field. True when the node has a team area.
async function fill_team_area_manager(frm, node) {
	const r = await frappe.xcall("emp_tracking.emp_tracking.doctype.area.area.team_area_of_node",
		{ node, area: frm.doc.area || null });
	if (!r || !r.area) return false;
	// a node's team area replaces the Area; a locality (no node team area) stays as it is
	const changed = r.from_node && frm.doc.area !== r.area;
	if (changed) await frm.set_value("area", r.area);
	if (frm.doc.team_area !== r.area) await frm.set_value("team_area", r.area);
	// 2026-11-28: no team and no vendor yet -> the EVisions team of that area (its riders /
	// splicers then become the choices); a team or vendor already chosen is kept
	if (r.team && !frm.doc.maintenance_team && !frm.doc.mapped_vendor) await frm.set_value("maintenance_team", r.team);
	if (r.staff && (changed || !frm.doc.area_manager_staff)) await frm.set_value("area_manager_staff", r.staff);
	if (r.user && (changed || !frm.doc.area_manager)) await frm.set_value("area_manager", r.user);
	return true;
}

// Date: 2026-11-27
// The message names a building on the node: pick that node's Site (Society / Building) by name.
// The LINKID is picked by pick_link_by_node(), which uses the same hint (frm.__society_hint).
async function match_building(frm, node, hint) {
	if (frm.doc.site) return;
	const sites = await frappe.db.get_list("Site", { filters: { node }, fields: ["name", "site_name"], limit: 1000 });
	const best = best_building_match(hint, sites, "site_name");
	if (best) {
		await frm.set_value("site", best.name);
		frappe.show_alert({ message: __("Building matched: {0}", [best.site_name]), indicator: "green" });
	} else {
		frappe.show_alert({ message: __("Building \"{0}\" from the message is not a Site of node {1}. Please pick it.", [hint, node]), indicator: "orange" });
	}
}

// Date: 2026-11-27
// Best record for a building name from a message, or null when none (or two) match clearly.
// Words are compared without case, punctuation or filler words; a record must have at least 3 of
// every 4 of its words in the message, and the message's building part (before the first comma,
// e.g. "DAD COMPLEX DEFENCE ACCOUNT DEPARTMENT" of "..., BIBWEWADI") half of its words in the record.
function best_building_match(hint, records, field) {
	const FILLER = new Set(["SOCIETY", "SOC", "CHS", "CHSL", "APARTMENT", "APARTMENTS", "APPT", "APT", "BUILDING",
		"BLDG", "CO", "OP", "HSG", "LTD", "PVT", "THE", "AND", "OF", "NEW"]);
	const words = (s) => (s || "").toUpperCase().replace(/[^A-Z0-9]+/g, " ").split(" ").filter((w) => w && !FILLER.has(w));
	const all = new Set(words(hint));
	const head = words(hint.split(",")[0]);
	let best = null, best_score = 0, tie = false;
	for (const r of records) {
		const w = words(r[field]);
		if (!w.length || !head.length) continue;
		const in_msg = w.filter((x) => all.has(x)).length / w.length;
		const in_rec = head.filter((x) => w.includes(x)).length / head.length;
		if (in_msg < 0.75 || in_rec < 0.5) continue;
		const score = in_msg + in_rec;
		if (score > best_score) {
			best = r; best_score = score; tie = false;
		} else if (score === best_score && r[field] !== best[field]) {
			tie = true;
		}
	}
	return tie ? null : best;
}

// Date: 2026-09-30
// Looks for a Network Link matching the link name/number from the message; sets it if exactly one matches.
async function suggest_link(frm, hint) {
	const like = `%${hint}%`;
	const links = await frappe.db.get_list("Network Link", {
		or_filters: [
			["name", "like", like],
			["operator_link_id", "like", like],
			["section", "like", like],
			["society_building", "like", like],
			["node_id", "like", like],
			["gis_node_id", "like", like],
			["node_a", "like", like],
			["node_b", "like", like],
			["location", "like", like],
		],
		fields: ["name"],
		limit: 5,
	});
	if (links.length === 1) {
		frm.set_value("linkid", links[0].name);
		frappe.show_alert({ message: __("LINKID {0} matched from the message", [links[0].name]), indicator: "green" });
	} else if (links.length > 1) {
		frappe.show_alert({ message: __("Several links match \"{0}\". Please pick the LINKID.", [hint]), indicator: "orange" });
	}
}

// Date: 2026-09-30
// Parses operator WhatsApp/Telegram messages. Kept as a pure function so it can be tested on its own.
window.emp_tracking = window.emp_tracking || {};
emp_tracking.parse_complaint_message = function (text, operator) {
	const out = {};
	const one_line = text.replace(/\s+/g, " ");
	const pad = (n) => String(n).padStart(2, "0");

	// Vodafone HPSM ticket: "HPSM Ticket ID : 40983629" style lines. Text read from a photo
	// (OCR) often turns ":" into "©", "%" or "*", so any of those count as the separator.
	const SEP = "\\s*(?:[:©%*;\"|]|\\.(?=\\s))?\\s*";
	const clean = (s) => (s || "").replace(/^[\s:©%*;"|.,'-]+|[\s|!:;.,'-]+$/g, "");
	const vi_value = (label) => {
		const m = text.match(new RegExp(label + SEP + "([^\\n]+(?:\\n(?!\\s*[A-Za-z][A-Za-z ]{2,30}" + SEP + ")[^\\n]+)*)", "i"));
		return m ? clean(m[1].replace(/\s+/g, "")) : null;
	};
	const line = (label) => {
		const m = text.match(new RegExp(label + SEP + "([^\\n]+)", "i"));
		return m ? clean(m[1]) : null;
	};
	// OCR can drop the decimal point: 1856527 -> 18.56527 (Indian lat/long have 2 whole digits)
	const coord = (s) => {
		const digits = ((s || "").match(/\d[\d.]*/) || [""])[0];
		if (!digits) return NaN;
		return digits.includes(".") ? parseFloat(digits) : parseFloat(digits.slice(0, 2) + "." + digits.slice(2));
	};
	const iso = (s) => {
		const m = (s || "").match(/(\d{4})-(\d{2})-(\d{2})T?\s*(\d{2})[:.](\d{2})(?:[:.](\d{2}))?/);
		return m ? `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}:${m[6] || "00"}` : null;
	};
	if (operator === "Vodafone" || /HPSM\s*Ticket\s*ID/i.test(text)) {
		out.operator = "Vodafone";
		const id = (vi_value("HPSM\\s*Ticket\\s*ID") || "").match(/\d{6,}/);
		if (id) out.incident_number = id[0];
		const pr = (line("Task\\s*Priority") || "").match(/P\s*([1-4])/i);
		if (pr) out.priority = { 1: "Critical", 2: "High", 3: "Medium", 4: "Low" }[pr[1]];
		const site = (vi_value("Site\\s*Name") || "").replace(/_TO(\d)/g, "_T0$1");
		if (/^[A-Z]{2}_[A-Z]/.test(site)) out.link_hint = out.operator_site_name = site;
		// Alarm time is the first date-time on the ticket (its label often splits over two lines)
		const alarm = iso(vi_value("Alarm\\s*Occ?urr?e?d?\\s*Time")) || iso(text) || iso(vi_value("Open\\s*Date"));
		if (alarm) out.down_time = alarm;
		const due = iso(vi_value("Due\\s*Date"));
		if (due) out.operator_due_date = due;
		const task = line("Task\\s*Type");
		if (task) out.fault_reported = task;
		const district = line("District");
		if (district) out.operator_district = district;
		const lat = coord(line("Latitude")), lng = coord(line("Longitude"));
		if (lat > 5 && lat < 40) out.operator_latitude = lat;
		if (lng > 65 && lng < 100) out.operator_longitude = lng;
		if (/FTTH|PON/i.test(one_line)) out.complaint_type = "FTTH";
		return out;
	}
	if (operator === "Railtel") out.operator = "Railtel";

	// Airtel: INC000254439929, optionally "-High"
	const inc = one_line.match(/\bINC\d{6,}\b/i);
	if (inc) {
		out.incident_number = inc[0].toUpperCase();
		out.operator = "Airtel";
		const pr = one_line.match(/\bINC\d{6,}\s*-\s*(Critical|High|Medium|Low)\b/i);
		if (pr) out.priority = pr[1][0].toUpperCase() + pr[1].slice(1).toLowerCase();
	} else if (/\brail\s*tel\b/i.test(one_line)) {
		out.operator = "Railtel";
	}

	// "Section - Chakan hill to chakan chowk" => Backbone
	const sec = text.match(/Section\s*[-:–]\s*(.+)/i);
	if (sec) {
		// stop at the next label when the message arrives on one line
		out.section = sec[1].split(/\s+(?:Down\s*(?:Time|Since)|Ageing|Aging|INC\d)/i)[0].trim();
		out.complaint_type = "Backbone";
		out.link_hint = out.link_as_reported = out.section;
	} else if (/\b(PON|FTTH)\b/i.test(one_line)) {
		out.complaint_type = "FTTH";
	}

	// Airtel FTTH, one value per line after the INC number. The 3-character node ID is used, and
	// (2026-11-27) the society line as society_hint; PON ports are not kept:
	//   S1B / 2 (customers down) / 9/9/2026 4:22:39 PM (down time)          -> node S1B
	//   PON TT / 17 / MPJ-H1/5/3 / PLANET MILLENNIUM ... / [down time]      -> node MPJ
	//   PON TT / 24W-G1/1/15 / VRUNDAVAN SANKUL,SHIVANE / 16 / [down time]   -> node 24W
	// 2026-10-08: after "PON TT" the port, society and customer count can come in any order.
	if (inc && !sec) {
		const lines = text.split(/\n/).map((l) => l.trim().replace(/,$/, "").trim()).filter(Boolean);
		const i = lines.findIndex((l) => /^INC\d{6,}\b/i.test(l));
		if (i >= 0) {
			let rest = lines.slice(i + 1);
			const is_pon_tt = /^PON\s*TT$/i.test(rest[0] || "");
			if (is_pon_tt) rest = rest.slice(1);
			let node = null;
			if (!is_pon_tt && /^[A-Z0-9]{3}$/i.test(rest[0] || "") && !/^\d+$/.test(rest[0])) node = rest.shift();   // S1B
			let customers = null;
			let society = null;
			for (const l of rest) {
				if (/^\d{1,2}:\d{2}\s*(?:am|pm)?$/i.test(l)) continue;   // WhatsApp's own "5:17 PM"
				const t = parse_date_time(l);
				if (t) {
					// 2026-11-27: the first date is the down time; reading goes on, because the date can
					// come before the port and society ("date / 1 / GGG-L1/1/11 / DAD COMPLEX ...")
					if (!out.down_time) out.down_time = t;
					continue;
				}
				if (customers === null && /^\d{1,5}$/.test(l)) {
					customers = parseInt(l, 10);
					continue;
				}
				const port = l.match(/^([A-Z0-9]{3})-[A-Z0-9]{1,4}(?:\/\d{1,3}){1,3}$/i);   // MPJ-H1/5/3 -> MPJ
				if (port) {
					if (!node) node = port[1];
					continue;
				}
				// 2026-11-27: a customer account such as "02036688293_wifi" (one word with a long
				// number) is not the society
				if (!/\s/.test(l) && /\d{5,}/.test(l)) continue;
				// 2026-11-27: the first line with words is the society, e.g. "VRUNDAVAN SANKUL,SHIVANE"
				if (!society && /[A-Z]{3,}/i.test(l)) society = l;
			}
			if (is_pon_tt || node || customers !== null) {
				out.complaint_type = "FTTH";
				if (customers !== null) out.customers_affected = customers;
				if (node) out.node_id = node.toUpperCase();
				if (society) out.society_hint = society;
			}
		}
	}

	// Railtel style "SBI Zonal to SBI East street 3861 link down"
	if (!out.link_hint) {
		const ld = one_line.match(/(?:^|[.\n]|\s)([A-Za-z0-9][^.\n]{2,80}?)\s+link\s+down/i);
		if (ld) {
			// drop WhatsApp mentions like "@Evision NOC @EVISION NOC 2"
			out.link_as_reported = ld[1]
				.replace(/@\S+(?:\s+NOC(?:\s+\d)?\b)?/gi, " ")
				.replace(/^\s*NOC(?:\s+\d)?\s+/i, "")
				.replace(/\s+/g, " ")
				.trim();
			const num = ld[1].match(/\b(\d{3,})\b/);
			out.link_hint = num ? num[1] : ld[1].trim();
		}
	}

	// "Down Time :09/09/2026 03:09 pm"
	const dt = one_line.match(/Down\s*(?:Time|Since)\s*[:\-]?\s*(\d{1,2}[\/.\-]\d{1,2}[\/.\-]\d{4}\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?)/i);
	if (dt && !out.down_time) out.down_time = parse_date_time(dt[1]);
	return out;
};

// "09/09/2026 03:09 pm" or "9/9/2026 4:22:39 PM" -> "2026-09-09 16:22:39".
// Day first (Indian format) unless that is impossible, e.g. 9/13/2026 is read as 13 Sep.
function parse_date_time(s) {
	const m = s.match(/(\d{1,2})[\/.\-](\d{1,2})[\/.\-](\d{4})\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?/i);
	if (!m) return null;
	let [, a, b, y, hh, mm, ss, ap] = m;
	let [day, month] = [parseInt(a, 10), parseInt(b, 10)];
	if (month > 12 && day <= 12) [day, month] = [month, day];
	let h = parseInt(hh, 10);
	if (ap) {
		ap = ap.toLowerCase();
		if (ap === "pm" && h < 12) h += 12;
		if (ap === "am" && h === 12) h = 0;
	}
	const pad = (n) => String(n).padStart(2, "0");
	return `${y}-${pad(month)}-${pad(day)} ${pad(h)}:${mm}:${ss || "00"}`;
}
