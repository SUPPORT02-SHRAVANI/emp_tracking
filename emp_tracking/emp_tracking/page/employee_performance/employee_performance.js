// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// ---------------------------------------------------------------------------------------------
// Employee Performance dashboard (Desk page /app/employee-performance), created 2026-10-26.
//
// Visual-only view of staff performance, in the same card style as the NOC Dashboard:
//   "Maintenance Calls" view: KPI tiles, top-3 podium, score bars, monthly trend, In vs Out SLA
//     per person and the field / home / office time split, from Staff Monthly Performance.
//     Clicking a person opens their own month-by-month cards and charts.
//   "FTTH / Projects" view: the job-based points (RFS, fiber, home pass) of the Performance
//     Leaderboard report, drawn as podium and bars.
// All numbers come from employee_performance.py; this file only draws them.
//
// Change log
//   2026-10-26  Created.
//   2026-10-26  Employee dropdown (Maintenance Calls view): lists the people with data for the
//               chosen designation and period; picking one opens their profile.
//   2026-10-27  Monthly Trend: Calls / Points legend moved to the card's top-right corner
//               (chart's own legend hidden; it overlapped the bars).
//   2026-10-27  Complaint calls from Complaint Information: Area filter, "Calls by Area" and
//               "Who Attended Where" cards, and in a person's profile their calls by area and a
//               table of every complaint (received, assigned to team, restored, times, SLA).
//   2026-10-27  Designation sent from the dropdown's shown value if the control has none: the
//               user saw Supervisors (17 people) while "Splicer" was shown.
//   2026-10-27  Person profile: charts from the complaint rows (calls by month with SLA, average
//               time to assign / restore by month, restore-time buckets, top causes).
//   2026-10-31  "Who Attended Where": each person's area chips split into one row per role
//               (As Splicer / As 2nd Splicer / As Rider / As 2nd Rider) with that role's calls.
//   2026-10-31  Person profile: their own "Where ... Attended" card with the same per-role area
//               rows (person_complaints_html).
//   2026-10-31  "EVisions Team" rank removed from the FTTH view (it existed only on New Project,
//               which was merged into FTTH Work Order).
//   2026-11-02  EVision design layer (public/css/evision.css): colours in the page's <style> are --ev-* tokens (Frappe
//               Espresso, light + dark mode) instead of hex; lighter type weights;
//               the loading box is a skeleton.
// ---------------------------------------------------------------------------------------------

const EP_METHOD = "emp_tracking.emp_tracking.page.employee_performance.employee_performance.";
const EP_PALETTE = ["#2563eb", "#16a34a", "#ea580c", "#9333ea", "#0891b2", "#db2777", "#ca8a04", "#4f46e5"];
const EP_LEVEL_COLOURS = { Diamond: "#0891b2", Platinum: "#7c3aed", Gold: "#ca8a04", Silver: "#64748b", Bronze: "#c2410c" };

frappe.pages["employee-performance"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Employee Performance"), single_column: true });
	wrapper.ep = new EmployeePerformance(page);
};

frappe.pages["employee-performance"].on_page_show = function (wrapper) {
	if (wrapper.ep) wrapper.ep.refresh();
};

function ep_esc(v) {
	return frappe.utils.escape_html(v == null ? "" : String(v));
}

function ep_num(v, digits = 0) {
	return format_number(v || 0, null, digits);
}

// Seconds -> "3h 25m" (Duration fields store seconds)
function ep_dur(seconds) {
	seconds = Math.round(seconds || 0);
	if (!seconds) return "-";
	const h = Math.floor(seconds / 3600), m = Math.round((seconds % 3600) / 60);
	return h ? `${h}h ${m}m` : `${m}m`;
}

function ep_avatar(name, size = 34) {
	const text = String(name || "?");
	let hash = 0;
	for (const ch of text) hash = (hash * 31 + ch.charCodeAt(0)) % 997;
	const initials = text.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
	return `<span class="ep-avatar" style="width:${size}px;height:${size}px;font-size:${Math.round(size * 0.38)}px;
		background:${EP_PALETTE[hash % EP_PALETTE.length]}">${ep_esc(initials)}</span>`;
}

function ep_badges(badges) {
	const list = Array.isArray(badges) ? badges : String(badges || "").split(/\s{2,}/).filter(Boolean);
	return list.map((b) => `<span class="ep-badge">${ep_esc(b)}</span>`).join("");
}

