// ---------------------------------------------------------------------------------------------
// FTTH Work Order list view: EVision look. Created 2026-11-02.
//
// How this file works
//   Added through doctype_list_js in hooks.py. Frappe runs it after FTTH Tracker's own
//   ftth_work_order_list.js, so it extends frappe.listview_settings["FTTH Work Order"] (keeps
//   its status indicator, "Only with warnings" button and fields) instead of replacing it.
//     1. Title column: plain text. Frappe 16 shows the title as text, so FTTH Tracker's warning
//        badge HTML appeared as "<span class=...>" in the name. The warning "!" is moved to
//        the Stage column.
//     2. Stage column: short name ("AT & HOTO" instead of "AT & HOTO by Project Head"), the full
//        name on hover, coloured by who acts; still a click-to-filter pill.
//     3. Issue Type column: coloured by meaning (done / working / waiting / blocked).
//     4. Final Distance column: "110 m"; empty or 0 shows a muted dash.
//   Styles are in public/css/evision.css (.ev-pill, .ev-wo-*).
//
// Change log
//   2026-11-02  Created.
//   2026-11-02  Stage pipeline strip above the list removed (user's request); the coloured
//               Stage / Issue pills stay.
// ---------------------------------------------------------------------------------------------

(function () {
	const DT = "FTTH Work Order";
	const esc = frappe.utils.escape_html;

	// Date: 2026-11-02
	// Stages in process order (ftth/logic.py STAGES): short label and the colour of who
	// acts. Area Manager orange, Project Head blue, Fiber Team yellow, Splicing purple,
	// Accounts cyan, Closed green, Cancelled red.
	const STAGES = [
		["Survey by Area Manager", "Survey", "orange"],
		["B End Approval by Project Head", "B End Approval", "blue"],
		["Fiber Team Assignment by Area Manager", "Fiber Team", "orange"],
		["Fiber Work by Fiber Team", "Fiber Work", "yellow"],
		["Splicer Assignment by Area Manager", "Splicer", "orange"],
		["Splicing by Splicing Team", "Splicing", "purple"],
		["Final Details by Project Head", "Final Details", "blue"],
		["AT & HOTO by Project Head", "AT & HOTO", "blue"],
		["Billing by Accounts", "Billing", "cyan"],
		["Closed", "Closed", "green"],
		["Cancelled", "Cancelled", "red"],
	];
	const STAGE = {};
	STAGES.forEach(([key, label, color]) => (STAGE[key] = { label, color }));

	// Date: 2026-11-02
	// Issue Type -> colour: done green, working blue, waiting on someone else yellow, site /
	// permission problems orange, dead ends red; anything else gray.
	const ISSUE_COLOR = {
		Completed: "green",
		WIP: "blue",
		"Mail Approval Required": "yellow",
		"OLT Pending": "yellow",
		"Site Location Not Received": "yellow",
		"Details Not Received": "yellow",
		"Permission Issue": "orange",
		"Permission Issue A End": "orange",
		"Permission Issue B End": "orange",
		"Access Issue": "orange",
		"Local Issue": "orange",
		"B End Not Evisions": "red",
		"Wrong WO": "red",
		Cancelled: "red",
	};

	// Date: 2026-11-02
	// A click-to-filter pill in Frappe's own markup (the list's click handler reads data-filter).
	function pill(field, value, label, color, title, extra) {
		return `<span class="filterable indicator-pill ev-pill ${color} ellipsis" data-filter="${field},=,${esc(value)}"
			title="${esc(title || label)}"><span class="ellipsis">${esc(label)}</span>${extra || ""}</span>`;
	}

	const s = (frappe.listview_settings[DT] = frappe.listview_settings[DT] || {});
	s.add_fields = [...new Set([...(s.add_fields || []), "has_warnings", "stage", "issue_type"])];

	s.formatters = Object.assign({}, s.formatters, {
		// Date: 2026-11-02
		// Title column: text only (Frappe 16 escapes it), so no badge HTML here.
		end_location(value) {
			return value || "";
		},
		// Date: 2026-11-02
		// Stage pill: short name, owner colour, red "!" when the work order has warnings.
		stage(value, df, doc) {
			if (!value) return "";
			const st = STAGE[value] || { label: value, color: "gray" };
			const warn = doc.has_warnings ? `<span class="ev-wo-warn" title="${__("Has warnings")}">!</span>` : "";
			return pill("stage", value, __(st.label), st.color, __(value), warn);
		},
		// Date: 2026-11-02
		issue_type(value) {
			if (!value) return "";
			return pill("issue_type", value, __(value), ISSUE_COLOR[value] || "gray");
		},
		// Date: 2026-11-02
		// Metres with a unit; nothing recorded yet shows a muted dash instead of "0".
		eff_final_distance(value) {
			const n = flt(value);
			if (!n) return `<span class="ev-wo-muted">—</span>`;
			return `<span class="ev-wo-num">${format_number(n, null, 0)} <span class="ev-wo-muted">m</span></span>`;
		},
	});
})();
