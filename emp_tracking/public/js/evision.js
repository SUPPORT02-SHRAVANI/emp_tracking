// ---------------------------------------------------------------------------------------------
// EVision shared UI helpers (window.evision). Created 2026-11-02.
//
// How this file works
//   Loaded on every desk page through app_include_js in hooks.py (a plain file, no bench build).
//   It only defines helpers; nothing runs until a form script calls them. Styles are in
//   public/css/evision.css.
//
//   evision.stepper(frm, opts) draws a stage tracker at the top of a form's first tab: a row of
//   steps (done = green tick, current = blue, upcoming = grey) and a header with the current
//   stage, "step N of M" and who has to act now (highlighted when that is the viewing user).
//   It uses frm.dashboard.add_section(), whose "custom" sections Frappe clears on every refresh,
//   so calling it from refresh() never leaves duplicates. Used by:
//     - FTTH Work Order (public/js/ftth_work_order.js): the work order's Stage.
//     - Complaint Information (complaint_information.js): the OHP Maintenance Workflow state.
//   opts.hero adds a header above the steps (title, meta line, badges); opts.after adds notices
//   (evision.notice_html) under them.
//
//   evision.form_style(frm) puts the class "ev-form" on the form's wrapper, which turns on the
//   card layout in evision.css (section 5): each form section a rounded card on a quiet grey
//   page, cleaner tabs and labels. Only forms that call it are restyled.
//
// Change log
//   2026-11-02  Created: stepper().
//   2026-11-02  stepper() opts.hero (summary header); form_style().
//   2026-11-26  noc_scope_filters() and noc_formatter(): shared filters and cell colours of the
//               NOC reports.
//   2026-11-26  month_bands(): light band behind every other month on day-by-day charts.
//   2026-11-26  noc_report_onload() / noc_report_after_render(): "Full screen" button and a
//               full-height table on the NOC reports.
//   2026-11-26  noc_fluid_table() (stretched "fluid" report tables) removed again: it squeezed
//               grouped (tree) tables into unreadable columns. Reports use wider columns instead.
//   2026-11-02  New look chosen by the user: header above a step card with a "Waiting on you" /
//               "Now with" status bar (replaces the "Current stage / Step N of M" head);
//               opts.after and notice_html() for warnings / actions; hero figure tiles dropped.
// ---------------------------------------------------------------------------------------------

frappe.provide("evision");

// Date: 2026-11-02
// Small inline icons (lucide "check" / "x"); inline so they do not depend on the desk icon sprite.
evision.ICON_CHECK =
	'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
evision.ICON_X =
	'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>';
// 2026-11-02: lucide "hand", "clock", "triangle-alert" and "link" for the status bar and notices
evision.ICON_HAND =
	'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 11V6a2 2 0 0 0-4 0v1M14 10V4a2 2 0 0 0-4 0v2M10 10.5V6a2 2 0 0 0-4 0v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/></svg>';
evision.ICON_CLOCK =
	'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>';
evision.ICON_WARN =
	'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4M12 17h.01"/></svg>';
evision.ICON_LINK =
	'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>';