const EP_STYLE = `
<style>
.ep-wrap { padding: 4px 0 30px; }
.ep-filters { display:flex; flex-wrap:wrap; gap:12px; align-items:flex-end; margin-bottom:14px; }
.ep-filters .frappe-control { margin-bottom:0; min-width:160px; }
.ep-tabs { display:inline-flex; background:var(--control-bg); border-radius:10px; padding:3px; margin-bottom:14px; }
.ep-tab { padding:6px 16px; border-radius:8px; cursor:pointer; font-weight:600; color:var(--text-muted); }
.ep-tab.active { background:var(--card-bg); color:var(--text-color); box-shadow:var(--shadow-sm); }
.ep-kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:14px; }
.ep-kpi { background:var(--card-bg); border:1px solid var(--border-color); border-radius:12px; padding:14px 16px;
	border-top:1px solid var(--ev-border); }
.ep-kpi .v { font-size:24px; font-weight:500; color:var(--text-color); line-height:1.2; }
.ep-kpi .l { font-size:12px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.03em; }
.ep-kpi.t-green { border-top-color:var(--ev-border); } .ep-kpi.t-orange { border-top-color:var(--ev-border); }
.ep-kpi.t-red { border-top-color:var(--ev-border); } .ep-kpi.t-purple { border-top-color:var(--ev-border); }
.ep-kpi.t-cyan { border-top-color:var(--ev-border); }
.ep-grid { display:grid; grid-template-columns:repeat(12,1fr); gap:14px; }
.ep-card { background:var(--card-bg); border:1px solid var(--border-color); border-radius:12px; padding:16px; min-width:0; }
.ep-card h4 { font-size:14px; font-weight:500; margin:0 0 12px; color:var(--text-color); }
.ep-card .sub { font-size:12px; color:var(--text-muted); font-weight:400; margin-left:6px; }
/* Legend in the card's top-right corner (used instead of the chart's own bottom legend) */
.ep-card h4.ep-head { display:flex; align-items:center; flex-wrap:wrap; gap:4px; }
.ep-legend { margin-left:auto; display:inline-flex; gap:14px; font-size:12px; font-weight:600; color:var(--text-muted); }
.ep-legend i { display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:5px; vertical-align:-1px; }
.ep-c12 { grid-column:span 12; } .ep-c8 { grid-column:span 8; } .ep-c6 { grid-column:span 6; } .ep-c4 { grid-column:span 4; }
@media (max-width: 991px) { .ep-c8, .ep-c6, .ep-c4 { grid-column:span 12; } }
.ep-avatar { display:inline-flex; align-items:center; justify-content:center; border-radius:50%; color:#fff;
	font-weight:500; flex:none; }
.ep-podium { display:flex; align-items:flex-end; justify-content:center; gap:14px; min-height:230px; }
.ep-step { flex:1; max-width:200px; text-align:center; cursor:pointer; }
.ep-step .who { font-weight:500; margin:6px 0 2px; color:var(--text-color); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ep-step .pts { font-size:13px; color:var(--text-muted); }
.ep-step .block { margin-top:8px; border-radius:10px 10px 0 0; display:flex; align-items:center; justify-content:center;
	font-size:30px; color:#fff; font-weight:600; }
.ep-step.p1 .block { height:120px; background:linear-gradient(180deg,var(--ev-warn),var(--ev-warn)); }
.ep-step.p2 .block { height:90px; background:linear-gradient(180deg,var(--ev-muted-2),#64748b); }
.ep-step.p3 .block { height:65px; background:linear-gradient(180deg,var(--ev-warn-bg),var(--ev-warn)); }
.ep-row { display:flex; align-items:center; gap:10px; padding:7px 4px; border-radius:8px; cursor:pointer; }
.ep-row:hover { background:var(--control-bg); }
.ep-row .rk { width:30px; text-align:center; font-weight:500; color:var(--text-muted); }
.ep-row .nm { width:190px; flex:none; overflow:hidden; }
.ep-row .nm b { display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--text-color); }
.ep-row .nm small { color:var(--text-muted); }
.ep-row .bar { flex:1; min-width:60px; }
.ep-track { background:var(--gray-200); border-radius:6px; height:12px; overflow:hidden; }
.ep-fill { height:12px; border-radius:6px; }
.ep-row .val { width:80px; text-align:right; font-weight:500; color:var(--text-color); }
.ep-row .bd { width:200px; flex:none; text-align:right; }
@media (max-width: 767px) { .ep-row .bd { display:none; } .ep-row .nm { width:120px; } }
.ep-badge { display:inline-block; font-size:11px; padding:1px 7px; margin:1px 2px; border-radius:10px;
	background:var(--control-bg); color:var(--text-color); white-space:nowrap; }
.ep-level { font-weight:500; }
.ep-empty { text-align:center; color:var(--text-muted); padding:50px 10px; }
.ep-hero { display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
.ep-hero .info { flex:1; min-width:200px; }
.ep-hero .info h3 { margin:0; font-size:20px; }
.ep-back { cursor:pointer; color:var(--text-muted); font-size:13px; margin-bottom:10px; display:inline-block; }
.ep-back:hover { color:var(--text-color); }
/* Complaint calls (2026-10-27): area chips and the complaint history table */
.ep-area { display:inline-block; font-size:12px; padding:2px 8px; margin:2px 3px 2px 0; border-radius:10px;
	background:var(--bg-blue); color:var(--text-on-blue); white-space:nowrap; }
.ep-area b { margin-left:4px; }
.ep-row .areas { flex:1; min-width:0; }
.ep-role-line + .ep-role-line { margin-top:4px; padding-top:4px; border-top:1px dashed var(--border-color); }
.ep-role { display:inline-block; font-size:11px; font-weight:500; color:var(--text-muted); margin-right:6px; }
.ep-table-wrap { overflow-x:auto; max-height:520px; overflow-y:auto; }
.ep-table { width:100%; border-collapse:collapse; font-size:12px; }
.ep-table th { position:sticky; top:0; background:var(--card-bg); color:var(--text-muted); font-weight:600;
	text-align:left; padding:6px 8px; border-bottom:1px solid var(--border-color); white-space:nowrap; }
.ep-table td { padding:6px 8px; border-bottom:1px solid var(--border-color); white-space:nowrap; color:var(--text-color); }
.ep-sla-in { color:var(--green-600); font-weight:500; } .ep-sla-out { color:var(--red-600); font-weight:500; }
</style>`;

