// Copyright (c) 2026, Softworld and contributors
// For license information, please see license.txt
//
// FTTH Work Order form: lookups, map links and the Route Map distance label.
//
// Change log
//   2026-10-29  Route Map shows the route length in metres on the line and under the map.
//   2026-10-29  Save button named after the next owner, as on New Project ("Send to Area Manager",
//               "Send to Project Head", "Send to Fiber Team", "Mark RFS Done", "Close Project").

const ftth = {
	parse_lat_long(text) {
		const nums = String(text || "").match(/-?\d+(?:\.\d+)?/g);
		if (!nums || nums.length < 2) return [null, null];
		const lat = parseFloat(nums[0]);
		const lon = parseFloat(nums[1]);
		if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return [null, null];
		return [lat, lon];
	},
	maps_url(lat, lon) {
		return `https://www.google.com/maps?q=${lat},${lon}`;
	},
	// Date: 2026-10-29
	// Length of a Leaflet polyline in metres (sum of its segments; Leaflet's distanceTo is great-circle).
	line_length_m(layer) {
		let pts = layer.getLatLngs();
		while (pts.length && Array.isArray(pts[0])) pts = pts.flat();
		let total = 0;
		for (let i = 1; i < pts.length; i++) total += pts[i - 1].distanceTo(pts[i]);
		return total;
	},
	// Date: 2026-10-29
	// Put "<n> m" on every route line of the Route Map and a summary under the map.
	// The Geolocation control draws the map after refresh, so this retries a few times.
	show_route_distance(frm, tries = 0) {
		const ctrl = frm.fields_dict.route_map;
		if (!ctrl || !frm.doc.route_map) return;
		if (!ctrl.map || !ctrl.editableLayers) {
			if (tries < 10) setTimeout(() => ftth.show_route_distance(frm, tries + 1), 300);
			return;
		}
		let route_m = 0;
		ctrl.editableLayers.eachLayer((layer) => {
			if (!(layer instanceof L.Polyline) || layer instanceof L.Polygon) return;
			const m = ftth.line_length_m(layer);
			route_m += m;
			layer.unbindTooltip();
			layer.bindTooltip(`${Math.round(m)} m`, { permanent: true, direction: "center" });
		});
		const parts = [];
		if (route_m) parts.push(__("Route covered: {0} m", [Math.round(route_m)]));
		if (frm.doc.latitude && frm.doc.longitude && frm.doc.b_end_latitude && frm.doc.b_end_longitude) {
			const straight = L.latLng(frm.doc.latitude, frm.doc.longitude).distanceTo(
				L.latLng(frm.doc.b_end_latitude, frm.doc.b_end_longitude)
			);
			parts.push(__("A end to B end straight line: {0} m", [Math.round(straight)]));
		}
		const $desc = $(ctrl.wrapper).find(".route-distance");
		const html = parts.length ? `<b>${parts.join(" &nbsp;|&nbsp; ")}</b>` : "";
		if ($desc.length) $desc.html(html);
		else $(ctrl.wrapper).find(".help-box, .control-input-wrapper").last().after(
			`<div class="route-distance text-muted small" style="margin-top:4px">${html}</div>`
		);
	},
	directions_url(frm) {
		return (
			"https://www.google.com/maps/dir/?api=1" +
			`&origin=${frm.doc.b_end_latitude},${frm.doc.b_end_longitude}` +
			`&destination=${frm.doc.latitude},${frm.doc.longitude}&travelmode=walking`
		);
	},
};

// 2026-10-29: which line of the pasted MWO message fills which field (label normalised -> fieldname).
// Same message format as New Project's Extract & Fill.
const MESSAGE_FIELD_MAP = {
	mwono: "wo_number",
	wono: "wo_number",
	uniqueid: "unique_id",
	sitename: "end_location",
	sitelatlong: "end_lat_long",
	hp: "hp",
	giscode: "gis",
	bpoint: "b_end",
	feederlength: "planning_distance",
	nearestodfno: "nearest_odf",
	nearestodf: "nearest_odf",
	pincode: "pincode",
	rsu: "rsu",
	remarks: "remarks",
};
// Message values that go into number fields: "160 mtrs" -> 160.
const NUMBER_FIELDS = ["planning_distance", "hp"];
const SHORT_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];

