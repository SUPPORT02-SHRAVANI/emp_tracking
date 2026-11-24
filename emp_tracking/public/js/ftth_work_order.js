// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt

// ---------------------------------------------------------------------------------------------
// FTTH Work Order (FTTH Tracker): OverHead project buttons, added from this app through
// doctype_js in hooks.py. Created 2026-10-31, when New Project was merged into FTTH Work Order.
//
// How this file works
//   Two buttons that New Project had and FTTH Work Order did not (ported from new_project.js):
//     1. "Send Mail to Planning": when the Area Manager ticked "B End / Distance Issue", the
//        Project Head opens an editable email draft to the Planning team with the WO, the site,
//        Planning's B End / distance and the survey result.
//     2. "Create Network Link": the server makes the Network Link (maintenance handover) by
//        itself when the HOTO Date is entered (emp_tracking/ftth_stages.py). This button is for
//        work orders that got their HOTO Date before that, or whose first try missed data.
//   Both are shown only to the Project Head (and System Manager).
//   Every user also sees a stage tracker at the top of the form (wo_stage_tracker): the work
//   order's steps from Survey to Closed, which are done, the current one and who acts now.
//
// Change log
//   2026-10-31  Created.
//   2026-11-02  Stage tracker (evision.stepper from public/js/evision.js) on every refresh.
//   2026-11-02  Summary header on the tracker (wo_hero: place, IDs, issue, key distances) and
//               the card layout for the form (evision.form_style).
//   2026-11-02  Layout the user chose: header with Stage / Status / Issue badges (no figure
//               tiles), a "Check this work order" box for FTTH Tracker's warnings and a Network
//               Link row (with "Create Network Link" for the Project Head) under the tracker.
// ---------------------------------------------------------------------------------------------

// Date: 2026-11-02
// The work order's steps, in the order ftth/logic.py compute_stage() moves through them,
// with short labels for the tracker and the role that acts at each (as in ftth_stages.py).
// "B End Approval" only applies when the Area Manager ticked B End / Distance Issue.
const WO_STEPS = [
	{ key: "Survey by Area Manager", label: "Survey", owner: "Area Manager" },
	{ key: "B End Approval by Project Head", label: "B End Approval", owner: "Project Head", b_end: true },
	{ key: "Fiber Team Assignment by Area Manager", label: "Fiber Team", owner: "Area Manager" },
	{ key: "Fiber Work by Fiber Team", label: "Fiber Work", owner: "Fiber Team" },
	{ key: "Splicer Assignment by Area Manager", label: "Splicer", owner: "Area Manager" },
	{ key: "Splicing by Splicing Team", label: "Splicing", owner: "Splicing Team" },
	{ key: "Final Details by Project Head", label: "Final Details", owner: "Project Head" },
	{ key: "AT & HOTO by Project Head", label: "AT & HOTO", owner: "Project Head" },
	{ key: "Billing by Accounts", label: "Billing", owner: "Accounts" },
	{ key: "Closed", label: "Closed" },
];

// Date: 2026-11-02
// Draws the stage tracker for the saved Stage. Cancelled shows the steps greyed out; Closed
// shows all done. Accounts is a team name, so its "you" check uses the two accounts roles.
function wo_stage_tracker(frm) {
	if (!window.evision || !frm.doc.stage) return;
	const stage = frm.doc.stage;
	const steps = WO_STEPS.filter((s) => !s.b_end || frm.doc.b_end_issue || stage === s.key).map((s) =>
		Object.assign({ title: s.key }, s)
	);
	let $body;
	if (stage === "Cancelled") {
		$body = evision.stepper(frm, {
			hero: wo_hero(frm),
			steps,
			current: null,
			state: "stopped",
			state_label: __("Cancelled"),
			owner: null,
			after: wo_notices(frm),
		});
	} else {
		if (!steps.some((s) => s.key === stage)) return;
		const now = steps.find((s) => s.key === stage);
		$body = evision.stepper(frm, {
			hero: wo_hero(frm),
			steps,
			current: stage,
			state: stage === "Closed" ? "finished" : "active",
			roles: now.owner === "Accounts" ? ["Accounts User", "Accounts Manager"] : undefined,
			after: wo_notices(frm),
		});
	}
	if ($body && $body.find) {
		$body.find('[data-ev-action="network-link"]').on("click", () => wo_create_network_link(frm));
	}
}

// Date: 2026-11-02
// Boxes under the tracker: FTTH Tracker's warnings, and the Network Link for maintenance (its
// name as a link, or "Create Network Link" for the Project Head once HOTO is done).
function wo_notices(frm) {
	const d = frm.doc;
	let html = "";
	if (d.has_warnings && d.warnings) {
		html += evision.notice_html({ icon: "warn", title: __("Check this work order"), text: d.warnings });
	}
	if (d.custom_network_link) {
		html += evision.notice_html({ icon: "link", text: __("Network Link: {0}", [d.custom_network_link]) });
	} else if (d.hoto_date && d.issue_type !== "Cancelled" && wo_is_project_head()) {
		html += evision.notice_html({
			icon: "link",
			text: __("HOTO is done but there is no Network Link for maintenance yet."),
			action: { id: "network-link", label: __("Create Network Link") },
		});
	}
	return html;
}