class EmployeePerformance {
	constructor(page) {
		this.page = page;
		this.view = "calls";
		this.employee = null;
		this.$body = $(`<div class="ep-wrap">${EP_STYLE}
			<div class="ep-tabs">
				<div class="ep-tab active" data-view="calls">${__("Maintenance Calls")}</div>
				<div class="ep-tab" data-view="jobs">${__("FTTH / Projects")}</div>
			</div>
			<div class="ep-filters" data-slot="filters"></div>
			<div data-slot="content"></div>
		</div>`).appendTo(page.main);

		this.$body.on("click", ".ep-tab", (e) => {
			this.view = $(e.currentTarget).data("view");
			this.employee = null;
			this.$body.find(".ep-tab").removeClass("active");
			$(e.currentTarget).addClass("active");
			this.toggle_filters();
			this.refresh();
		});
		// Any person (podium, bar row) opens their own cards; only the calls view has per-person months
		this.$body.on("click", "[data-person]", (e) => {
			if (this.view !== "calls") return;
			this.employee = $(e.currentTarget).attr("data-person");
			this.refresh();
		});
		this.$body.on("click", ".ep-back", () => {
			this.employee = null;
			this.refresh();
		});

		page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");
		if (frappe.model.can_write("Leaderboard Settings")) {
			page.add_inner_button(__("Points Settings"), () => frappe.set_route("Form", "Leaderboard Settings"));
		}
		if (frappe.model.can_read("Staff Monthly Performance")) {
			page.add_inner_button(__("Monthly Data"), () => frappe.set_route("List", "Staff Monthly Performance"));
		}
		this.make_filters();
		this.charts = [];
		// First load comes from on_page_show, which Frappe also fires when the page first opens
		this.loaded = false;
	}

	slot(name) {
		return this.$body.find(`[data-slot="${name}"]`);
	}

	control(df) {
		const c = frappe.ui.form.make_control({
			parent: $('<div>').appendTo(this.slot("filters")),
			df: { ...df, change: () => { if (this.loaded) { this.employee = null; this.refresh(); } } },
			render_input: true,
		});
		c.$wrapper.addClass("ep-filter");
		return c;
	}

	make_filters() {
		this.f_designation = this.control({ fieldname: "designation", label: __("Designation"), fieldtype: "Select",
			options: ["Splicer", "Supervisor", "Rider"].map((v) => ({ value: v, label: __(v) })) });
		this.f_designation.set_value("Splicer");
		this.f_rank = this.control({ fieldname: "rank_by", label: __("Rank"), fieldtype: "Select",
			options: "Vendor\nEmployee\nFiber Pulling Team\nArea\nArea Manager\nGIS" });
		this.f_rank.set_value("Vendor");
		this.f_from = this.control({ fieldname: "from_date", label: __("From"), fieldtype: "Date" });
		this.f_to = this.control({ fieldname: "to_date", label: __("To"), fieldtype: "Date" });
		this.f_to.set_value(frappe.datetime.get_today());
		// Area narrows only the complaint-based parts (calls by area, complaint history) and keeps
		// the person being viewed, so it has its own change handler like the Employee dropdown.
		this.f_area = frappe.ui.form.make_control({
			parent: $("<div>").appendTo(this.slot("filters")),
			df: { fieldname: "area", label: __("Area"), fieldtype: "Link", options: "Area",
				change: () => { if (this.loaded) this.refresh(); } },
			render_input: true,
		});
		// Own change handler: picking a person must keep this.employee (the shared one clears it).
		// Options are filled after each load from the people on the board.
		this.f_employee = frappe.ui.form.make_control({
			parent: $("<div>").appendTo(this.slot("filters")),
			df: {
				fieldname: "employee", label: __("Employee"), fieldtype: "Select",
				options: [{ value: "", label: __("All Employees") }],
				change: () => {
					if (!this.loaded || this.syncing_employee) return;
					const value = this.f_employee.get_value() || null;
					if (value === this.employee) return;
					this.employee = value;
					this.refresh();
				},
			},
			render_input: true,
		});
		this.toggle_filters();
	}

	// Fill the Employee dropdown from the board (A-Z) and show the person being viewed.
	// 2026-10-27: also people who only appear on complaints (no monthly figures yet).
	set_employee_options(board, area_people, person) {
		const seen = new Set();
		const people = [...(board || []), ...(area_people || []), ...(person ? [{ participant: this.employee, name: person.name }] : [])]
			.filter((r) => r.participant && !seen.has(r.participant) && seen.add(r.participant))
			.map((r) => ({ value: r.participant, label: r.name }))
			.sort((a, b) => String(a.label).localeCompare(String(b.label)));
		this.syncing_employee = true;
		this.f_employee.df.options = [{ value: "", label: __("All Employees") }, ...people];
		this.f_employee.set_options();
		Promise.resolve(this.f_employee.set_value(this.employee || ""))
			.then(() => setTimeout(() => (this.syncing_employee = false), 0));
	}

	toggle_filters() {
		this.f_employee.$wrapper.parent().toggle(this.view === "calls");
		this.f_area.$wrapper.parent().toggle(this.view === "calls");
		this.f_designation.$wrapper.parent().toggle(this.view === "calls");
		this.f_rank.$wrapper.parent().toggle(this.view === "jobs");
	}

