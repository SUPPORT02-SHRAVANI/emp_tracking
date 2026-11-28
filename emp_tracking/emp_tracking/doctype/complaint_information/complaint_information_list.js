// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt

// ---------------------------------------------------------------------------------------------
// Complaint Information: list view. Created 2026-11-27 (user's request: "give option to add colors
// to these options, they all look grey" and "area name like Area 1, colours per area").
//
// How this file works
//   Colours come from the Complaint List Colours page (column, value, colour); a value not listed
//   stays grey. Operator, Link Status, Link Type and EVisions SLA are drawn as coloured badges; the
//   Area column shows the complaint's EVision team area (Area 1-6, field team_area) in its colour,
//   with the locality in the tooltip; the Status pill (workflow state) takes its colour too.
//   "Colours" in the list menu opens the page.
//
// Change log
//   2026-11-27  Created.
//   2026-11-27  Calmer look (user: "can we make this look better?"): pills only for Status and
//               Link Status (sentence case, no more cut-off "NEED TO ASSI..."); Operator, Link
//               Type and Area as a coloured dot with text; SLA "In" a small green tick, "Out" a red pill.
//   2026-11-28  Fail-safe (main site showed an empty list): each column falls back to its plain
//               value if drawing it fails (clc_safe), plain pills without frappe.ui.badge, and the
//               status colour / colours loading never stop the list; errors go to the console.
// ---------------------------------------------------------------------------------------------

frappe.provide("emp_tracking");

// badge theme -> list status indicator colour (the indicator has no "violet")
const CLC_INDICATOR = { violet: "purple" };

// 2026-11-27 (user: "can we make this look better?"): only the two state columns (Status, Link
// Status) are pills; Operator, Link Type and Area are a coloured dot with plain text, and SLA
// only stands out when it is Out, so the eye goes to what needs action.
const CLC_DOT = {
	gray: "var(--gray-500)", blue: "var(--blue-500)", green: "var(--green-500)", orange: "var(--orange-500)",
	red: "var(--red-500)", violet: "var(--violet-500)", yellow: "var(--yellow-500)", cyan: "var(--cyan-500)",
	pink: "var(--pink-500)", "light-blue": "var(--blue-300, #5cb3fb)",
};
if (!document.getElementById("clc-style")) {
	$(`<style id="clc-style">
		.clc-dot { display:inline-flex; align-items:center; gap:7px; max-width:100%; color:var(--text-color); }
		.clc-dot .d { flex:none; width:8px; height:8px; border-radius:50%; }
		.clc-dot .d.hollow { background:transparent !important; border:1.5px solid var(--gray-400, #c0c0c0); }
		.clc-dot.muted { color:var(--text-muted); }
		.clc-sla-in { display:inline-flex; align-items:center; gap:4px; color:var(--green-600, #2f855a); font-size:var(--text-sm); }
	</style>`).appendTo("head");
}

// plain text with a coloured dot, clickable to filter like Frappe's own columns
function clc_dot(fieldname, value, label, theme, title, muted) {
	if (!value) return "";
	const esc = frappe.utils.escape_html;
	const dot = theme ? `<span class="d" style="background:${CLC_DOT[theme] || CLC_DOT.gray}"></span>` : `<span class="d hollow"></span>`;
	return `<a class="filterable ellipsis clc-dot ${muted ? "muted" : ""}" data-filter="${esc(fieldname)},=,${esc(value)}"
		title="${esc(title || value)}">${dot}<span class="ellipsis">${esc(label || __(value))}</span></a>`;
}

// "NEED TO ASSIGN" -> "Need to assign" (the stored value, used by the filter, stays the same)
function clc_sentence(text) {
	const t = (text || "").toLowerCase();
	return t.charAt(0).toUpperCase() + t.slice(1);
}

