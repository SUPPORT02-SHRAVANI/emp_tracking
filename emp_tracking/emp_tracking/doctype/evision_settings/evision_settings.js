// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// EVision Settings form (created 2026-11-27): the other places where the app's rules and lists
// are kept, so everything can be changed from the screen.
//
// Change log
//   2026-11-27  Created: link cards to the other settings pages.
//   2026-11-28  "Other Settings" as tabs (user: "make this into tabs"): one tab per settings page,
//               each with a live preview of what is set there and an "Open to edit" button.
//   2026-11-28  "Formulas" tab: how each number is calculated, with this page's values (render_formulas).
//   2026-11-28  Editable formulas table: the explanation shows each formula as written in it.

const EVS_PAGES = [
	{ key: "colours", label: "List Colours", route: ["Form", "Complaint List Colours"],
		about: "Colours of Status, Operator, Link Status, Link Type, Area and SLA in the complaint list." },
	{ key: "pins", label: "Map Pin Types", route: ["Form", "KMZ Map Settings"],
		about: "Pin types on the maps (ODF, Encloser / JC ...), the words that find them and their colours." },
	{ key: "areas", label: "Areas", route: ["List", "Area"],
		about: "Team areas 1-6 with their Area Manager and boundary; each locality's Team Area." },
	{ key: "teams", label: "Maintenance Teams", route: ["List", "Maintenance Team"],
		about: "Team members (splicers, riders, team leader) and the team's area." },
	{ key: "staff", label: "Field Staff", route: ["List", "Field Staff"],
		about: "Area managers and engineers with their phone numbers." },
	{ key: "shifts", label: "Shift Types", route: ["List", "Shift Type"],
		about: "Shift times and attendance thresholds (the office hours on the Office Attendance tab are kept in step)." },
	{ key: "ftth", label: "FTTH", route: ["Form", "FTTH Settings"], about: "FTTH work order defaults." },
	{ key: "whatsapp", label: "WhatsApp", route: ["Form", "WhatsApp Settings"], about: "WhatsApp messages." },
];

const EVS_DOT = { gray: "--gray-500", blue: "--blue-500", green: "--green-500", orange: "--orange-500", red: "--red-500",
	violet: "--violet-500", yellow: "--yellow-500", cyan: "--cyan-500", pink: "--pink-500", "light-blue": "--blue-300" };