	refresh() {
		this.charts = [];
		const content = this.slot("content");
		content.html(`<div class="ep-empty ev-loading">${__("Loading...")}</div>`);
		const common = { from_date: this.f_from.get_value() || null, to_date: this.f_to.get_value() || null };
		if (this.view === "jobs") {
			// FTTH data has no RFS in recent months: default the start to 1 January, as the report does
			if (!common.from_date) common.from_date = frappe.datetime.year_start();
			frappe.call({ method: EP_METHOD + "get_jobs_dashboard", args: { ...common, rank_by: this.f_rank.get_value() } })
				.then((r) => this.render_jobs(r.message || {}));
			return;
		}
		frappe.call({
			method: EP_METHOD + "get_calls_dashboard",
			// 2026-10-27: fall back to what the dropdown shows. An empty value made the server rank
			// every designation together (Supervisors appeared under "Splicer").
			args: { ...common, designation: this.f_designation.get_value() || this.f_designation.$input.val() || "Splicer",
				employee: this.employee,
				area: this.f_area.get_value() || null },
		}).then((r) => {
			const d = r.message || {};
			// The server fills in the earliest month on record; show it in the filter without reloading
			if (!this.f_from.get_value() && d.from_date) {
				this.loaded = false;
				this.f_from.set_value(d.from_date).then(() => (this.loaded = true));
			} else {
				this.loaded = true;
			}
			this.set_employee_options(d.board, (d.area_calls || {}).people, d.person);
			d.person ? this.render_person(d) : this.render_calls(d);
		});
	}

	// ---------------- Maintenance Calls view ----------------
	render_calls(d) {
		const content = this.slot("content");
		const board = d.board || [];
		if (!board.length) {
			// Riders have no monthly figures yet, but may already have complaint calls
			content.html(`<div class="ep-card ep-empty">${__("No monthly performance data for this period.")}</div>
				<div class="ep-grid" style="margin-top:14px">${this.area_cards_html(d)}</div>`);
			this.area_chart(d.area_calls, "areas");
			return;
		}
		const k = d.kpis;
		content.html(`
			${this.kpi_html([
				[ep_num(k.people), __("People"), ""],
				[ep_num(k.calls), __("Calls Attended"), "t-green"],
				[`${k.sla_pct}%`, __("Closed In SLA"), k.sla_pct >= 70 ? "t-green" : "t-orange"],
				[ep_dur(k.avg_mttr), __("Avg MTTR"), "t-purple"],
				[ep_dur(k.avg_field_time), __("Field Time / Day"), "t-cyan"],
				[ep_num(k.leaves), __("Leaves"), "t-red"],
			])}
			<div class="ep-grid">
				<div class="ep-card ep-c6"><h4>🏆 ${__("Top Performers")}</h4>${this.podium_html(board)}</div>
				<div class="ep-card ep-c6"><h4 class="ep-head">📈 ${__("Monthly Trend")}<span class="sub">${__("calls and points")}</span>
					<span class="ep-legend"><span><i style="background:var(--ev-accent)"></i>${__("Calls")}</span>
						<span><i style="background:var(--ev-ok)"></i>${__("Points")}</span></span></h4>
					<div data-slot="trend"></div></div>
				<div class="ep-card ep-c12"><h4>📊 ${__("Leaderboard")}<span class="sub">${__("click a name for details")}</span></h4>
					${this.bars_html(board, (r) => r.points, (r) => ep_num(r.points, 1),
						(r) => `${__(r.designation || "")} · ${ep_num(r.main_calls)} ${__("calls")} · ${r.sla_pct}% SLA`)}</div>
				<div class="ep-card ep-c8"><h4>🎯 ${__("In SLA vs Out of SLA")}</h4><div data-slot="sla"></div></div>
				<div class="ep-card ep-c4"><h4>📍 ${__("Where the Day Goes")}<span class="sub">${__("avg hours / day")}</span></h4>
					<div data-slot="split"></div></div>
				<div class="ep-card ep-c6"><h4>✅ ${__("SLA % by Month")}</h4><div data-slot="slapct"></div></div>
				<div class="ep-card ep-c6"><h4>⏱️ ${__("Avg MTTR by Person")}<span class="sub">${__("hours")}</span></h4>
					<div data-slot="mttr"></div></div>
				${this.area_cards_html(d)}
			</div>`);
		this.area_chart(d.area_calls, "areas");

		const trend = d.trend || [];
		const labels = trend.map((t) => frappe.datetime.str_to_obj(t.month).toLocaleString("default", { month: "short", year: "2-digit" }));
		this.chart("trend", {
			// Legend is drawn in the card header (top right); the chart's own legend sat over the bars
			type: "axis-mixed", height: 240, colors: ["#2563eb", "#16a34a"], showLegend: 0,
			data: { labels, datasets: [
				{ name: __("Calls"), chartType: "bar", values: trend.map((t) => t.calls) },
				{ name: __("Points"), chartType: "line", values: trend.map((t) => t.score) },
			] },
			lineOptions: { regionFill: 0, dotSize: 4 },
		});
		this.chart("slapct", {
			type: "line", height: 220, colors: ["#16a34a"],
			data: { labels, datasets: [{ name: __("SLA %"), values: trend.map((t) => t.sla_pct) }] },
			lineOptions: { regionFill: 1, dotSize: 4 },
			yMarkers: [{ label: __("Target 70%"), value: 70 }],
		});
		const top = board.slice(0, 15);
		this.chart("sla", {
			type: "bar", height: 260, colors: ["#16a34a", "#dc2626"],
			barOptions: { stacked: 1, spaceRatio: 0.4 },
			data: { labels: top.map((r) => this.short(r.name)), datasets: [
				{ name: __("In SLA"), values: top.map((r) => r.in_sla) },
				{ name: __("Out of SLA"), values: top.map((r) => r.out_sla) },
			] },
		});
		const s = d.time_split || {};
		if (s.field || s.home || s.office) {
			this.chart("split", {
				type: "donut", height: 240, colors: ["#16a34a", "#ea580c", "#2563eb"],
				data: { labels: [__("Field"), __("Home"), __("Office")], datasets: [{ values: [s.field, s.home, s.office] }] },
			});
		} else {
			this.slot("split").html(`<div class="ep-empty">${__("No location data")}</div>`);
		}
		const by_mttr = board.filter((r) => r.avg_mttr).sort((a, b) => a.avg_mttr - b.avg_mttr).slice(0, 15);
		this.chart("mttr", {
			type: "bar", height: 240, colors: ["#9333ea"],
			data: { labels: by_mttr.map((r) => this.short(r.name)),
				datasets: [{ name: __("Avg MTTR (h)"), values: by_mttr.map((r) => +(r.avg_mttr / 3600).toFixed(2)) }] },
		});
	}