// Date: 2026-11-02
// Draws the stage tracker on a form.
//   opts.steps    [{key, label, owner}]  in order; owner is the role (or team) that acts there
//   opts.current  key of the step the record is at (null when stopped before any step)
//   opts.state    "active" (default) | "finished" (every step done) | "stopped" (Cancelled /
//                 Rejected); opts.state_label replaces the stage name in the status bar
//   opts.owner    who acts now (defaults to the current step's owner); opts.roles are the roles
//                 that count as "you" (defaults to [owner])
//   opts.hero     optional header above the card: { title, meta: [text], badges: [{label, color}] }
//   opts.after    optional HTML placed under the card (evision.notice_html: warnings, actions)
// Layout (2026-11-02, the look the user chose): header, then a card with the step circles (done =
// dark tick, current = ringed with its owner under it, upcoming = grey number) and a status bar
// under them: "Waiting on you: <stage>" (amber) when the viewer's role acts, else "Now with ...".
// Returns the section body (jQuery) so callers can bind clicks inside opts.after.
// Does nothing on a new record or when the form has no dashboard (guarded for future Frappe).
evision.stepper = function (frm, opts) {
	if (!frm || frm.is_new() || !frm.dashboard || !frm.dashboard.add_section) return;
	const esc = frappe.utils.escape_html;
	const steps = opts.steps || [];
	const state = opts.state || "active";
	let at = steps.findIndex((s) => s.key === opts.current);
	if (state === "finished") at = steps.length;

	const items = steps
		.map((s, i) => {
			const cls = i < at ? "done" : i === at ? "current" : "";
			const mark = i < at ? evision.ICON_CHECK : i === at && state === "stopped" ? evision.ICON_X : i + 1;
			const who = i === at && state === "active" && s.owner ? `<span class="who">${esc(__(s.owner))}</span>` : "";
			return `<li class="ev-step ${cls}" title="${esc(s.title || s.label)}${s.owner ? " · " + esc(__(s.owner)) : ""}">
				<span class="mark">${mark}</span><span class="name">${esc(__(s.label))}</span>${who}</li>`;
		})
		.join("");

	const now = steps[at];
	const stage = opts.state_label || (now ? now.label : state === "finished" ? __("Completed") : "");
	const owner = opts.owner !== undefined ? opts.owner : now && now.owner;
	const roles = opts.roles || (owner ? [owner] : []);
	const mine = state === "active" && owner && roles.length && frappe.user.has_role(roles);

	// Status bar under the steps
	let bar = "";
	if (state === "stopped") {
		bar = `<div class="ev-now stopped">${evision.ICON_X}<span>${esc(__(stage))}</span></div>`;
	} else if (state === "finished") {
		bar = `<div class="ev-now finished">${evision.ICON_CHECK}<span>${esc(__(stage))}</span></div>`;
	} else if (now) {
		const with_owner = owner ? __("Now with {0}", [esc(__(owner))]) + ": " : "";
		bar = mine
			? `<div class="ev-now mine">${evision.ICON_HAND}<span>${__("Waiting on you")}: <b>${esc(__(stage))}</b></span></div>`
			: `<div class="ev-now">${evision.ICON_CLOCK}<span>${with_owner}${esc(__(stage))}</span></div>`;
	}

	const html = `<div class="ev-track">
		${opts.hero ? evision.hero_html(opts.hero) : ""}
		<div class="ev-stepper ${state}">
			<ol class="ev-steps">${items}</ol>
			${bar}
		</div>
		${opts.after || ""}
	</div>`;
	const $body = frm.dashboard.add_section(html);
	// The section is a collapsible card; the tracker draws its own frame, so drop the extra padding.
	if ($body && $body.closest) $body.closest(".form-dashboard-section").addClass("ev-stepper-section");
	return $body;
};

// Date: 2026-11-02
// A notice box under the tracker: { icon: "warn" | "link", title, text, action: {label, id} }.
// The action is a button with data-ev-action="<id>"; the caller binds its click.
evision.notice_html = function (n) {
	const esc = frappe.utils.escape_html;
	const icon = n.icon === "link" ? evision.ICON_LINK : evision.ICON_WARN;
	const title = n.title ? `<div class="t">${esc(n.title)}</div>` : "";
	const button = n.action
		? `<button class="btn btn-default btn-sm" data-ev-action="${esc(n.action.id)}">${esc(n.action.label)}</button>`
		: "";
	return `<div class="ev-notice ${esc(n.icon || "warn")}">
		<span class="ic">${icon}</span>
		<div class="tx">${title}<div class="d">${esc(n.text || "")}</div></div>
		${button}
	</div>`;
};

