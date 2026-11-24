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