	// ---------------- One person ----------------
	render_person(d) {
		const p = d.person, r = p.row, content = this.slot("content");
		if (!r) {
			// No monthly figures, but their complaints (if any) are still worth showing
			content.html(`<span class="ep-back">← ${__("Back to everyone")}</span>
				<div class="ep-card ep-empty">${__("No data for this person in the period.")}</div>
				<div class="ep-grid" style="margin-top:14px">${this.person_complaints_html(d)}</div>`);
			this.area_chart(d.area_calls, "p_areas");
			this.complaint_charts(p.complaints);
			return;
		}
		const of = (d.board || []).length;
		content.html(`
			<span class="ep-back">← ${__("Back to everyone")}</span>
			<div class="ep-card" style="margin-bottom:14px"><div class="ep-hero">
				${ep_avatar(p.name, 64)}
				<div class="info"><h3>${r.medal ? r.medal + " " : ""}${ep_esc(p.name)}</h3>
					<div class="text-muted">${__(r.designation || "")} · ${__("Rank {0} of {1}", [r.rank, of])} ·
						<span class="ep-level" style="color:${EP_LEVEL_COLOURS[r.level] || "inherit"}">${__(r.level)}</span></div>
					<div style="margin-top:6px">${ep_badges(r.badges)}</div></div>
				<div style="min-width:220px">${this.level_html(r)}</div>
			</div></div>
			${this.kpi_html([
				[ep_num(r.points, 1), __("Points"), ""],
				[ep_num(r.main_calls), __("Calls"), "t-green"],
				[ep_num(r.assistant_calls), __("Assistant Calls"), "t-cyan"],
				[`${r.sla_pct}%`, __("In SLA"), r.sla_pct >= 70 ? "t-green" : "t-orange"],
				[ep_dur(r.avg_mttr), __("Avg MTTR"), "t-purple"],
				[ep_dur(r.avg_field_time), __("Field Time / Day"), "t-cyan"],
				[ep_num(r.leaves), __("Leaves"), "t-red"],
			])}
			<div class="ep-grid">
				<div class="ep-card ep-c6"><h4>📈 ${__("Points by Month")}</h4><div data-slot="p_pts"></div></div>
				<div class="ep-card ep-c6"><h4>🎯 ${__("SLA by Month")}</h4><div data-slot="p_sla"></div></div>
				<div class="ep-card ep-c6"><h4>🏃 ${__("Field Hours / Day")}</h4><div data-slot="p_field"></div></div>
				<div class="ep-card ep-c6"><h4>⏱️ ${__("MTTR (hours)")}</h4><div data-slot="p_mttr"></div></div>
				${this.person_complaints_html(d)}
			</div>`);
		this.area_chart(d.area_calls, "p_areas");
		this.complaint_charts(p.complaints);
		const m = p.months;
		const labels = m.map((x) => frappe.datetime.str_to_obj(x.month).toLocaleString("default", { month: "short", year: "2-digit" }));
		this.chart("p_pts", { type: "bar", height: 220, colors: ["#2563eb"],
			data: { labels, datasets: [{ name: __("Points"), values: m.map((x) => x.score) }] } });
		this.chart("p_sla", { type: "bar", height: 220, colors: ["#16a34a", "#dc2626"], barOptions: { stacked: 1 },
			data: { labels, datasets: [
				{ name: __("In SLA"), values: m.map((x) => x.in_sla) },
				{ name: __("Out of SLA"), values: m.map((x) => x.out_sla) }] } });
		this.chart("p_field", { type: "line", height: 220, colors: ["#0891b2"], lineOptions: { regionFill: 1, dotSize: 4 },
			data: { labels, datasets: [{ name: __("Field hours"), values: m.map((x) => x.field_hours) }] } });
		this.chart("p_mttr", { type: "line", height: 220, colors: ["#9333ea"], lineOptions: { dotSize: 4 },
			data: { labels, datasets: [{ name: __("MTTR"), values: m.map((x) => x.mttr_hours) }] } });
	}