// Date: 2026-10-29
// "Site Lat Long" -> "sitelatlong": lower case, letters and digits only.
function normalise_key(key) {
	return key.toLowerCase().replace(/[^a-z0-9]/g, "");
}

// Date: 2026-10-29
// Splits the pasted message into label/value pairs, one per line. Empty values and "-" are skipped.
// "→ Site Name:- Pokle Sankul" -> { sitename: "Pokle Sankul" }  (copied from New Project)
function parse_message(text) {
	const data = {};
	text.split(/\r?\n/).forEach((line) => {
		const match = line.match(/^[^A-Za-z0-9]*([^:]+?)\s*:-?\s*(.*)$/);
		if (!match) return;
		const value = match[2].replace(/["\s]+$/, "").trim();
		if (value && value !== "-") data[normalise_key(match[1])] = value;
	});
	return data;
}

// Date: 2026-10-29
// Release date in the message heading, used as the WO Received Date.
// "New MWO Released - 01-Oct-26" -> "2026-10-01"
function get_released_date(text) {
	const match = text.match(/Released\s*[-:]*\s*(\d{1,2})[-\s/]([A-Za-z]{3})[A-Za-z]*[-\s/](\d{2,4})/i);
	if (!match) return null;
	const month = SHORT_MONTHS.indexOf(match[2].toLowerCase()) + 1;
	if (!month) return null;
	const year = cint(match[3]) < 100 ? 2000 + cint(match[3]) : cint(match[3]);
	const date = new Date(year, month - 1, cint(match[1]));
	if (date.getMonth() !== month - 1) return null;
	return `${year}-${String(month).padStart(2, "0")}-${String(cint(match[1])).padStart(2, "0")}`;
}

// Date: 2026-10-29
// City from the MWO No: the part after the state ("...-Maharashtra/PUNE/Capex/..." -> "Pune").
function get_city(wo) {
	const part = ((wo || "").split("/")[1] || "").trim();
	if (!/^[A-Za-z ]{3,}$/.test(part)) return null;
	return part.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

// Date: 2026-10-29
// "Extract & Fill": parse the pasted message, fill the work order and report what was not found.
// Setting WO Number and the lat/long fields runs their own handlers below (WO ID / date, coordinates).
async function extract_and_fill(frm) {
	const text = frm.doc.wo_message || "";
	const data = parse_message(text);
	const values = {};
	const not_found = [];
	Object.keys(MESSAGE_FIELD_MAP).forEach((key) => {
		if (!data[key]) return;
		const fieldname = MESSAGE_FIELD_MAP[key];
		values[fieldname] = NUMBER_FIELDS.includes(fieldname) ? flt((data[key].match(/[\d.]+/) || [0])[0]) : data[key];
	});
	if (values.unique_id) values.unique_id = values.unique_id.toUpperCase();
	// B Point given as coordinates goes into B End Lat, Long instead of the B End name.
	if (values.b_end && ftth.parse_lat_long(values.b_end)[0] !== null && !/[a-z]{3}/i.test(values.b_end)) {
		values.b_end_lat_long = values.b_end;
		delete values.b_end;
	}
	// GIS must be an existing GIS Node.
	if (values.gis) {
		const code = values.gis.trim().toUpperCase();
		const found = await frappe.db.get_value("GIS Node", code, "name");
		if (found.message && found.message.name) values.gis = found.message.name;
		else {
			not_found.push(__("GIS {0}", [code.bold()]));
			delete values.gis;
		}
	}
	const city = get_city(values.wo_number);
	if (city && !frm.doc.city) values.city = city;
	const released = get_released_date(text);
	if (released && !frm.doc.wo_received_date) values.wo_received_date = released;

	if (!Object.keys(values).length) {
		frappe.msgprint(__("Could not find any data in the message. Please check the pasted text."));
		return;
	}
	await frm.set_value(values);
	frappe.show_alert({
		message: __("{0} fields filled from the message", [Object.keys(values).length]),
		indicator: "green",
	});
	if (not_found.length) {
		frappe.msgprint({
			title: __("Not found in master"),
			indicator: "orange",
			message: __("These were not filled because no matching record exists: {0}", [not_found.join(", ")]),
		});
	}
	// The work is ours only when Evision is the feeder partner (same check as New Project).
	if (data.feederpartner && !/e\s*vision/i.test(data.feederpartner)) {
		frappe.msgprint({
			title: __("Check Feeder Partner"),
			indicator: "red",
			message: __("Feeder Partner in this WO is {0}, not Evision. Please confirm before going ahead.", [
				frappe.utils.escape_html(data.feederpartner).bold(),
			]),
		});
	}
}

// Who acts at each Stage (same as New Project); the Save button is named after them.
const STAGE_OWNERS = {
	"Survey by Area Manager": "Area Manager",
	"B End Approval by Project Head": "Project Head",
	"Fiber Team Assignment by Area Manager": "Area Manager",
	"Fiber Work by Fiber Team": "Fiber Team",
	"Splicer Assignment by Area Manager": "Area Manager",
	"Splicing by Splicing Team": "Splicing Team",
	"Final Details by Project Head": "Project Head",
	"AT & HOTO by Project Head": "Project Head",
	"Billing by Accounts": "Accounts",
	Closed: null,
	Cancelled: null,
};
// Payment statuses that end the Billing stage (PAYMENT_DONE in logic.py).
const PAYMENT_DONE = ["Fully Received", "Cancelled/ Written Off"];

// Date: 2026-10-29
// The Stage the work order will be at once saved. Same rules as compute_stage() in logic.py.
function get_next_stage(doc) {
	if (doc.issue_type === "Cancelled") return "Cancelled";
	if (doc.rfs_date || doc.work_completed_date || doc.issue_type === "Completed") {
		if (!(doc.at_status === "Done" && doc.hoto_date)) return "AT & HOTO by Project Head";
		if (!PAYMENT_DONE.includes(doc.payment_status)) return "Billing by Accounts";
		return "Closed";
	}
	if (doc.b_end_issue && !doc.approval_date) return "B End Approval by Project Head";
	if (!doc.survey_distance) return "Survey by Area Manager";
	if (!doc.fiber_team) return "Fiber Team Assignment by Area Manager";
	if (!(doc.fiber_id || (doc.reading_a_snap && doc.reading_b_snap))) return "Fiber Work by Fiber Team";
	if (!doc.splicer) return "Splicer Assignment by Area Manager";
	if (!(doc.splicing_snaps_done || (doc.splicing_snap_a && doc.splicing_snap_b))) return "Splicing by Splicing Team";
	return "Final Details by Project Head";
}

// Date: 2026-10-29
// Names the Save button after whoever gets the work order next (copied from New Project).
// It stays "Save" while the same owner keeps working.
function set_send_button(frm) {
	const btn = frm.page.btn_primary;
	if (!btn || frm.toolbar?.current_status !== "Save") return;
	const current_owner = frm.is_new() ? "Project Head" : STAGE_OWNERS[frm.doc.stage];
	const next_stage = get_next_stage(frm.doc);
	const next_owner = STAGE_OWNERS[next_stage];
	const changes = next_stage !== frm.doc.stage;
	let label = __("Save");
	if (changes && next_stage === "Cancelled") label = __("Cancel Work Order");
	else if (changes && next_stage === "Closed") label = __("Close Work Order");
	else if (changes && frm.doc.stage === "Final Details by Project Head") label = __("Mark RFS Done");
	else if (next_owner && next_owner !== current_owner) label = __("Send to {0}", [__(next_owner)]);
	btn.html(label).attr("data-label", label);
}

frappe.ui.form.on("FTTH Work Order", {
	setup(frm) {
		// 2026-10-29: Frappe redraws the Save button on each change; rename it after that redraw.
		$(frm.wrapper).on("dirty", () => setTimeout(() => set_send_button(frm), 0));
		frm.set_query("gis", () => ({ filters: { is_active: 1 } }));
		frm.set_query("ibd_team", () => ({ filters: { is_active: 1 } }));
		frm.set_query("fiber_team", () => ({ filters: { is_active: 1 } }));
		const staff = (types) => () => ({ filters: { is_active: 1, staff_type: ["in", types] } });
		frm.set_query("splicer", staff(["Splicer", "Assistant Splicer"]));
		frm.set_query("splicer_2", staff(["Splicer", "Assistant Splicer"]));
		frm.set_query("assistant_splicer", staff(["Assistant Splicer", "Splicer"]));
		frm.set_query("rider_1", staff(["Rider"]));
		frm.set_query("rider_2", staff(["Rider"]));
		frm.set_query("end_point", () => ({ filters: frm.doc.gis ? { gis: ["in", [frm.doc.gis, ""]] } : {} }));
		frm.set_query("b_end_point", () => ({ filters: frm.doc.gis ? { gis: ["in", [frm.doc.gis, ""]] } : {} }));
		frm.set_query("kmz_route", () =>
			frm.doc.gis ? { filters: [["KMZ Route", "gis", "in", [frm.doc.gis, ""]]] } : {}
		);
	},

	refresh(frm) {
		if (frm.doc.has_warnings && frm.doc.warnings) {
			const items = frm.doc.warnings
				.split("\n")
				.map((w) => `<li>${frappe.utils.escape_html(w)}</li>`)
				.join("");
			frm.set_intro(`<b>${__("Please check")}</b><ul style="margin:4px 0 0">${items}</ul>`, "red");
		}
		if (frm.doc.latitude && frm.doc.longitude) {
			frm.add_custom_button(
				__("End Location"),
				() => window.open(ftth.maps_url(frm.doc.latitude, frm.doc.longitude)),
				__("Open in Maps")
			);
		}
		if (frm.doc.latitude && frm.doc.b_end_latitude) {
			frm.add_custom_button(
				__("Route B End → End"),
				() => window.open(ftth.directions_url(frm)),
				__("Open in Maps")
			);
		}
		ftth.show_route_distance(frm);
		set_send_button(frm);
		const go = (label, doctype, name) =>
			name && frm.add_custom_button(label, () => frappe.set_route("Form", doctype, name), __("Connected"));
		if (!frm.is_new()) {
			go(__("GIS Node"), "GIS Node", frm.doc.gis);
			go(__("Link Register"), "FTTH Link", frm.doc.ftth_link);
			go(__("KMZ Route"), "KMZ Route", frm.doc.kmz_route);
			go(__("End KMZ Pin"), "KMZ Point", frm.doc.end_point);
			go(__("B End KMZ Pin"), "KMZ Point", frm.doc.b_end_point);
			go(__("Import"), "FTTH Import", frm.doc.ftth_import);
		}
	},

	// 2026-10-29: "Extract & Fill" button under the pasted WO message.
	extract_data(frm) {
		extract_and_fill(frm);
	},

	wo_number(frm) {
		if (!frm.doc.wo_number) return;
		frappe
			.call("emp_tracking.ftth.doctype.ftth_work_order.ftth_work_order.preview_wo_number", {
				wo_number: frm.doc.wo_number,
			})
			.then(({ message: m }) => {
				if (!m) return;
				frm.set_value({
					wo_id: m.wo_id,
					wo_date: m.wo_date,
					segment: m.segment,
					building_type: m.building_type,
				});
				if (!frm.doc.wo_received_date && m.wo_date) frm.set_value("wo_received_date", m.wo_date);
				if (m.existing && m.existing !== frm.doc.name) {
					frappe.msgprint({
						title: __("Already exists"),
						indicator: "orange",
						message: __("WO {0} is already saved as {1}.", [
							m.wo_id,
							`<a href="/app/ftth-work-order/${encodeURIComponent(m.existing)}">${m.existing}</a>`,
						]),
					});
				}
			});
	},

	end_lat_long(frm) {
		const [lat, lon] = ftth.parse_lat_long(frm.doc.end_lat_long);
		frm.set_value({ latitude: lat, longitude: lon });
	},

	b_end_lat_long(frm) {
		const [lat, lon] = ftth.parse_lat_long(frm.doc.b_end_lat_long);
		frm.set_value({ b_end_latitude: lat, b_end_longitude: lon });
	},

	b_end_issue(frm) {
		frm.toggle_reqd("new_b_end", frm.doc.b_end_issue);
	},

	splicing_snap_a: (frm) => frm.trigger("auto_tick_snaps"),
	splicing_snap_b: (frm) => frm.trigger("auto_tick_snaps"),
	auto_tick_snaps(frm) {
		if (frm.doc.splicing_snap_a && frm.doc.splicing_snap_b) frm.set_value("splicing_snaps_done", 1);
	},
});