// Date: 2026-11-02
// Header above the tracker: title, a meta line (IDs, place, date) and coloured badges on the
// right. Values are escaped; empty ones are skipped.
evision.hero_html = function (hero) {
	const esc = frappe.utils.escape_html;
	const has = (v) => v !== null && v !== undefined && v !== "";
	const meta = (hero.meta || []).filter(has).map((m) => `<span>${esc(String(m))}</span>`).join("");
	const badges = (hero.badges || [])
		.filter((b) => b && has(b.label))
		.map((b) => `<span class="ev-badge ${esc(b.color || "gray")}">${esc(__(b.label))}</span>`)
		.join("");
	return `<div class="ev-hero">
		<div class="ev-hero-title">
			<div class="t">${esc(hero.title || "")}</div>
			${meta ? `<div class="m">${meta}</div>` : ""}
		</div>
		${badges ? `<div class="ev-hero-badges">${badges}</div>` : ""}
	</div>`;
};

// Date: 2026-11-02
// Turns on the card layout for this form (evision.css section 5). frm.wrapper is the form
// page's element (checked on Frappe 16.33); guarded so a future change only skips the styling.
evision.form_style = function (frm) {
	if (frm && frm.wrapper && frm.wrapper.classList) frm.wrapper.classList.add("ev-form");
	else if (frm && frm.wrapper && frm.wrapper.addClass) frm.wrapper.addClass("ev-form");
};

// Date: 2026-11-26
// Shared look of the five NOC reports (report/noc_*): the scope filters every report has, and a
// cell formatter that colours by meaning only. Green = In SLA, red = Out SLA, amber = pending,
// zero counts fade to "–" so the numbers that matter stand out; group rows (tree view) are bold.
evision.noc_scope_filters = function () {
	return [
		{
			fieldname: "own_fiber_only", label: __("Own fibre faults only"), fieldtype: "Check", default: 1,
			description: __("RFO Own Fiber Issue, no terminations: the NOC sheet's scope"),
		},
		{
			fieldname: "own_teams_only", label: __("Own teams only"), fieldtype: "Check", default: 1,
			description: __("Leave out vendors"),
		},
	];
};

evision.noc_formatter = function (value, row, column, data, default_formatter) {
	var html = default_formatter(value, row, column, data);
	if (!data || !column) return html;
	var f = column.fieldname;
	var raw = data[f];
	var wrap = (cls, inner) => '<div class="' + cls + '">' + (inner == null ? html : inner) + "</div>";
	var right = (text) => '<div style="text-align:right">' + text + "</div>";

	if (column.fieldtype === "Int" && raw === 0) return wrap("ev-r-zero", right("–"));
	if (f === "sla" && raw) {
		var tone = raw === "OUT" ? "bad" : raw === "IN" ? "ok" : "warn";
		return '<span class="ev-r-chip ev-r-chip-' + tone + '">' + frappe.utils.escape_html(raw) + "</span>";
	}
	// 2026-11-26: any "..._pct" SLA column (NOC Performance has day_pct / night_pct / all_pct)
	if ((f === "sla_pct" || /_pct$/.test(f)) && raw != null) html = wrap(raw >= 80 ? "ev-r-ok ev-r-strong" : "ev-r-bad ev-r-strong");
	else if (f === "in_sla" || /_in$/.test(f)) html = wrap("ev-r-ok");
	else if (f === "out_sla" || /_out$/.test(f)) html = wrap("ev-r-bad");
	else if ((f === "closing" || f === "open") && raw > 0) html = wrap("ev-r-warn ev-r-strong");
	if (data.is_group) html = wrap("ev-r-group");
	return html;
};