	// ---------------- FTTH / Projects view ----------------
	render_jobs(d) {
		const content = this.slot("content"), board = d.board || [], t = d.totals || {};
		if (!board.length) {
			content.html(`<div class="ep-card ep-empty">${__("No completed FTTH / project work in this period.")}</div>`);
			return;
		}
		content.html(`
			${this.kpi_html([
				[ep_num(t.players), __("Ranked"), ""],
				[ep_num(t.rfs_done), __("RFS Done"), "t-green"],
				[ep_num(t.fiber_m), __("Fiber Laid (m)"), "t-cyan"],
				[ep_num(t.home_pass), __("Home Pass"), "t-purple"],
			])}
			<div class="ep-grid">
				<div class="ep-card ep-c6"><h4>🏆 ${__("Top Performers")}</h4>${this.podium_html(board, true)}</div>
				<div class="ep-card ep-c6"><h4>🧵 ${__("Fiber Laid (m)")}</h4><div data-slot="fiber"></div></div>
				<div class="ep-card ep-c12"><h4>📊 ${__("Leaderboard")}</h4>
					${this.bars_html(board, (r) => r.points, (r) => ep_num(r.points),
						(r) => `${ep_num(r.rfs_done)} RFS · ${ep_num(r.home_pass)} ${__("HP")} · ${r.on_time_pct || 0}% ${__("on time")}`, true)}</div>
			</div>`);
		const top = board.slice(0, 12);
		this.chart("fiber", { type: "bar", height: 240, colors: ["#0891b2"],
			data: { labels: top.map((r) => this.short(r.name)), datasets: [{ name: __("Fiber (m)"), values: top.map((r) => Math.round(r.fiber_m || 0)) }] } });
	}

	// ---------------- Complaint calls (from Complaint Information) ----------------
	// Date: 2026-10-27
	// Main view: "Calls by Area" chart plus who attended calls in which area. Hidden for users who
	// may not read Complaint Information.
	area_cards_html(d) {
		if (!d.can_see_complaints) return "";
		const a = d.area_calls || {}, people = a.people || [];
		const where = this.f_area.get_value() ? ` · ${ep_esc(this.f_area.get_value())}` : "";
		if (!people.length) {
			return `<div class="ep-card ep-c12"><h4>🗺️ ${__("Calls by Area")}<span class="sub">${__("from complaints")}${where}</span></h4>
				<div class="ep-empty">${__("No complaints with these people as Splicer / Rider in this period.")}</div></div>`;
		}
		const max = Math.max(...people.map((p) => p.calls), 1);
		const rows = people.map((p, i) => `
			<div class="ep-row" data-person="${ep_esc(p.participant)}">
				${ep_avatar(p.name, 30)}
				<div class="nm"><b title="${ep_esc(p.name)}">${ep_esc(p.name)}</b>
					<small>${ep_num(p.calls)} ${__("calls")} · ${ep_num(p.restored)} ${__("restored")} · ${ep_num(p.in_sla)} ${__("in SLA")}</small></div>
				<div class="areas">${this.role_areas_html(p)}</div>
				<div class="val" style="width:50px">${ep_num(p.calls)}</div>
			</div>`).join("");
		return `
			<div class="ep-card ep-c6"><h4>🗺️ ${__("Calls by Area")}<span class="sub">${__("from complaints")}${where}</span></h4>
				<div data-slot="areas"></div></div>
			<div class="ep-card ep-c6"><h4>👷 ${__("Who Attended Where")}<span class="sub">${__("click a name for each call")}</span></h4>
				<div style="max-height:320px;overflow-y:auto">${rows}</div></div>`;
	}

	// Date: 2026-10-31
	// A person's area chips, one row per role they had on the complaints ("As Splicer: Dhayari 120
	// Narhe 80 ...", "As 2nd Splicer: ..."). Falls back to the single combined row when the server
	// sent no roles (older reply).
	role_areas_html(p) {
		const chips = (areas) => areas.map(([area, n]) => `<span class="ep-area">${ep_esc(__(area))}<b>${n}</b></span>`).join("");
		if (!(p.roles || []).length) return chips(p.areas || []);
		return p.roles.map((r) => `<div class="ep-role-line">
			<span class="ep-role">${__("As {0}", [__(r.role)])} · ${ep_num(r.calls)}</span>${chips(r.areas)}</div>`).join("");
	}

	// Date: 2026-10-27
	// Bar chart of calls per area (top 15, most calls first) into the given slot.
	area_chart(area_calls, slot) {
		const areas = ((area_calls || {}).areas || []).slice(0, 15);
		if (!areas.length) return;
		this.chart(slot, { type: "bar", height: 240, colors: ["#0891b2"],
			axisOptions: { xIsSeries: 0, shortenYAxisNumbers: 1 },
			data: { labels: areas.map(([area]) => this.short(__(area))), datasets: [{ name: __("Calls"), values: areas.map(([, n]) => n) }] } });
	}