// Date: 2026-11-28
// "Formulas" tab (user: "in settings add show calculation formula"): how each number on the NOC
// dashboard, reports, attendance and maps is worked out, filled with the values set on this page,
// so changing a setting shows straight away what it changes.
function render_formulas(frm) {
	const d = frm.doc;
	const v = (x, fallback) => `<b>${frappe.utils.escape_html(String(x || fallback))}</b>`;
	const sla = v(d.sla_hours && flt(d.sla_hours), 4);
	const full = flt(d.office_full_day_hours) || 9;
	const grace = d.office_grace_minutes == null ? 15 : cint(d.office_grace_minutes);
	const present = full - grace / 60;
	const hm = (h) => `${Math.floor(h)} h${Math.round((h % 1) * 60) ? " " + Math.round((h % 1) * 60) + " min" : ""}`;
	// 2026-11-28: the editable formulas (table above) as written now
	const rows = {};
	(d.formula_table || []).forEach((r) => (rows[r.formula_key] = r.formula || r.default_formula));
	const fx = (key, fallback) => `<code>${frappe.utils.escape_html(rows[key] || fallback)}</code>`;
	const groups = [
		["NOC: pending, received, closed (Performance, Pending Summary)", [
			["Scope", `Own maintenance teams only (no vendors); Reason for Outage = ${v(d.own_fiber_rfo, "Own Fiber Issue")} or not filled yet; terminations left out.`],
			["Opening pending", "SRs received before the first day and not closed before it. On every later day: the previous day's Pending."],
			["SRs received", "SRs whose received time falls in the period (or day)."],
			["Team SRs closed", "SRs whose Team SR closed time falls in the period. A finished SR with no Team closed time counts at its Company closed time; with neither it is left out."],
			["Available", "Opening pending + SRs received."],
			["Pending now", `${fx("pending_now", "max(0, opening + received - closed)")} per day and team.`],
		]],
		["SLA and MTTR", [
			["SLA In / Out", `In when ${fx("sla_in", "restore_hours <= sla_hours")} (restore_hours = Team SR closed − received, sla_hours = ${sla}); else Out. Empty while not closed.`],
			["Above MTTR (overdue)", `Open SRs received more than ${sla} hours ago.`],
			["In SLA %", `${fx("in_sla_pct", "in_sla / (in_sla + out_sla) * 100")}, closed SRs only.`],
			["MTTR (hours)", "Average of (Team SR closed − received) over the closed SRs."],
			["TAT bucket", "Days from received to Team SR closed: same day, next day, 2 days, 3+ days; not closed = Open."],
		]],
		["Unique cuts and outages", [
			["Unique cut", "SRs on one fibre cut share a Unique Cut (blank = the SR is its own cut)."],
			["Cut owner", "The team of the cut's earliest SR."],
			["Cut closed", "When every SR under it is closed, at the latest close. Cut SLA = Out if any SR is Out, else In."],
			["Major outage days", `Per team and month, the ${v(d.outage_days_per_month, 2)} days with the most new cuts.`],
		]],
		["Day and night calls", [
			["Day call", `Received from ${v(d.day_start_hour, "8:00 AM")} up to ${v(d.night_start_hour, "8:00 PM")} (IST).`],
			["Night call", `Received from ${v(d.night_start_hour, "8:00 PM")} until ${v(d.day_start_hour, "8:00 AM")} next morning.`],
		]],
		["Office attendance (mobile app)", [
			["Hours worked", "First punch-in to last punch-out of the day."],
			["Present", `Hours worked ≥ ${fx("present_from_hours", "full_day_hours - grace_minutes / 60")} (full_day_hours = ${v(full, 9)}, grace_minutes = ${v(grace, 15)}).`],
			["Half Day", "Between the two: at least the Absent-under hours, less than the Present-from hours."],
			["Absent", `Hours worked under ${fx("absent_under_hours", "full_day_hours / 2")}.`],
		]],
		["Field staff location hours", [
			["Time counted", `The time from one location ping to the next, only when the gap is at most ${v(d.max_ping_gap_minutes, 15)} minutes (longer = phone off / no signal, not counted).`],
			["Place of that time", `Where the first ping was, checked in this order: Field = within the radius of a site on a complaint they were sent on that day; Home = within the radius of their home location; Office = within the radius of a Shift Location; else Other. Radius ${v(d.location_radius_m, 200)} m unless the location has its own.`],
			["Tracked", "Field + Home + Office + Other."],
			["In field", `${fx("in_field_pct", "field_hours / tracked_hours * 100")}.`],
		]],
		["Areas and managers", [
			["Node's team area", "Its own KMZ pin inside an area boundary; else the area most of its Network Links lie in; else the Team N most of its FTTH Master Data rows name."],
			["Link's area", "The area boundary its latitude / longitude lies in; else its node's area."],
			["Complaint's area manager", "The manager of the node's team area; with no node, of the locality's Team Area (set on each Area)."],
		]],
	];
	frm.get_field("formulas").$wrapper.html(`<style>
			.evs-f h5 { margin:18px 0 6px; font-size:var(--text-md); font-weight:600; color:var(--text-color); }
			.evs-f h5:first-child { margin-top:0; }
			.evs-f table { width:100%; border-collapse:collapse; font-size:var(--text-sm); }
			.evs-f td { padding:7px 8px; border-bottom:1px solid var(--border-color); vertical-align:top; }
			.evs-f td:first-child { width:190px; color:var(--text-muted); white-space:nowrap; }
		</style>
		<div class="evs-f">
			<p class="text-muted">${__("How each number is worked out, with the values set on the other tabs. The formulas in code style come from the table above. Save after changing a value to see it here.")}</p>
			${groups.map(([title, rows]) => `<h5>${__(title)}</h5><table>${rows.map(([k, text]) =>
				`<tr><td>${__(k)}</td><td>${text}</td></tr>`).join("")}</table>`).join("")}
		</div>`);
}

frappe.ui.form.on("EVision Settings", {
	refresh(frm) {
		render_formulas(frm);
		// 2026-11-28: the formula list is fixed (one row per number); only the formula text is edited
		const grid = frm.get_field("formula_table").grid;
		grid.cannot_add_rows = true;
		grid.wrapper.find(".grid-add-row, .grid-add-multiple-rows").hide();
		const $w = frm.get_field("more").$wrapper;
		const tabs = EVS_PAGES.map((p, i) =>
			`<button class="evs-tab ${i ? "" : "active"}" data-key="${p.key}">${__(p.label)}</button>`).join("");
		$w.html(`<style>
				.evs-tabs { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:14px; }
				.evs-tab { border:1px solid var(--border-color); background:var(--fg-color); color:var(--text-muted);
					border-radius:999px; padding:5px 13px; font-size:var(--text-sm); }
				.evs-tab.active { background:var(--text-color); color:var(--fg-color); border-color:var(--text-color); }
				.evs-pane-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:10px; }
				.evs-pane-head p { margin:0; color:var(--text-muted); }
				.evs-table { width:100%; font-size:var(--text-sm); border-collapse:collapse; }
				.evs-table th { color:var(--text-muted); font-weight:500; text-align:left; padding:6px 8px; border-bottom:1px solid var(--border-color); }
				.evs-table td { padding:6px 8px; border-bottom:1px solid var(--border-color); }
				.evs-dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px; vertical-align:0; }
				.evs-muted { color:var(--text-muted); }
			</style>
			<div class="evs-tabs">${tabs}</div>
			<div class="evs-pane"></div>`);
		const show = (key) => {
			$w.find(".evs-tab").removeClass("active").filter(`[data-key="${key}"]`).addClass("active");
			render_pane($w.find(".evs-pane"), EVS_PAGES.find((p) => p.key === key));
		};
		$w.find(".evs-tab").on("click", (e) => show($(e.currentTarget).attr("data-key")));
		show(EVS_PAGES[0].key);
	},
});

