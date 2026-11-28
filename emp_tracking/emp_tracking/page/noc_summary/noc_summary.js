// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt

// ---------------------------------------------------------------------------------------------
// NOC Summary (Desk page /app/noc-summary). Created 2026-11-28 (user: "put all these dashboards
// in one, with tabs").
//
// How this file works
//   One tab per NOC summary report. Each tab runs that report through Frappe's own report runner
//   (frappe.desk.query_report.run, so the numbers are exactly the report's) with the filters at
//   the top - From, To, Team, own fibre faults only, own teams only - and shows its dashboard:
//   the summary tiles and the chart. "Open full report" opens the report with the same filters,
//   for its table. A tab is loaded when first opened and again after the filters change; the
//   last open tab is remembered in this browser.
// ---------------------------------------------------------------------------------------------

const NS_TABS = [
	["NOC Pending Summary", __("Pending")],
	["NOC Cut Team Summary", __("Cut Team")],
	["NOC Unique Cut Summary", __("Unique Cut")],
	["NOC Unique Cut Master", __("Cut Master")],
	["NOC Major Outage Closure", __("Major Outage")],
	["NOC SLA TAT Summary", __("SLA / TAT")],
	["NOC Performance", __("Performance")],
	["NOC Team Availability", __("Team Availability")],
	["Field Staff Location Hours", __("Field Staff Hours")],
];
const NS_TAB_KEY = "noc_summary_tab";
const NS_STYLE = `<style>
	.ns-tabs { display:flex; flex-wrap:wrap; gap:4px; border-bottom:1px solid var(--border-color); margin-bottom:14px; }
	.ns-tabs button { border:0; background:none; padding:8px 12px; color:var(--text-muted); border-bottom:2px solid transparent; }
	.ns-tabs button.on { color:var(--text-color); border-bottom-color:var(--text-color); font-weight:600; }
	.ns-filters { display:flex; flex-wrap:wrap; gap:12px; align-items:flex-end; margin-bottom:12px; }
	.ns-filters .frappe-control { margin:0; min-width:150px; }
	.ns-head { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:12px; }
	.ns-head h4 { margin:0; font-size:var(--text-lg); }
	.ns-tiles { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:12px; margin-bottom:16px; }
	.ns-tile { border:1px solid var(--border-color); border-radius:12px; padding:14px 16px; background:var(--card-bg, var(--fg-color)); min-width:0; }
	.ns-tile .l { font-size:var(--text-sm); color:var(--text-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
	.ns-tile .v { margin-top:6px; font-size:22px; font-weight:600; line-height:1.2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
	.ns-tile .v.blue { color:var(--blue-600, #2563eb); } .ns-tile .v.green { color:var(--green-600, #16a34a); }
	.ns-tile .v.red { color:var(--red-600, #dc2626); } .ns-tile .v.orange { color:var(--orange-600, #ea580c); }
	.ns-chart { border:1px solid var(--border-color); border-radius:12px; padding:12px 8px 4px; background:var(--card-bg, var(--fg-color)); }
	.ns-empty { border:1px dashed var(--border-color); border-radius:12px; padding:18px; text-align:center; color:var(--text-muted); }
</style>`;

frappe.pages["noc-summary"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("NOC Summary"), single_column: true });
	wrapper.ns = new NocSummary(page);
};