	// Date: 2026-10-27
	// One person: their calls per area and every complaint with when it came in, when the team
	// was assigned, when it was restored, how long each took and the SLA.
	person_complaints_html(d) {
		if (!d.can_see_complaints) return "";
		const list = (d.person && d.person.complaints) || [];
		const where = this.f_area.get_value() ? ` · ${ep_esc(this.f_area.get_value())}` : "";
		if (!list.length) {
			return `<div class="ep-card ep-c12"><h4>📋 ${__("Complaint Calls")}<span class="sub">${__("from complaints")}${where}</span></h4>
				<div class="ep-empty">${__("No complaints with this person as Splicer / Rider in this period.")}</div></div>`;
		}
		const dt = (v) => (v ? frappe.datetime.str_to_user(v) : "-");
		const sla = (v) => (v ? `<span class="${v === "In" ? "ep-sla-in" : "ep-sla-out"}">${__(v)}</span>` : "-");
		const rows = list.map((c) => `<tr>
			<td><a href="/app/complaint-information/${encodeURIComponent(c.name)}">${ep_esc(c.name)}</a></td>
			<td>${ep_esc(__(c.area))}</td>
			<td>${ep_esc(c.society_name || c.linkid || c.site || "-")}</td>
			<td>${ep_esc([c.operatorcustomer, c.complaint_type].filter(Boolean).join(" · ") || "-")}</td>
			<td>${c.people.map(([, role]) => ep_esc(__(role))).join(", ")}</td>
			<td>${dt(c.complaint_date_and_time)}</td>
			<td>${dt(c.call_assigned_on)}</td>
			<td>${dt(c.evision_closed_on)}</td>
			<td>${ep_dur(c.delay_in_assigning)}</td>
			<td>${ep_dur(c.evision_mttr)}</td>
			<td>${sla(c.evision_sla)}</td>
			<td>${ep_esc(__(c.workflow_state || "-"))}</td>
		</tr>`).join("");
		const restored = list.filter((c) => c.evision_closed_on).length;
		// 2026-10-31: the person's own "Who Attended Where" row (areas split by role), as on the main
		// view. area_calls here holds only this person's complaints, so its one row is theirs.
		const me = ((d.area_calls || {}).people || []).find((p) => p.participant === this.employee);
		const where_card = me ? `
			<div class="ep-card ep-c12"><h4>👷 ${__("Where {0} Attended", [ep_esc(d.person.name)])}<span class="sub">${__("calls per area, by role")}${where}</span></h4>
				<div class="ep-row" style="cursor:default">
					${ep_avatar(d.person.name, 30)}
					<div class="nm"><b title="${ep_esc(d.person.name)}">${ep_esc(d.person.name)}</b>
						<small>${ep_num(me.calls)} ${__("calls")} · ${ep_num(me.restored)} ${__("restored")} · ${ep_num(me.in_sla)} ${__("in SLA")}</small></div>
					<div class="areas">${this.role_areas_html(me)}</div>
					<div class="val" style="width:50px">${ep_num(me.calls)}</div>
				</div></div>` : "";
		return `
			${where_card}
			${this.complaint_visuals_html()}
			<div class="ep-card ep-c4"><h4>🗺️ ${__("Calls by Area")}<span class="sub">${__("from complaints")}${where}</span></h4>
				<div data-slot="p_areas"></div></div>
			<div class="ep-card ep-c8"><h4>📋 ${__("Complaint Calls")}<span class="sub">${ep_num(list.length)} ${__("calls")} ·
				${ep_num(restored)} ${__("restored")}${where}</span></h4>
				<div class="ep-table-wrap"><table class="ep-table">
					<thead><tr><th>${__("Complaint")}</th><th>${__("Area")}</th><th>${__("Site / Link")}</th><th>${__("Operator")}</th>
						<th>${__("Role")}</th><th>${__("Received")}</th><th>${__("Assigned to Team")}</th><th>${__("Restored")}</th>
						<th>${__("Time to Assign")}</th><th>${__("Time to Restore")}</th><th>${__("SLA")}</th><th>${__("Status")}</th></tr></thead>
					<tbody>${rows}</tbody></table></div></div>`;
	}

	// Date: 2026-10-27
	// Chart cards for one person's complaints (drawn by complaint_charts). Two-series charts get
	// their legend in the card header, top right, like Monthly Trend.
	complaint_visuals_html() {
		const legend = (items) => `<span class="ep-legend">${items.map(([colour, label]) =>
			`<span><i style="background:${colour}"></i>${label}</span>`).join("")}</span>`;
		return `
			<div class="ep-card ep-c6"><h4 class="ep-head">📅 ${__("Calls by Month")}
				${legend([["#16a34a", __("In SLA")], ["#dc2626", __("Out of SLA")], ["#94a3b8", __("Not restored")]])}</h4>
				<div data-slot="c_month"></div></div>
			<div class="ep-card ep-c6"><h4 class="ep-head">⏱️ ${__("Average Time by Month")}<span class="sub">${__("hours")}</span>
				${legend([["#ea580c", __("To Assign")], ["#2563eb", __("To Restore")]])}</h4>
				<div data-slot="c_times"></div></div>
			<div class="ep-card ep-c6"><h4>⌛ ${__("How Long Restores Took")}<span class="sub">${__("calls")}</span></h4>
				<div data-slot="c_buckets"></div></div>
			<div class="ep-card ep-c6"><h4>🔧 ${__("Top Causes")}<span class="sub">${__("RFO type")}</span></h4>
				<div data-slot="c_causes"></div></div>`;
	}