// Date: 2026-11-02
// Stage badge colour = who acts, as on the list: Area Manager orange, Project Head blue, Fiber
// Team yellow, Splicing purple, Accounts cyan, Closed green, Cancelled red.
function wo_stage_color(stage) {
	if (stage === "Closed") return "green";
	if (stage === "Cancelled") return "red";
	const owner = (WO_STEPS.find((s) => s.key === stage) || {}).owner;
	return (
		{ "Area Manager": "orange", "Project Head": "blue", "Fiber Team": "yellow", "Splicing Team": "purple", Accounts: "cyan" }[
			owner
		] || "gray"
	);
}

// Date: 2026-11-02
// Issue Type colours, as on the list (public/js/ftth_work_order_list.js): done green, in work
// blue, waiting on permissions / access orange, dead ends red, the rest grey.
function wo_issue_color(issue) {
	if (issue === "Completed") return "green";
	if (issue === "WIP") return "blue";
	if (["B End Not Evisions", "Wrong WO", "Cancelled"].includes(issue)) return "red";
	if (/Permission|Access|Local/.test(issue || "")) return "orange";
	return "gray";
}

// Date: 2026-11-02
// The header at the top of the form: the place, its IDs and date, and badges for the Stage
// (short name), the Status (only when it says more than the stage) and the Issue Type.
// Empty values are left out by evision.hero_html.
function wo_hero(frm) {
	const d = frm.doc;
	const step = WO_STEPS.find((s) => s.key === d.stage);
	const stage_label = step ? step.label : d.stage;
	return {
		title: d.end_location || d.name,
		meta: [
			d.name,
			d.wo_id ? `WO ${d.wo_id}` : "",
			d.area,
			d.wo_date ? frappe.datetime.str_to_user(d.wo_date) : "",
		],
		badges: [
			d.stage ? { label: stage_label, color: wo_stage_color(d.stage) } : null,
			d.status && d.status !== stage_label ? { label: d.status, color: "outline" } : null,
			d.issue_type ? { label: d.issue_type, color: wo_issue_color(d.issue_type) } : null,
		],
	};
}

// Date: 2026-10-31
// Only the Project Head mails Planning and hands a link over to maintenance (as on New Project).
function wo_is_project_head() {
	return frappe.user.has_role(["Project Head", "System Manager"]);
}

frappe.ui.form.on("FTTH Work Order", {
	// Date: 2026-10-31
	// Form opened or saved: add the buttons that apply to this work order right now.
	// 2026-11-02: also draws the stage tracker (for every user, before the Project Head check).
	refresh(frm) {
		if (window.evision) evision.form_style(frm);
		wo_stage_tracker(frm);
		if (frm.is_new() || !wo_is_project_head()) return;
		if (frm.doc.b_end_issue) {
			frm.add_custom_button(__("Send Mail to Planning"), () => wo_send_mail_to_planning(frm), __("Project"));
		}
		if (frm.doc.hoto_date && !frm.doc.custom_network_link && frm.doc.issue_type !== "Cancelled") {
			frm.add_custom_button(__("Create Network Link"), () => wo_create_network_link(frm), __("Project"));
		}
	},
});

// Date: 2026-10-31
// Asks the server to make the Network Link now, then reloads the form to show it.
function wo_create_network_link(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Please save the work order first."));
		return;
	}
	frappe
		.call({
			method: "emp_tracking.ftth_stages.create_network_link",
			args: { work_order: frm.doc.name },
			freeze: true,
		})
		.then(() => frm.reload_doc());
}

// Date: 2026-10-31 (from New Project's send_mail_to_planning, 2026-10-07)
// Opens the email composer with a ready draft; the Project Head edits it, adds recipients and sends.
// The draft is a table of the WO, the site, Planning's B End / distance, the survey and the issue.
function wo_send_mail_to_planning(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Please save the work order first."));
		return;
	}
	const doc = frm.doc;
	const esc = frappe.utils.escape_html;
	const row = (label, value) =>
		`<tr><td style="padding:4px 10px;border:1px solid #ccc;"><b>${label}</b></td>` +
		`<td style="padding:4px 10px;border:1px solid #ccc;">${esc(String(value ?? "") || "-")}</td></tr>`;
	const wo = doc.wo_number || doc.wo_id;
	const site = doc.end_location || doc.name;

	const message = `<p>Dear Planning Team,</p>
<p>During the site survey for the work order below, our Area Manager found an issue with the B End / distance. Please review and approve the new B End location.</p>
<table style="border-collapse:collapse;">
${row("WO", wo)}
${row("WO Date", doc.wo_date ? frappe.datetime.str_to_user(doc.wo_date) : "")}
${row("Unique ID", doc.unique_id)}
${row("Site", doc.end_location)}
${row("Site Lat Long", doc.end_lat_long)}
${row("GIS", doc.gis)}
${row("HP", doc.hp)}
${row("B End (Planning)", doc.b_end)}
${row("B End Lat Long (Planning)", doc.b_end_lat_long)}
${row("Planning Distance (m)", doc.planning_distance)}
${row("Survey Distance (m)", doc.survey_distance)}
${row("Issue", doc.issue_detail)}
${row("New B End Location", doc.new_b_end)}
</table>
<p>Kindly confirm the approval by reply.</p>
<p>Regards,<br>${esc(frappe.session.user_fullname)}</p>`;

	new frappe.views.CommunicationComposer({
		doc: doc,
		frm: frm,
		subject: __("B End issue: approval required for {0}", [site]) + (wo ? ` (${wo})` : ""),
		message: message,
	});
}