// a coloured, clickable (filters the list) badge like Frappe's own Select badges
function clc_badge(fieldname, value, label, theme, title) {
	if (!value) return "";
	// 2026-11-28: Frappe versions without frappe.ui.badge get a plain indicator pill
	if (!(frappe.ui && frappe.ui.badge && frappe.ui.badge.html)) {
		const esc = frappe.utils.escape_html;
		return `<span class="indicator-pill ${CLC_INDICATOR[theme] || theme || "gray"} filterable ellipsis"
			data-filter="${esc(fieldname)},=,${esc(value)}" title="${esc(title || value)}">${esc(label || __(value))}</span>`;
	}
	return frappe.ui.badge.html({
		label: label || __(value),
		theme: theme || "gray",
		title: title || "",
		css_class: "filterable ellipsis",
		attrs: { "data-filter": `${fieldname},=,${value}` },
	});
}

// 2026-11-28 (main site showed an empty complaint list): a formatter that fails shows the plain
// value instead of breaking the whole list, and says why in the browser console
function clc_safe(fieldname, fn) {
	return function (value, df, doc) {
		try {
			const html = fn(value, df, doc);
			return html == null ? frappe.utils.escape_html(value == null ? "" : String(value)) : html;
		} catch (e) {
			console.error(`Complaint list: column ${fieldname} could not be drawn`, e);
			return frappe.utils.escape_html(value == null ? "" : String(value));
		}
	};
}

function clc_colour(column, value) {
	return ((emp_tracking.complaint_colours || {})[column] || {})[value];
}

frappe.listview_settings["Complaint Information"] = {
	add_fields: ["team_area", "area", "workflow_state"],

	onload(listview) {
		try {
			frappe.xcall("emp_tracking.emp_tracking.doctype.complaint_list_colours.complaint_list_colours.get_colours")
				.then((c) => {
					emp_tracking.complaint_colours = c || {};
					listview.refresh();
				})
				.catch((e) => console.error("Complaint list: colours could not be loaded", e));
			if (frappe.user.has_role(["System Manager", "NOC Head"])) {
				listview.page.add_menu_item(__("Colours"), () => frappe.set_route("Form", "Complaint List Colours"));
			}
		} catch (e) {
			console.error("Complaint list: onload failed", e);
		}
	},

	formatters: {
		link_status: clc_safe("link_status", (value) => clc_badge("link_status", value, clc_sentence(value), clc_colour("Link Status", value), value)),
		operatorcustomer: clc_safe("operatorcustomer", (value) => clc_dot("operatorcustomer", value, null, clc_colour("Operator", value))),
		complaint_type: clc_safe("complaint_type", (value) => clc_dot("complaint_type", value, null, clc_colour("Link Type", value))),
		// Area 1-6 with its colour; the locality (e.g. Baner) in the tooltip. A locality with no
		// team area yet is grey text with a hollow dot.
		area: clc_safe("area", (value, df, doc) => {
			const team = doc && doc.team_area;
			if (!team) return clc_dot("area", value, null, null, __("{0}: no team area set yet", [value]), true);
			return clc_dot("team_area", team, team, clc_colour("Area", team), value && value !== team ? `${team} · ${value}` : team);
		}),
		// Out is what needs attention: a pill; In is a small tick
		evision_sla: clc_safe("evision_sla", (value) => {
			if (value === "In") {
				return `<a class="filterable clc-sla-in" data-filter="evision_sla,=,In" title="${__("Within SLA")}">✓ ${__("In")}</a>`;
			}
			return clc_badge("evision_sla", value, null, clc_colour("EVisions SLA", value));
		}),
	},
};

// Status pill = workflow state; Frappe colours it from the Workflow State's style, so the colour
// chosen on the Colours page is put in front for this doctype only
if (!frappe.__clc_indicator_wrapped) {
	frappe.__clc_indicator_wrapped = true;
	const original = frappe.get_indicator;
	frappe.get_indicator = function (doc, doctype, show_workflow_state) {
		const out = original.apply(this, arguments);
		try {
			if (doctype === "Complaint Information" && doc && doc.workflow_state && Array.isArray(out)) {
				const theme = clc_colour("Status", doc.workflow_state);
				if (theme) out[1] = CLC_INDICATOR[theme] || theme;
			}
		} catch (e) {
			console.error("Complaint list: status colour failed", e); // Frappe's own colour stays
		}
		return out;
	};
}
