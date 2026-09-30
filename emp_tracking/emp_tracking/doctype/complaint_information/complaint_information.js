// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

// Workflow states after which a complaint no longer counts as open (for the duplicate check).
const CLOSED_STATES = ["Closed"];

// What NOC should paste, per operator.
const PASTE_HINTS = {
	Airtel: "Paste the Airtel WhatsApp message, or attach a screenshot of it on the right. Everything fills automatically.",
	Vodafone: "Attach the Vodafone HPSM screenshot on the right: its text is read and fills priority, alarm time, fault and location. Or paste the ticket text here.",
	Railtel: "Paste the Railtel message, or attach a screenshot of it. The link name/number is used to find the LINKID.",
};

// Complaint types per operator (the server enforces the same rule). Railtel has none,
// and only Airtel gives an incident number.
const OPERATOR_TYPES = {
	Airtel: ["Backbone", "FTTH"],
	Vodafone: ["Backbone", "Small Cell"],
	Railtel: [],
};

frappe.ui.form.on("Complaint Information", {
	setup(frm) {
		// With a Node ID, only links on that node can be picked as LINKID.
		frm.set_query("linkid", () => (frm.doc.node_id ? { filters: { node_id: frm.doc.node_id } } : {}));
	},

	refresh(frm) {
		set_paste_hint(frm);
		set_type_options(frm);
		if (frm.is_new() && frm.doc.message_attachment) {
			frm.add_custom_button(__("Read Screenshot Again"), () => read_screenshot_text(frm));
		}
	},

	operatorcustomer(frm) {
		set_paste_hint(frm);
		set_type_options(frm);
		if (frm.doc.operatorcustomer !== "Airtel" && frm.doc.incident_number) frm.set_value("incident_number", "");
	},

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

		const filled = Object.entries(p).filter(([, v]) => v).map(([k]) => k.replace(/_/g, " "));
		frappe.show_alert({
			message: filled.length ? __("Filled from message: {0}", [filled.join(", ")]) : __("Nothing recognised. Please fill the form by hand."),
			indicator: filled.length ? "green" : "orange",
		});

		if (p.node_id && !frm.doc.linkid) pick_link_by_node(frm, p.node_id);
		else if (p.link_hint && !frm.doc.linkid) suggest_link(frm, p.link_hint);
		check_duplicates(frm, false);
	},

	// A screenshot was attached: read its text into the paste box, which then fills the form.
	message_attachment(frm) {
		if (frm.doc.message_attachment && frm.is_new()) read_screenshot_text(frm);
	},

	incident_number(frm) {
		check_duplicates(frm, false);
	},

	node_id(frm) {
		const node = (frm.doc.node_id || "").trim().toUpperCase();
		if (node !== frm.doc.node_id) {
			frm.set_value("node_id", node);
			return;
		}
		if (!node) return;
		if (frm.doc.linkid) {
			// A LINKID from another node is no longer valid.
			frappe.db.get_value("Network Link", frm.doc.linkid, "node_id").then((r) => {
				if ((r.message || {}).node_id !== node) frm.set_value("linkid", "");
			});
		} else {
			pick_link_by_node(frm, node);
		}
	},

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
		if (l.area) {
			const am = await frappe.db.get_value("Area", l.area, "area_manager");
			const manager = am?.message?.area_manager;
			if (manager && !frm.doc.area_manager) await frm.set_value("area_manager", manager);
			if (!manager) {
				frappe.show_alert({ message: __("Area {0} has no Area Manager set. Please choose one.", [l.area]), indicator: "orange" });
			}
		}
	},

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

function set_type_options(frm) {
	const types = OPERATOR_TYPES[frm.doc.operatorcustomer];
	if (!types) return;
	frm.set_df_property("complaint_type", "options", ["", ...types].join("\n"));
	if (frm.doc.complaint_type && !types.includes(frm.doc.complaint_type)) frm.set_value("complaint_type", "");
}

function set_paste_hint(frm) {
	const op = frm.doc.operatorcustomer;
	frm.set_df_property("paste_message", "description", PASTE_HINTS[op] || "");
	frm.set_df_property("paste_message", "label", op ? __("Paste {0} Message", [op]) : __("Paste Message"));
	const labels = OPERATOR_LABELS[op] || DEFAULT_LABELS;
	for (const [field, label] of Object.entries(labels)) frm.set_df_property(field, "label", __(label));
}

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

async function check_duplicates(frm) {
	const dups = await find_duplicates(frm);
	if (dups.length) frappe.msgprint({ title: __("Already open"), indicator: "orange", message: duplicate_message(dups) });
}

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

// Airtel FTTH: the LINKID is the Network Link on the message's node (e.g. MPJ).
async function pick_link_by_node(frm, node) {
	const links = await frappe.db.get_list("Network Link", { filters: { node_id: node }, fields: ["name"], limit: 5 });
	if (links.length === 1) {
		await frm.set_value("linkid", links[0].name);
		frappe.show_alert({ message: __("LINKID {0} is on node {1}", [links[0].name, node]), indicator: "green" });
	} else if (links.length > 1) {
		frappe.show_alert({ message: __("Several links are on node {0}. Please pick the LINKID.", [node]), indicator: "orange" });
	} else {
		frappe.msgprint(__("No Network Link has Node ID {0}. Add it to the right link first, or check the node name.", [node]));
	}
}

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

	// Airtel FTTH, one value per line after the INC number. Only the 3-character node ID is
	// used; PON ports and society names are ignored:
	//   S1B / 2 (customers down) / 9/9/2026 4:22:39 PM (down time)          -> node S1B
	//   PON TT / 17 / MPJ-H1/5/3 / PLANET MILLENNIUM ... / [down time]      -> node MPJ
	if (inc && !sec) {
		const lines = text.split(/\n/).map((l) => l.trim().replace(/,$/, "").trim()).filter(Boolean);
		const i = lines.findIndex((l) => /^INC\d{6,}\b/i.test(l));
		if (i >= 0) {
			let rest = lines.slice(i + 1);
			const is_pon_tt = /^PON\s*TT$/i.test(rest[0] || "");
			if (is_pon_tt) rest = rest.slice(1);
			let node = null;
			if (!is_pon_tt && /^[A-Z0-9]{3}$/i.test(rest[0] || "") && !/^\d+$/.test(rest[0])) node = rest.shift();   // S1B
			if (/^\d{1,5}$/.test(rest[0] || "")) {
				out.complaint_type = "FTTH";
				out.customers_affected = parseInt(rest.shift(), 10);
				for (const l of rest) {
					if (/^\d{1,2}:\d{2}\s*(?:am|pm)?$/i.test(l)) continue;   // WhatsApp's own "5:17 PM"
					const t = parse_date_time(l);
					if (t) {
						out.down_time = t;
						break;
					}
					const port = l.match(/^([A-Z0-9]{3})-[A-Z0-9]{1,4}(?:\/\d{1,3}){1,3}$/i);   // MPJ-H1/5/3 -> MPJ
					if (port && !node) node = port[1];
				}
				if (node) out.node_id = node.toUpperCase();
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