// Date: 2026-11-28
// One tab: what the page is for, an "Open to edit" button and a preview of what is set there.
async function render_pane($pane, page) {
	const esc = frappe.utils.escape_html;
	$pane.html(`<div class="evs-pane-head"><p>${__(page.about)}</p>
		<button class="btn btn-sm btn-default evs-open">${__("Open to edit")}</button></div>
		<div class="evs-body evs-muted">${__("Loading...")}</div>`);
	$pane.find(".evs-open").on("click", () => frappe.set_route(...page.route));
	const table = (head, rows) => rows.length
		? `<table class="evs-table"><thead><tr>${head.map((h) => `<th>${__(h)}</th>`).join("")}</tr></thead>
			<tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${c ?? ""}</td>`).join("")}</tr>`).join("")}</tbody></table>`
		: `<div class="evs-muted">${__("Nothing set yet.")}</div>`;
	const dot = (colour) => `<span class="evs-dot" style="background:${colour && colour.startsWith("#") ? colour : `var(${EVS_DOT[colour] || "--gray-500"})`}"></span>`;
	let html = "";
	try {
		if (page.key === "colours") {
			const c = await frappe.xcall("emp_tracking.emp_tracking.doctype.complaint_list_colours.complaint_list_colours.get_colours");
			html = table(["Column", "Values"], Object.entries(c || {}).map(([col, vals]) => [esc(__(col)),
				Object.entries(vals).map(([v, t]) => `<span style="margin-right:12px;white-space:nowrap">${dot(t)}${esc(v)}</span>`).join("")]));
		} else if (page.key === "pins") {
			const doc = await frappe.db.get_doc("KMZ Map Settings");
			html = table(["Pin type", "Words in the name", "Shown at start"], (doc.pin_types || []).map((r) =>
				[dot(r.colour) + esc(r.label), esc(r.keywords || r.match_type || ""), r.show_by_default ? __("Yes") : __("No")]));
		} else if (page.key === "areas") {
			const rows = await frappe.db.get_list("Area", { filters: { is_team_area: 1 },
				fields: ["name", "field_manager", "field_manager_no"], order_by: "name asc", limit: 50 });
			const unset = await frappe.db.count("Area", { filters: { is_team_area: 0, team_area: ["is", "not set"] } });
			html = table(["Team area", "Area Manager", "Phone"], rows.map((r) => [esc(r.name), esc(r.field_manager || "–"), esc(r.field_manager_no || "–")]))
				+ (unset ? `<p class="evs-muted" style="margin-top:8px">${__("{0} localities have no Team Area yet.", [unset])}</p>` : "");
		} else if (page.key === "teams") {
			const rows = await frappe.db.get_list("Maintenance Team", { fields: ["name", "team_type", "area", "manager_name", "status"],
				order_by: "name asc", limit: 50 });
			html = table(["Team", "Type", "Area", "Manager", "Status"], rows.map((r) =>
				[esc(r.name), esc(r.team_type || ""), esc(r.area || "–"), esc(r.manager_name || "–"), esc(r.status || "")]));
		} else if (page.key === "staff") {
			const rows = await frappe.db.get_list("Field Staff", { fields: ["name", "staff_type", "contact_no", "is_active"],
				filters: { is_active: 1 }, order_by: "staff_type asc, name asc", limit: 100 });
			html = table(["Name", "Type", "Phone"], rows.map((r) => [esc(r.name), esc(r.staff_type || ""), esc(r.contact_no || "–")]));
		} else if (page.key === "shifts") {
			const rows = await frappe.db.get_list("Shift Type", { fields: ["name", "start_time", "end_time",
				"working_hours_threshold_for_half_day", "working_hours_threshold_for_absent"], limit: 50 });
			html = table(["Shift", "Start", "End", "Present from (h)", "Absent under (h)"], rows.map((r) => [esc(r.name),
				esc(fmt_time(r.start_time)), esc(fmt_time(r.end_time)),
				r.working_hours_threshold_for_half_day || "–", r.working_hours_threshold_for_absent || "–"]));
		} else {
			html = `<div class="evs-muted">${__("Open the page to see and change these settings.")}</div>`;
		}
	} catch (e) {
		html = `<div class="evs-muted">${__("Could not load a preview. Open the page to see it.")}</div>`;
	}
	$pane.find(".evs-body").removeClass("evs-muted").html(html);
}

// "18:30:00" -> "6:30 PM" (12-hour, as used in India)
function fmt_time(value) {
	if (!value) return "–";
	const [h, m] = String(value).split(":").map((x) => parseInt(x, 10) || 0);
	return `${(h % 12) || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
}