	// Date: 2026-10-27
	// Charts from the same rows as the Complaint Calls table: calls per month split by SLA,
	// average hours to assign / restore per month, restore times in buckets, and the top 8
	// causes. "Restore" = received to EVisions restored (EVisions MTTR), only for restored calls.
	complaint_charts(list) {
		if (!list || !list.length) return;
		const months = {};
		for (const c of list) {
			const key = String(c.complaint_date_and_time || "").slice(0, 7);
			if (!key) continue;
			const m = (months[key] = months[key] || { in: 0, out: 0, open: 0, assign: [], restore: [] });
			m[c.evision_sla === "In" ? "in" : c.evision_sla === "Out" ? "out" : "open"] += 1;
			if (c.call_assigned_on && c.delay_in_assigning != null) m.assign.push(c.delay_in_assigning);
			if (c.evision_closed_on && c.evision_mttr != null) m.restore.push(c.evision_mttr);
		}
		const keys = Object.keys(months).sort();
		const labels = keys.map((k) => frappe.datetime.str_to_obj(`${k}-01`).toLocaleString("default", { month: "short", year: "2-digit" }));
		const avg_hours = (a) => (a.length ? +(a.reduce((s, v) => s + v, 0) / a.length / 3600).toFixed(2) : 0);
		this.chart("c_month", { type: "bar", height: 240, colors: ["#16a34a", "#dc2626", "#94a3b8"], showLegend: 0,
			barOptions: { stacked: 1, spaceRatio: 0.4 },
			data: { labels, datasets: [
				{ name: __("In SLA"), values: keys.map((k) => months[k].in) },
				{ name: __("Out of SLA"), values: keys.map((k) => months[k].out) },
				{ name: __("Not restored"), values: keys.map((k) => months[k].open) },
			] } });
		this.chart("c_times", { type: "line", height: 240, colors: ["#ea580c", "#2563eb"], showLegend: 0,
			lineOptions: { dotSize: 4 },
			data: { labels, datasets: [
				{ name: __("To Assign (h)"), values: keys.map((k) => avg_hours(months[k].assign)) },
				{ name: __("To Restore (h)"), values: keys.map((k) => avg_hours(months[k].restore)) },
			] } });

		// Restore time buckets; the 4-hour SLA line falls between "2-4h" and "4-8h"
		const buckets = [[1, __("< 1h")], [2, __("1-2h")], [4, __("2-4h")], [8, __("4-8h")], [24, __("8-24h")], [Infinity, __("> 24h")]];
		const counts = buckets.map(() => 0);
		for (const c of list) {
			if (!c.evision_closed_on || c.evision_mttr == null) continue;
			counts[buckets.findIndex(([max]) => c.evision_mttr / 3600 < max)] += 1;
		}
		this.chart("c_buckets", { type: "bar", height: 240, colors: ["#0891b2"],
			axisOptions: { xIsSeries: 0, shortenYAxisNumbers: 1 },
			data: { labels: buckets.map(([, label]) => label), datasets: [{ name: __("Calls"), values: counts }] } });

		const causes = {};
		for (const c of list) {
			const cause = c.rfo_type || __("Not given");
			causes[cause] = (causes[cause] || 0) + 1;
		}
		const top = Object.entries(causes).sort((a, b) => b[1] - a[1]).slice(0, 8);
		// Percentage chart: cause names are long, its legend shows them in full
		this.chart("c_causes", { type: "percentage", height: 200, colors: EP_PALETTE,
			data: { labels: top.map(([cause]) => __(cause)), datasets: [{ values: top.map(([, n]) => n) }] } });
	}

	// ---------------- Shared drawing helpers ----------------
	kpi_html(tiles) {
		return `<div class="ep-kpis">${tiles.map(([v, l, cls]) =>
			`<div class="ep-kpi ${cls}"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("")}</div>`;
	}

	podium_html(board, static_rows) {
		// Classic podium order: 2nd, 1st, 3rd
		const steps = [[board[1], 2], [board[0], 1], [board[2], 3]].filter(([r]) => r);
		return `<div class="ep-podium">${steps.map(([r, pos]) => `
			<div class="ep-step p${pos}" ${static_rows ? "" : `data-person="${ep_esc(r.participant)}"`}>
				${ep_avatar(r.name, pos === 1 ? 58 : 46)}
				<div class="who" title="${ep_esc(r.name)}">${ep_esc(r.name)}</div>
				<div class="pts">${ep_num(r.points, 1)} ${__("pts")} · <span class="ep-level" style="color:${EP_LEVEL_COLOURS[r.level] || "inherit"}">${__(r.level || "")}</span></div>
				<div class="block">${r.medal || pos}</div>
			</div>`).join("")}</div>`;
	}

	bars_html(board, value, label, sub, static_rows) {
		const max = Math.max(...board.map(value), 1);
		return board.map((r, i) => {
			const pct = Math.max(2, Math.round((value(r) * 100) / max));
			const colour = EP_LEVEL_COLOURS[r.level] || EP_PALETTE[i % EP_PALETTE.length];
			return `<div class="ep-row" ${static_rows ? "" : `data-person="${ep_esc(r.participant)}"`}>
				<div class="rk">${r.medal || r.rank}</div>
				${ep_avatar(r.name, 30)}
				<div class="nm"><b title="${ep_esc(r.name)}">${ep_esc(r.name)}</b><small>${sub(r)}</small></div>
				<div class="bar"><div class="ep-track"><div class="ep-fill" style="width:${pct}%;background:${colour}"></div></div></div>
				<div class="val">${label(r)}</div>
				<div class="bd">${ep_badges(r.badges)}</div>
			</div>`;
		}).join("");
	}

	level_html(r) {
		if (!r.next_level) return `<div class="text-muted">${__("Max level reached")}</div>`;
		const pct = Math.max(0, Math.min(100, r.level_progress || 0));
		return `<div class="text-muted" style="font-size:12px;margin-bottom:4px">
				${__("{0} more points to {1}", [ep_num(r.points_to_next, 1), __(r.next_level)])}</div>
			<div class="ep-track"><div class="ep-fill" style="width:${pct}%;background:${EP_LEVEL_COLOURS[r.next_level] || "var(--blue-500)"}"></div></div>`;
	}

	chart(slot, options) {
		const el = this.slot(slot)[0];
		if (!el) return;
		this.charts.push(new frappe.Chart(el, { axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 1 }, ...options }));
	}

	short(name) {
		const s = String(name || "");
		return s.length > 14 ? s.slice(0, 13) + "…" : s;
	}
}