class NocSummary {
	constructor(page) {
		this.page = page;
		this.cache = {};
		$(NS_STYLE + `<div class="ns-filters"></div>
			<div class="ns-tabs">${NS_TABS.map(([r, label]) => `<button data-r="${frappe.utils.escape_html(r)}">${label}</button>`).join("")}</div>
			<div class="ns-head"><h4></h4><button class="btn btn-sm btn-default ns-open">${__("Open full report")}</button></div>
			<div class="ns-body"></div>`).appendTo(page.main);
		this.$ = (s) => $(page.main).find(s);
		const $f = this.$(".ns-filters");
		const control = (df) => {
			const c = frappe.ui.form.make_control({ parent: $f, df: Object.assign({}, df, { change: () => this.filters_changed() }), render_input: true });
			c.refresh();
			return c;
		};
		this.f = {
			from_date: control({ fieldname: "from_date", fieldtype: "Date", label: __("From") }),
			to_date: control({ fieldname: "to_date", fieldtype: "Date", label: __("To") }),
			team: control({ fieldname: "team", fieldtype: "Link", options: "Maintenance Team", label: __("Team") }),
			own_fiber_only: control({ fieldname: "own_fiber_only", fieldtype: "Check", label: __("Own fibre faults only") }),
			own_teams_only: control({ fieldname: "own_teams_only", fieldtype: "Check", label: __("Own teams only") }),
		};
		this.loading = true;
		this.f.from_date.set_value(frappe.datetime.month_start());
		this.f.to_date.set_value(frappe.datetime.get_today());
		this.f.own_fiber_only.set_value(1);
		this.f.own_teams_only.set_value(1);
		this.loading = false;
		this.$(".ns-tabs button").on("click", (e) => this.show($(e.currentTarget).attr("data-r")));
		this.$(".ns-open").on("click", () => {
			frappe.route_options = this.values();
			frappe.set_route("query-report", this.report);
		});
		page.set_primary_action(__("Refresh"), () => { this.cache = {}; this.show(this.report); }, "refresh");
		let saved = null;
		try { saved = localStorage.getItem(NS_TAB_KEY); } catch (e) { /* storage blocked */ }
		setTimeout(() => this.show(NS_TABS.some(([r]) => r === saved) ? saved : NS_TABS[0][0]), 300);
	}

	values() {
		const v = {};
		Object.entries(this.f).forEach(([k, c]) => {
			const x = c.get_value();
			if (x !== "" && x != null) v[k] = x;
		});
		return v;
	}

	filters_changed() {
		if (this.loading) return;
		this.cache = {};
		clearTimeout(this.t);
		this.t = setTimeout(() => this.report && this.show(this.report), 300);
	}

	async show(report) {
		this.report = report;
		try { localStorage.setItem(NS_TAB_KEY, report); } catch (e) { /* not remembered */ }
		this.$(".ns-tabs button").removeClass("on").filter((i, b) => $(b).attr("data-r") === report).addClass("on");
		this.$(".ns-head h4").text(NS_TABS.find(([r]) => r === report)[1]);
		const $b = this.$(".ns-body").html(`<div class="ns-empty">${__("Loading...")}</div>`);
		let r = this.cache[report];
		if (!r) {
			try {
				r = (await frappe.call({ method: "frappe.desk.query_report.run", args: { report_name: report, filters: this.values() } })).message || {};
			} catch (e) {
				$b.html(`<div class="ns-empty">${__("This report could not be run with these filters.")}</div>`);
				return;
			}
			this.cache[report] = r;
		}
		if (this.report !== report) return; // another tab was opened meanwhile
		this.render($b, r);
	}

	render($b, r) {
		const esc = frappe.utils.escape_html;
		const tiles = (r.report_summary || []).map((s) => {
			const colour = (s.indicator || "").toLowerCase();
			const value = s.datatype === "Percent" && s.value !== "–" ? `${s.value}%` : s.value;
			return `<div class="ns-tile"><div class="l" title="${esc(s.label)}">${esc(s.label)}</div>
				<div class="v ${esc(colour)}">${esc(value == null ? "–" : String(value))}</div></div>`;
		}).join("");
		const message = r.message && !tiles ? `<div class="ns-empty">${r.message}</div>` : "";
		$b.html(`${tiles ? `<div class="ns-tiles">${tiles}</div>` : ""}${message}
			${r.chart ? `<div class="ns-chart"><div class="ns-chart-el"></div></div>` : ""}
			${!tiles && !r.chart && !message ? `<div class="ns-empty">${__("Nothing to show for these filters.")}</div>` : ""}`);
		if (r.chart) {
			const opts = Object.assign({}, r.chart, { height: r.chart.height || 240, truncateLegends: 1 });
			// "ev_axis" (the reports' own key): whole numbers on the y axis, every n-th date label
			if (r.chart.ev_axis) {
				const extra = Object.assign({}, r.chart.ev_axis);
				if (extra.integer) {
					delete extra.integer;
					extra.numberFormatter = (v) => String(Math.round(v));
				}
				opts.axisOptions = Object.assign({}, opts.axisOptions, extra);
			}
			delete opts.ev_axis;
			try {
				new frappe.Chart($b.find(".ns-chart-el")[0], opts);
			} catch (e) {
				$b.find(".ns-chart").remove();
			}
		}
	}
}