// Date: 2026-11-26
// Light background band behind every other month of a day-by-day Frappe chart, with the month's
// name at its top, so a range over several months reads month by month (user's request). Frappe
// Charts has no x-bands, so they are drawn into the chart's own SVG: chart.state.xAxis.positions
// are the days' x centres inside chart.drawArea, chart.height is the plot height. `dates` are the
// ISO dates of the chart's labels, in order. Does nothing for a single month. A resize redraws the
// whole SVG, so a MutationObserver puts the bands back each time.
evision.month_bands = function (chart, dates) {
	if (!chart || !dates || !dates.length) return;
	var months = dates.map((d) => String(d).slice(0, 7));
	if (new Set(months).size < 2) return;
	var NS = "http://www.w3.org/2000/svg";

	var draw = function () {
		var area = chart.drawArea;
		var st = chart.state;
		if (!area || !st || !st.xAxis || !st.xAxis.positions || area.querySelector(".ev-month-bands")) return;
		var pos = st.xAxis.positions;
		var w = st.unitWidth || 0;
		var g = document.createElementNS(NS, "g");
		g.setAttribute("class", "ev-month-bands");
		var start = 0;
		var n = 0;
		for (var i = 1; i <= months.length; i++) {
			if (i < months.length && months[i] === months[start]) continue;
			var x0 = pos[start] - w / 2;
			var x1 = pos[i - 1] + w / 2;
			if (n % 2 === 0) {
				var rect = document.createElementNS(NS, "rect");
				rect.setAttribute("class", "ev-band");
				rect.setAttribute("x", x0);
				rect.setAttribute("y", 0);
				rect.setAttribute("width", Math.max(x1 - x0, 0));
				rect.setAttribute("height", chart.height);
				g.appendChild(rect);
			}
			var label = document.createElementNS(NS, "text");
			label.setAttribute("class", "ev-band-label");
			label.setAttribute("x", x0 + 6);
			label.setAttribute("y", 12);
			label.textContent = moment(dates[start]).format(x1 - x0 > 70 ? "MMMM YYYY" : "MMM");
			g.appendChild(label);
			start = i;
			n++;
		}
		area.insertBefore(g, area.firstChild); // behind the bars and lines
	};

	draw();
	var box = chart.parent || (chart.svg && chart.svg.parentNode);
	if (box && window.MutationObserver) {
		if (box._evBands) box._evBands.disconnect(); // one observer per chart box
		box._evBands = new MutationObserver(() => draw());
		box._evBands.observe(box, { childList: true, subtree: true });
	}
};

// NOC reports: bands on the report's chart, from the ISO dates the report sends as chart.dates
evision.noc_report_month_bands = function () {
	var qr = frappe.query_report;
	if (qr && qr.chart && qr.raw_data && qr.raw_data.chart) evision.month_bands(qr.chart, qr.raw_data.chart.dates);
};

// Date: 2026-11-26
// NOC reports, "full screen" (user's request). Frappe uses one report page for every report, so
// nothing here changes the page for other reports:
//   onload: a "Full screen" button that shows the report page alone on the whole screen
//           (browser Fullscreen API; Esc or the button again leaves it).
//   after_datatable_render: this report's table fills the screen height (Frappe's default box is
//           shorter and left empty space below), and the month bands on its chart.
evision.noc_report_onload = function (report) {
	report.page.add_inner_button(__("Full screen"), () => {
		var el = report.page.wrapper[0];
		if (document.fullscreenElement) document.exitFullscreen();
		else if (el.requestFullscreen) el.requestFullscreen().catch(() => frappe.show_alert(__("Full screen is blocked in this browser")));
	});
};

evision.noc_report_after_render = function (datatable) {
	if (datatable && datatable.bodyScrollable) {
		datatable.bodyScrollable.style.height = "calc(100vh - 150px)";
	}
	// Frappe's report page replaces a chart's axisOptions with its own (query_report.js
	// get_chart_options), so the report's own ones (xIsSeries: show every n-th date label instead
	// of squeezing all into "0..") are merged back and the chart drawn once more.
	var qr = frappe.query_report;
	// own key "ev_axis": Frappe overwrites axisOptions on the very object the report sent
	var own = qr && qr.raw_data && qr.raw_data.chart && qr.raw_data.chart.ev_axis;
	if (own && qr.chart_options && !qr.chart_options._ev_axis) {
		var extra = Object.assign({}, own);
		// 2026-11-26: "integer": counts on the y axis as whole numbers (not "100.00")
		if (extra.integer) {
			delete extra.integer;
			extra.numberFormatter = (v) => String(Math.round(v));
		}
		qr.chart_options.axisOptions = Object.assign({}, qr.chart_options.axisOptions, extra);
		qr.chart_options._ev_axis = 1;
		qr.render_chart(qr.chart_options);
	}
	evision.noc_report_month_bands();
};
