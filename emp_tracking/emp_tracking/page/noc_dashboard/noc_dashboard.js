// NOC Dashboard — Frappe Desk page
// Route: /app/noc-dashboard
//
// Three sections on one page, all built from Complaint Information:
//   1. Complaints Overview — open complaints right now (noc_dashboard.py `get_dashboard_data`)
//   2. Performance — the NOC report workbook's numbers for a date range (noc_reports.py
//      `get_performance`; the same numbers as the five NOC reports)
//   3. Employee Sheet — one employee's month, day by day (noc_dashboard.py `get_employee_sheet`)
// All counting happens in Python; this file only draws.
//
// Change log (earlier changes are in git history)
//   2026-11-02  EVision design layer (public/css/evision.css): colours in the page's <style> are --ev-* tokens (Frappe
//               Espresso, light + dark mode) instead of hex; lighter type weights;
//               no coloured top strip on KPI tiles; skeleton loading and icon empty states.
//   2026-11-26  Performance section (user's request: show the dashboard like the NOC report
//               workbook): KPI tiles, daily received / closed / pending chart, team table, TAT
//               buckets, major outage days, and a "NOC Reports" button menu.
//   2026-11-26  Redesign (user: "doesn't look good"): Performance opens with a carry-forward
//               strip (opening + received - closed = pending) and the SLA split; quick ranges;
//               team table with SLA bars; time-to-close as one split bar; busiest days by month;
//               sentence-case labels. Chart colours read from the theme.
//   2026-11-26  Tabs (user's request): Live complaints / Performance / Employee sheet, one at a
//               time; the last tab is remembered; hidden tabs load when first opened.
//   2026-11-26  Map tab (user's request): complaints only, coloured by status; clicking one shows
//               its details in the side panel with an "Open complaint" button
//               (noc_dashboard.py get_complaint_map).
//   2026-11-26  Open complaints stand out on the map (user's request): dot with a pulsing ring
//               (still when the system asks for reduced motion) and an age badge; counts above
//               the map (open, over 4 h, oldest); side panel lists open complaints, oldest
//               first, and a click there zooms to the complaint.
//   2026-11-26  Opening a complaint draws its node's KMZ fibre routes (own building thick blue,
//               others thin violet), with "Open node on KMZ Map" and "Hide routes"
//               (noc_dashboard.py get_complaint_route).
//   2026-11-26  Map key (index) on the map (user's request): complaint colours, ring and badge,
//               and the two route lines; click its title to fold it.
//   2026-11-27  Hovering a violet route highlights every route to that building (bold, full
//               colour, on top); the tooltip names the building (user's request).
//   2026-11-27  Building points (user's request): cyan squares at each building's KMZ pin, the
//               complaint's own building larger with a blue border; hovering one lights up its
//               routes. Map panes fix the order: routes < buildings < complaints.

frappe.pages['noc-dashboard'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('NOC Dashboard'),
		single_column: true,
	});

	// 2026-11-26: kept on the page wrapper so it can be reached from the console when checking
	wrapper.noc_dashboard = new NocDashboard(page);
};

var NOC_REFRESH_INTERVAL_MS = 60000;
var NOC_METHOD = 'emp_tracking.emp_tracking.page.noc_dashboard.noc_dashboard.';
// 2026-11-26: Performance section data, shared with the NOC reports
var NOC_PERF_METHOD = 'emp_tracking.noc_reports.get_performance';
// The NOC workbook's tabs, as reports (button menu and links in the Performance section)
var NOC_REPORTS = [
	['NOC Pending Summary', 'Pending Summary'],
	['NOC Unique Cut Summary', 'Unique Cut Summary'],
	['NOC Unique Cut Master', 'Unique Cut Master'],
	['NOC Major Outage Closure', 'Major Outage Closure'],
	['NOC SLA TAT Summary', 'SLA / TAT Summary'],
];

// Same visual language as the Manager Dashboard (md-*) and Workforce Dashboards (wd-*) pages:
// cards, neutral text, tinted icon tiles, uppercase table headers (2026-11-02: --ev-* tokens).
var NOC_STYLE = [
	'<style>',
	'.noc-root{padding:12px 16px 28px}',
	'@media (max-width:480px){.noc-root{padding:10px 12px 24px}}',
	// section head
	'.noc-head{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;margin:26px 0 16px}',
	'.noc-head:first-child{margin-top:6px}',
	'.noc-title{font-size:16px;font-weight:600;color:var(--ev-text);line-height:1.2}',
	'.noc-sub{font-size:12px;color:var(--ev-text-4);margin-top:2px}',
	'.noc-head-right{display:flex;align-items:flex-end;gap:10px;flex-wrap:wrap}',
	'.noc-badge{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:500;color:var(--ev-text-3);background:var(--ev-card);',
	'  border:1px solid var(--ev-border);border-radius:8px;padding:6px 10px;white-space:nowrap}',
	'.noc-badge .dot{width:7px;height:7px;border-radius:50%;background:var(--ev-ok)}',
	'.noc-filters{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end}',
	'.noc-filters .frappe-control{margin:0;min-width:180px}',
	'.noc-filters .form-group{margin:0}',
	'.noc-filters .control-label{font-size:11px;color:var(--ev-text-4);font-weight:500;margin-bottom:3px}',
	// stat tiles
	'.noc-kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(178px,1fr));gap:12px;margin-bottom:18px}',
	'.noc-kpi{background:var(--ev-card);border:1px solid var(--ev-border);border-top:1px solid var(--ev-border);border-radius:12px;padding:13px 14px;',
	'  display:flex;align-items:center;gap:12px;box-shadow:0 1px 2px rgba(15,23,42,.04);transition:box-shadow .15s,transform .15s;min-width:0}',
	'.noc-kpi.clickable{cursor:pointer}',
	'.noc-kpi.clickable:hover{box-shadow:0 4px 10px rgba(15,23,42,.08);transform:translateY(-1px)}',
	'.noc-kpi-icon{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;',
	'  background:var(--ev-accent-bg);color:var(--ev-accent)}',
	'.noc-kpi-body{min-width:0;flex:1}',
	'.noc-kpi .val{font-size:19px;font-weight:600;color:var(--ev-text);line-height:1.15;font-variant-numeric:tabular-nums;white-space:nowrap}',
	'.noc-kpi .lbl{font-size:10.5px;color:var(--ev-text-4);margin-top:2px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
	'.noc-kpi .hint{font-size:10.5px;color:var(--ev-text-5);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
	'.noc-kpi.t-blue{border-top-color:var(--ev-border)}.noc-kpi.t-blue .noc-kpi-icon{background:var(--ev-accent-bg);color:var(--ev-accent)}',
	'.noc-kpi.t-green{border-top-color:var(--ev-border)}.noc-kpi.t-green .noc-kpi-icon{background:var(--ev-ok-bg);color:var(--ev-ok)}.noc-kpi.t-green .val{color:var(--ev-ok)}',
	'.noc-kpi.t-orange{border-top-color:var(--ev-border)}.noc-kpi.t-orange .noc-kpi-icon{background:var(--ev-warn-bg);color:var(--ev-warn)}.noc-kpi.t-orange .val{color:var(--ev-warn)}',
	'.noc-kpi.t-red{border-top-color:var(--ev-border)}.noc-kpi.t-red .noc-kpi-icon{background:var(--ev-bad-bg);color:var(--ev-bad)}.noc-kpi.t-red .val{color:var(--ev-bad)}',
	'.noc-kpi.t-purple{border-top-color:var(--ev-border)}.noc-kpi.t-purple .noc-kpi-icon{background:var(--ev-violet-bg);color:var(--ev-violet)}.noc-kpi.t-purple .val{color:var(--ev-violet)}',
	// cards
	'.noc-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px;align-items:stretch}',
	'.noc-grid>.noc-card{grid-column:span 4}',
	'@media (max-width:1100px){.noc-grid>.noc-card{grid-column:span 6}}',
	'@media (max-width:767px){.noc-grid>.noc-card{grid-column:span 12}}',
	// 2026-11-26: tab bar (one section per tab); the first section heading sits right under it
	'.noc-tabs{display:flex;gap:4px;border-bottom:1px solid var(--ev-border);margin:2px 0 4px;overflow-x:auto}',
	'.noc-tabs button{border:0;background:none;padding:10px 14px 11px;font-size:13.5px;font-weight:500;color:var(--ev-text-4);',
	'  border-bottom:2px solid transparent;margin-bottom:-1px;white-space:nowrap;display:inline-flex;align-items:center;gap:7px}',
	'.noc-tabs button:hover{color:var(--ev-text)}',
	'.noc-tabs button.on{color:var(--ev-text);border-bottom-color:var(--ev-text);font-weight:600}',
	'.noc-tabs button:focus{outline:none}.noc-tabs button:focus-visible{box-shadow:inset 0 0 0 2px var(--ev-accent);border-radius:6px}',
	'.noc-tab-count{font-size:11px;font-weight:600;color:var(--ev-warn);background:var(--ev-warn-bg);border-radius:9px;padding:1px 7px}',
	'.noc-pane>.noc-head:first-child{margin-top:18px}',
	// 2026-11-26: Map tab: map + details panel side by side, stacked on small screens
	'.noc-mapwrap{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:14px}',
	'@media (max-width:900px){.noc-mapwrap{grid-template-columns:1fr}}',
	'.noc-map{height:calc(100vh - 260px);min-height:420px;border:1px solid var(--ev-border);border-radius:14px;overflow:hidden;z-index:0}',
	'.noc-mapside{background:var(--ev-card);border:1px solid var(--ev-border);border-radius:14px;padding:16px;overflow:auto;',
	'  max-height:calc(100vh - 260px);min-height:220px}',
	'.noc-mapside .t{font-size:15px;font-weight:600;color:var(--ev-text)}',
	'.noc-mapside .s{font-size:12px;color:var(--ev-text-4);margin:2px 0 12px}',
	'.noc-mapside dl{display:grid;grid-template-columns:110px 1fr;gap:7px 10px;margin:0 0 14px;font-size:12.5px}',
	'.noc-mapside dt{color:var(--ev-text-4);font-weight:500}.noc-mapside dd{margin:0;color:var(--ev-text);word-break:break-word}',
	'.noc-mapside .empty{color:var(--ev-text-4);font-size:12.5px;text-align:center;padding:40px 10px}',
	'.noc-pill{display:inline-block;font-size:11px;font-weight:600;border-radius:10px;padding:2px 9px;margin-right:6px}',
	'.noc-pill.open{color:var(--ev-warn);background:var(--ev-warn-bg)}.noc-pill.late{color:var(--ev-bad);background:var(--ev-bad-bg)}',
	'.noc-pill.ok{color:var(--ev-ok);background:var(--ev-ok-bg)}.noc-pill.done{color:var(--ev-text-3);background:var(--ev-muted)}',
	'.noc-maplegend{display:flex;flex-wrap:wrap;gap:16px;align-items:center;font-size:12px;color:var(--ev-text-4);margin-top:10px}',
	'.noc-maplegend i{display:inline-block;width:10px;height:10px;border-radius:5px;margin-right:6px;vertical-align:-1px}',
	'.noc-maplegend .warn{color:var(--ev-warn);font-weight:600}',
	// 2026-11-26: open complaints stand out: a dot with a pulsing ring and an age badge
	'.noc-pin{position:relative;width:18px;height:18px}',
	'.noc-pin .dot{position:absolute;inset:3px;border-radius:50%;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.35)}',
	'.noc-pin .ring{position:absolute;inset:-6px;border-radius:50%;border:3px solid currentColor;opacity:0;animation:noc-pulse 1.8s ease-out infinite}',
	'.noc-pin .age{position:absolute;left:16px;top:-12px;font:600 10.5px/1 Inter,system-ui,sans-serif;color:#fff;',
	'  border-radius:8px;padding:3px 6px;white-space:nowrap;box-shadow:0 1px 3px rgba(0,0,0,.3)}',
	'.noc-pin .age b{color:#fff;font-weight:600}',
	'@keyframes noc-pulse{0%{transform:scale(.5);opacity:.85}100%{transform:scale(1.6);opacity:0}}',
	'@media (prefers-reduced-motion:reduce){.noc-pin .ring{animation:none;opacity:.5}}',
	// list of open complaints in the side panel, oldest first
	'.noc-openlist .row{display:flex;gap:10px;align-items:flex-start;padding:9px 6px;border-bottom:1px solid var(--ev-border);cursor:pointer;border-radius:8px}',
	'.noc-openlist .row:hover{background:var(--ev-subtle)}',
	'.noc-openlist .sw{width:10px;height:10px;border-radius:5px;margin-top:4px;flex-shrink:0}',
	'.noc-openlist .nm{font-size:12.5px;font-weight:600;color:var(--ev-text)}',
	'.noc-openlist .mt{font-size:11.5px;color:var(--ev-text-4);margin-top:1px}',
	'.noc-openlist .ag{margin-left:auto;font-size:11.5px;font-weight:600;white-space:nowrap}',
	'.noc-openlist .h{font-size:12px;font-weight:600;color:var(--ev-text-3);margin:0 0 6px}',
	'.noc-mapstats{display:flex;gap:18px;flex-wrap:wrap;margin:-6px 0 12px;font-size:12.5px;color:var(--ev-text-3)}',
	'.noc-route{font-size:12px;color:var(--ev-text-3);background:var(--ev-subtle);border-radius:10px;padding:10px 12px;margin:0 0 14px}',
	// 2026-11-26: map key (index) in the map's corner; the title folds it away
	'.noc-mapkey{background:var(--ev-card);color:var(--ev-text-2);border:1px solid var(--ev-border);border-radius:10px;',
	'  padding:8px 12px 9px;font-size:11.5px;line-height:1.3;box-shadow:0 2px 8px rgba(15,23,42,.15);min-width:210px}',
	'.noc-mapkey .kt{font-weight:600;color:var(--ev-text);cursor:pointer;margin-bottom:6px;user-select:none}',
	'.noc-mapkey .kt::after{content:" \\25BE";color:var(--ev-text-5)}',
	'.noc-mapkey.folded .kt{margin-bottom:0}.noc-mapkey.folded .kt::after{content:" \\25B8"}',
	'.noc-mapkey.folded .kb{display:none}',
	'.noc-mapkey .kr{display:flex;align-items:center;gap:8px;padding:2px 0}',
	'.noc-mapkey .ks{width:28px;display:inline-flex;justify-content:center;align-items:center;flex-shrink:0}',
	'.noc-mapkey .dot{width:11px;height:11px;border-radius:50%;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.25)}',
	'.noc-mapkey .ring{width:14px;height:14px;border-radius:50%;border:2px solid var(--ev-bad)}',
	'.noc-mapkey .badge{font:600 9.5px/1 Inter,system-ui,sans-serif;color:#fff;background:var(--ev-bad);border-radius:7px;padding:2px 5px;font-style:normal}',
	'.noc-mapkey .line{width:24px;border-radius:2px}',
	// 2026-11-27: building point, a cyan square (complaints are round); own building larger, blue border
	'.noc-bldg{width:11px;height:11px;background:var(--ev-cyan);border:2px solid #fff;border-radius:2px;box-shadow:0 0 0 1px rgba(0,0,0,.3);box-sizing:border-box;display:inline-block}',
	'.noc-bldg.own{width:16px;height:16px;border:3px solid var(--ev-accent)}',
	'.noc-route b{color:var(--ev-text)}',
	'.noc-mapstats b{font-size:18px;font-weight:600;margin-right:6px;font-variant-numeric:tabular-nums}',
	// 2026-11-26: Performance section. Meaning colours, the same everywhere on it:
	// blue = received, green = restored / In SLA, amber = pending, red = Out SLA.
	'.noc-grid>.noc-card.w12{grid-column:span 12}.noc-grid>.noc-card.w8{grid-column:span 8}',
	'@media (max-width:1100px){.noc-grid>.noc-card.w8{grid-column:span 12}}',
	'.noc-chart{min-height:250px;margin:0 -6px}',
	// quick ranges next to the date filters
	'.noc-ranges{display:flex;gap:4px;align-self:flex-end;padding-bottom:1px}',
	'.noc-ranges button{border:1px solid var(--ev-border);background:var(--ev-card);color:var(--ev-text-3);font-size:12px;font-weight:500;',
	'  border-radius:7px;padding:5px 10px;line-height:1.2}',
	'.noc-ranges button:hover{color:var(--ev-text)}',
	'.noc-ranges button:focus{outline:none;box-shadow:none}.noc-ranges button:focus-visible{box-shadow:0 0 0 2px var(--ev-accent)}',
	'.noc-ranges button.on{background:var(--ev-text);border-color:var(--ev-text);color:var(--ev-card)}',
	// carry-forward strip: opening + received - closed = pending, then the SLA split
	'.noc-flow{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:0;background:var(--ev-card);border:1px solid var(--ev-border);',
	'  border-radius:16px;margin-bottom:14px;overflow:hidden}',
	'@media (max-width:900px){.noc-flow{grid-template-columns:1fr}}',
	'.noc-eq{display:flex;align-items:center;justify-content:space-between;gap:6px;padding:22px 26px;flex-wrap:wrap}',
	'.noc-table th.left{text-align:left}',
	'.noc-term .n{font-size:34px;font-weight:600;line-height:1;letter-spacing:-.02em;font-variant-numeric:tabular-nums;color:var(--ev-text)}',
	'.noc-term .l{font-size:12px;color:var(--ev-text-4);margin-top:8px;font-weight:500}',
	'.noc-term.recv .n{color:var(--ev-accent)}.noc-term.done .n{color:var(--ev-ok)}.noc-term.left .n{color:var(--ev-warn)}',
	'.noc-term.left.zero .n{color:var(--ev-ok)}',
	'.noc-op{font-size:24px;font-weight:300;color:var(--ev-text-5);padding-bottom:20px;line-height:1}',
	'@media (max-width:600px){.noc-term .n{font-size:24px}.noc-op{font-size:18px;padding-bottom:20px}.noc-eq{padding:18px}}',
	'.noc-sla{padding:22px 26px;border-left:1px solid var(--ev-border);display:flex;flex-direction:column;justify-content:center;gap:10px}',
	'@media (max-width:900px){.noc-sla{border-left:0;border-top:1px solid var(--ev-border)}}',
	'.noc-sla .top{display:flex;align-items:baseline;gap:10px}',
	'.noc-sla .pct{font-size:34px;font-weight:600;line-height:1;letter-spacing:-.02em;font-variant-numeric:tabular-nums}',
	'.noc-sla .pct.good{color:var(--ev-ok)}.noc-sla .pct.poor{color:var(--ev-bad)}',
	'.noc-sla .cap{font-size:12.5px;color:var(--ev-text-3)}',
	'.noc-split{display:flex;height:10px;border-radius:5px;overflow:hidden;background:var(--ev-muted)}',
	'.noc-split .in{background:var(--ev-ok)}.noc-split .out{background:var(--ev-bad)}',
	'.noc-split.sm{height:6px;border-radius:3px;min-width:90px}',
	'.noc-facts{display:flex;gap:18px;flex-wrap:wrap;font-size:12px;color:var(--ev-text-4)}',
	'.noc-facts b{color:var(--ev-text);font-weight:600;font-variant-numeric:tabular-nums}',
	// TAT: one segmented bar + legend
	'.noc-tat-bar{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--ev-muted);margin:2px 0 14px}',
	'.noc-tat-row{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--ev-border);font-size:12.5px;color:var(--ev-text-2)}',
	'.noc-tat-row:last-child{border-bottom:0}',
	'.noc-tat-row .sw{width:10px;height:10px;border-radius:3px;flex-shrink:0}',
	'.noc-tat-row .nm{flex:1}.noc-tat-row .ct{font-weight:600;color:var(--ev-text);font-variant-numeric:tabular-nums}',
	'.noc-tat-row .pc{width:46px;text-align:right;color:var(--ev-text-5);font-variant-numeric:tabular-nums}',
	// team table cells
	'.noc-table td.pend{color:var(--ev-warn);font-weight:600}',
	'.noc-table td .slacell{display:flex;align-items:center;gap:10px;justify-content:flex-end}',
	'.noc-table td .slacell span{width:46px;text-align:right;font-weight:600}',
	'.noc-table td .good{color:var(--ev-ok)}.noc-table td .poor{color:var(--ev-bad)}',
	'.noc-table td.wrap{text-align:left;white-space:normal;min-width:220px;color:var(--ev-text-3)}',
	'.noc-rank{display:inline-flex;width:20px;height:20px;border-radius:10px;align-items:center;justify-content:center;font-size:11px;font-weight:600;',
	'  background:var(--ev-muted);color:var(--ev-text-3)}.noc-rank.r1{background:var(--ev-bad-bg);color:var(--ev-bad)}',
	'.noc-month td{background:var(--ev-subtle);color:var(--ev-text-4)!important;font-size:11.5px!important;font-weight:600!important;padding:6px 10px!important}',
	'.noc-perf-empty{background:var(--ev-card);border:1px dashed var(--ev-border-strong);border-radius:16px;padding:40px 20px;text-align:center}',
	'.noc-perf-empty .t{font-size:14px;font-weight:600;color:var(--ev-text)}',
	'.noc-perf-empty .s{font-size:12.5px;color:var(--ev-text-4);margin:6px 0 14px}',
	'.noc-card{background:var(--ev-card);border:1px solid var(--ev-border);border-radius:14px;padding:14px 16px;min-width:0;display:flex;flex-direction:column;',
	'  box-shadow:0 1px 2px rgba(15,23,42,.04)}',
	'.noc-card-head{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:12px;min-height:26px}',
	'.noc-card-head .title{font-size:13.5px;font-weight:600;color:var(--ev-text);display:flex;align-items:center;gap:10px}',
	'.noc-card-head .count{color:var(--ev-text-4);font-weight:500}',
	'.noc-card-head .sub{font-size:11px;color:var(--ev-text-5);font-weight:600}',
	'.noc-group{display:flex;justify-content:space-between;font-size:11.5px;color:var(--ev-text-4);',
	'  font-weight:500;padding:10px 0 4px;border-bottom:1px solid var(--ev-border)}',
	'.noc-group:first-of-type{padding-top:0}',
	// bars
	'.noc-bar{padding:7px 0;border-bottom:1px solid var(--ev-border)}',
	'.noc-bar:last-child{border-bottom:0}',
	'.noc-bar .line{display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:12.5px;font-weight:600;color:var(--ev-text-2);margin-bottom:5px}',
	'.noc-bar .line .name{display:flex;align-items:center;gap:8px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
	'.noc-bar .line .num{display:flex;align-items:center;gap:8px;font-weight:600;color:var(--ev-text);font-variant-numeric:tabular-nums;white-space:nowrap}',
	'.noc-bar .track{height:7px;border-radius:4px;background:var(--ev-muted)}',
	'.noc-bar .fill{height:7px;border-radius:4px;min-width:3px;background:var(--ev-accent)}',
	'.noc-bar .fill.warn{background:var(--ev-warn)}.noc-bar .fill.bad{background:var(--ev-bad)}.noc-bar .fill.ok{background:var(--ev-ok)}',
	'.noc-avatar{width:26px;height:26px;border-radius:13px;display:inline-flex;align-items:center;justify-content:center;color:#fff;font-weight:600;',
	'  font-size:10.5px;flex-shrink:0}',
	'.noc-avatar.lg{width:42px;height:42px;border-radius:21px;font-size:14px}',
	'.noc-chip{display:inline-block;font-size:10.5px;font-weight:500;padding:3px 9px;border-radius:20px;white-space:nowrap;line-height:1.4}',
	'.noc-chip.red{color:var(--ev-bad);background:var(--ev-bad-bg)}.noc-chip.orange{color:var(--ev-warn);background:var(--ev-warn-bg)}',
	'.noc-empty{text-align:center;padding:30px 14px;color:var(--ev-text-5);font-size:12.5px}',
	'.noc-loading{padding:60px 0;text-align:center;color:var(--ev-text-5);font-size:13px}',
	// employee sheet
	'.noc-person{display:flex;gap:12px;align-items:center}',
	'.noc-person .name{font-weight:600;font-size:13.5px;color:var(--ev-text)}',
	'.noc-person .meta{font-size:11.5px;color:var(--ev-text-4);margin-top:2px}',
	'.noc-table-wrap{overflow:auto;max-height:520px}',
	'.noc-table{width:100%;border-collapse:separate;border-spacing:0}',
	'.noc-table thead th{position:sticky;top:0;background:var(--ev-card);text-align:right;font-size:11.5px;',
	'  color:var(--ev-text-4);font-weight:500;padding:6px 10px;border-bottom:1px solid var(--ev-border);white-space:nowrap;z-index:1}',
	'.noc-table tr.groups th{text-align:center;color:var(--ev-text-4);border-bottom:0;padding-bottom:0}',
	'.noc-table tr.cols th{top:22px}',
	'.noc-table tbody td{padding:8px 10px;font-size:12px;color:var(--ev-text-2);border-bottom:1px solid var(--ev-border);text-align:right;white-space:nowrap;',
	'  font-variant-numeric:tabular-nums}',
	'.noc-table th:first-child,.noc-table td:first-child{text-align:left}',
	'.noc-table td:first-child{font-weight:500;color:var(--ev-text)}',
	'.noc-table .split{border-left:1px solid var(--ev-border)}',
	'.noc-table td.zero{color:var(--ev-text-6)}',
	'.noc-table td .day{color:var(--ev-text-5);font-size:10.5px;font-weight:600;margin-left:6px}',
	'.noc-table tr.off td{background:var(--ev-subtle)}',
	'.noc-table tr.today td:first-child{color:var(--ev-accent);box-shadow:inset 3px 0 0 var(--ev-accent)}',
	'.noc-table tbody tr:hover td{background:var(--ev-subtle)}',
	'.noc-table tr.total td{position:sticky;bottom:0;background:var(--ev-subtle);font-weight:600;color:var(--ev-text);border-top:1px solid var(--ev-border);border-bottom:0}',
	'</style>',
].join('');

var NOC_AVATAR_PALETTE = ['#2563eb', '#0d9488', '#9333ea', '#ea580c', '#0891b2', '#4f46e5', '#be185d', '#16803d'];

// Inline icons, currentColor so the tile colour drives them.
var NOC_ICONS = {
	list: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 6h11M9 12h11M9 18h11"/><path d="m4 6 1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"/></svg>',
	users: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
	person: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
	clock: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
	alert: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
	check: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
	pin: '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/></svg>',
	home: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10"/></svg>',
	office: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3" width="14" height="18" rx="1"/><path d="M9 8h2M13 8h2M9 12h2M13 12h2M10 21v-4h4v4"/></svg>',
};

// 2026-11-26: one tab per section (user's request); the tab bar is the page's first row.
var NOC_TABS = [
	['live', __('Live complaints')],
	['perf', __('Performance')],
	// 2026-11-26: complaints on a map, details on click (user's request)
	['map', __('Map')],
	['sheet', __('Employee sheet')],
];
var NOC_TAB_KEY = 'noc_dashboard_tab';

var NOC_LAYOUT = [
	'<div class="noc-root">',
	'<div class="noc-tabs" role="tablist">' + NOC_TABS.map((t) =>
		'<button type="button" role="tab" data-tab="' + t[0] + '">' + t[1] +
		(t[0] === 'live' ? ' <span class="noc-tab-count" data-slot="live-count"></span>' : '') + '</button>').join('') + '</div>',
	'<div class="noc-pane" data-pane="live">',
	'<div class="noc-head"><div><div class="noc-title">' + __('Complaints Overview') + '</div>',
	'<div class="noc-sub">' + __('Open complaints right now') + '</div></div>',
	'<div class="noc-head-right"><div class="noc-filters" data-slot="overview-filters"></div>',
	'<span class="noc-badge"><span class="dot"></span><span data-slot="updated">' + __('Loading…') + '</span></span></div></div>',
	'<div data-slot="overview"></div>',
	'</div>',
	// 2026-11-26: Performance section
	'<div class="noc-pane" data-pane="perf">',
	'<div class="noc-head"><div><div class="noc-title">' + __('Performance') + '</div>',
	'<div class="noc-sub" data-slot="perf-sub">' + __('Own teams, own fibre faults') + '</div></div>',
	'<div class="noc-head-right"><div class="noc-ranges" data-slot="perf-ranges"></div>',
	'<div class="noc-filters" data-slot="perf-filters"></div></div></div>',
	'<div data-slot="perf"></div>',
	'</div>',
	// 2026-11-26: Map tab
	'<div class="noc-pane" data-pane="map">',
	'<div class="noc-head"><div><div class="noc-title">' + __('Complaints map') + '</div>',
	'<div class="noc-sub" data-slot="map-sub">' + __('Click a complaint to see its details') + '</div></div>',
	'<div class="noc-head-right"><div class="noc-filters" data-slot="map-filters"></div></div></div>',
	'<div class="noc-mapstats" data-slot="map-stats"></div>',
	'<div class="noc-mapwrap"><div class="noc-map" data-slot="map"></div>',
	'<div class="noc-mapside" data-slot="map-side"></div></div>',
	'<div class="noc-maplegend" data-slot="map-legend"></div>',
	'</div>',
	'<div class="noc-pane" data-pane="sheet">',
	'<div class="noc-head"><div><div class="noc-title">' + __('Employee Sheet') + '</div>',
	'<div class="noc-sub">' + __('Day-by-day hours by location and complaints for one employee or area supervisor') + '</div></div>',
	'<div class="noc-head-right"><div class="noc-filters" data-slot="sheet-filters"></div></div></div>',
	'<div data-slot="sheet"></div>',
	'</div>',
	'</div>',
].join('');

class NocDashboard {
	constructor(page) {
		this.page = page;
		this.root = $(NOC_STYLE + NOC_LAYOUT).appendTo(page.main);
		this.slot = (name) => this.root.find('[data-slot="' + name + '"]');

		// Each section keeps its own filters next to its heading, labels always visible.
		this.closedDate = this.control('overview-filters', {
			fieldname: 'closed_date', fieldtype: 'Date', label: __('Closed Date'),
		}, () => this.refresh());
		this.employee = this.control('sheet-filters', {
			fieldname: 'employee', fieldtype: 'Link', options: 'Employee', label: __('Employee / Area Supervisor'),
		}, () => this.refreshSheet());
		this.sheetMonth = this.control('sheet-filters', {
			fieldname: 'sheet_month', fieldtype: 'Date', label: __('Month (pick any date)'),
		}, () => this.refreshSheet());
		// 2026-11-26: Performance filters (this month by default)
		this.perfFrom = this.control('perf-filters', {
			fieldname: 'perf_from', fieldtype: 'Date', label: __('From'),
		}, () => this.refreshPerf());
		this.perfTo = this.control('perf-filters', {
			fieldname: 'perf_to', fieldtype: 'Date', label: __('To'),
		}, () => this.refreshPerf());
		this.perfTeam = this.control('perf-filters', {
			fieldname: 'perf_team', fieldtype: 'Link', options: 'Maintenance Team', label: __('Team'),
		}, () => this.refreshPerf());
		// 2026-11-26: Map tab filters (Open = every open complaint; dates apply to Closed / All)
		this.mapStatus = this.control('map-filters', {
			fieldname: 'map_status', fieldtype: 'Select', options: 'Open\nClosed\nAll', label: __('Show'),
		}, () => this.refreshMap());
		this.mapFrom = this.control('map-filters', {
			fieldname: 'map_from', fieldtype: 'Date', label: __('From'),
		}, () => this.refreshMap());
		this.mapTo = this.control('map-filters', {
			fieldname: 'map_to', fieldtype: 'Date', label: __('To'),
		}, () => this.refreshMap());
		this.mapTeam = this.control('map-filters', {
			fieldname: 'map_team', fieldtype: 'Link', options: 'Maintenance Team', label: __('Team'),
		}, () => this.refreshMap());
		this.mapStatus.set_value('Open');
		this.mapFrom.set_value(frappe.datetime.month_start());
		this.mapTo.set_value(frappe.datetime.get_today());
		this.closedDate.set_value(frappe.datetime.get_today());
		this.sheetMonth.set_value(frappe.datetime.get_today());
		this.perfFrom.set_value(frappe.datetime.month_start());
		this.perfTo.set_value(frappe.datetime.get_today());
		this.perfRanges();

		page.set_primary_action(__('Refresh'), () => {
			this.refresh();
			this.stale = { perf: true, sheet: true, map: true };
			this.refreshTab();
		}, 'refresh');
		page.add_inner_button(__('View Complaints'), () => frappe.set_route('List', 'Complaint Information'));
		NOC_REPORTS.forEach((r) => {
			page.add_inner_button(__(r[1]), () => this.openReport(r[0]), __('NOC Reports'));
		});

		this.slot('overview').html('<div class="noc-loading">' + __('Loading…') + '</div>');
		// 2026-11-26: tabs. Live complaints always load (the tab shows their count); Performance
		// and Employee sheet load when their tab is first opened, or again after their filters changed.
		this.stale = { perf: true, sheet: true, map: true };
		this.root.find('.noc-tabs button').on('click', (e) => this.showTab($(e.currentTarget).data('tab')));
		var saved = null;
		try { saved = localStorage.getItem(NOC_TAB_KEY); } catch (e) { /* storage blocked: start on the first tab */ }
		this.showTab(NOC_TABS.some((t) => t[0] === saved) ? saved : 'live');
		this.refresh();
		this.timer = setInterval(() => {
			if (frappe.get_route()[0] === 'noc-dashboard') this.refresh();
		}, NOC_REFRESH_INTERVAL_MS);
	}

	// ---- tabs (2026-11-26) -------------------------------------------------

	showTab(tab) {
		this.tab = tab;
		this.root.find('.noc-tabs button').each((i, b) => {
			var on = $(b).data('tab') === tab;
			$(b).toggleClass('on', on).attr('aria-selected', on ? 'true' : 'false');
		});
		this.root.find('.noc-pane').each((i, p) => $(p).toggle($(p).data('pane') === tab));
		try { localStorage.setItem(NOC_TAB_KEY, tab); } catch (e) { /* not remembered, no harm */ }
		this.refreshTab();
	}

	// Loads the open tab when its data is missing or its filters changed while it was hidden
	refreshTab() {
		if (this.tab === 'perf' && this.stale.perf) this.refreshPerf();
		if (this.tab === 'sheet' && this.stale.sheet) this.refreshSheet();
		if (this.tab === 'map') {
			if (this.stale.map) this.refreshMap();
			else if (this.map) setTimeout(() => this.map.invalidateSize(), 50); // map was hidden: fit it again
		}
	}

	// ---- complaints map (2026-11-26) ---------------------------------------

	refreshMap() {
		if (!this.stale || !this.mapStatus || !this.mapTeam) return; // controls still being built
		if (this.tab !== 'map') { this.stale.map = true; return; }
		this.stale.map = false;
		// Leaflet is loaded on demand in Frappe 16.54 (as on the KMZ Map page)
		Promise.all([frappe.require('leaflet.bundle.js'), frappe.require('leaflet.bundle.css')]).then(() => {
			frappe.call({
				method: NOC_METHOD + 'get_complaint_map',
				args: {
					status: this.mapStatus.get_value() || 'Open',
					from_date: this.mapFrom.get_value(),
					to_date: this.mapTo.get_value(),
					team: this.mapTeam.get_value() || '',
				},
				callback: (r) => r.message && this.renderMap(r.message),
			});
		});
	}

	makeMap() {
		if (this.map) return;
		var d = frappe.utils.map_defaults;
		L.Icon.Default.imagePath = d.image_path;
		this.map = L.map(this.slot('map')[0], { preferCanvas: true }).setView(d.center, 11);
		var street = L.tileLayer(d.tiles.default_tile.url, d.tiles.default_tile.options).addTo(this.map);
		var satellite = L.tileLayer(d.tiles.satellite_tile.url, d.tiles.satellite_tile.options);
		L.control.layers({ [__('Street')]: street, [__('Satellite')]: satellite }).addTo(this.map);
		// 2026-11-27: own panes so the order is fixed: routes (overlay pane, 400) < building points
		// (450) < closed complaint dots (500, own canvas) < open complaint pins (marker pane, 600)
		this.map.createPane('nocBuildings').style.zIndex = 450;
		this.map.createPane('nocComplaints').style.zIndex = 500;
		this.complaintRenderer = L.canvas({ pane: 'nocComplaints' });
		// 2026-11-26: the opened complaint's node routes, drawn under the complaint pins
		this.routeLayer = L.layerGroup().addTo(this.map);
		this.markers = L.layerGroup().addTo(this.map);
	}

	// Date: 2026-11-26
	// The map's key (index), in the map's bottom-left corner (user's request): what each complaint
	// colour, the pulsing ring and badge, and the two route lines mean. Built once; it can be
	// folded away with its title.
	mapKey(limitHours) {
		if (this.keyControl) return;
		var swatch = (c) => '<i class="dot" style="background:' + c + '"></i>';
		var line = (c, w) => '<i class="line" style="background:' + c + ';height:' + w + 'px"></i>';
		var rows = [
			[swatch(this.themeColour('--ev-warn', '#d97706')), __('Open complaint')],
			[swatch(this.themeColour('--ev-bad', '#dc2626')), __('Open over {0} hours', [limitHours])],
			[swatch(this.themeColour('--ev-ok', '#15803d')), __('Closed within SLA')],
			[swatch('#94a3b8'), __('Closed late')],
			['<i class="ring"></i>', __('Pulsing ring: still open')],
			['<i class="badge">30d</i>', __('Badge: how long it has been open')],
			[line(this.themeColour('--ev-accent', '#2563eb'), 5), __('Fibre route to the complaint\'s building')],
			[line(this.themeColour('--ev-violet', '#7c3aed'), 2), __('Other fibre routes of its node')],
			['<i class="noc-bldg"></i>', __('Building (KMZ pin)')],
			['<i class="noc-bldg own"></i>', __('The complaint\'s building')],
			[line(this.themeColour('--ev-violet', '#7c3aed'), 6), __('Hover a building or violet route: its routes light up')],
		];
		var Key = L.Control.extend({
			options: { position: 'bottomleft' },
			onAdd: () => {
				var el = L.DomUtil.create('div', 'noc-mapkey');
				el.innerHTML = '<div class="kt">' + __('Map key') + '</div><div class="kb">' +
					rows.map((r) => '<div class="kr"><span class="ks">' + r[0] + '</span>' + noc_esc(r[1]) + '</div>').join('') + '</div>';
				L.DomEvent.disableClickPropagation(el);
				el.querySelector('.kt').addEventListener('click', () => el.classList.toggle('folded'));
				return el;
			},
		});
		this.keyControl = new Key().addTo(this.map);
	}

	// Date: 2026-11-26
	// Draws the complaint's node and its KMZ fibre routes: routes to the complaint's own building
	// thick blue, the node's other routes thin violet; the view fits the routes and the complaint.
	drawRoute(p) {
		var box = this.slot('map-side').find('[data-route]');
		this.routeLayer.clearLayers();
		frappe.call({
			method: NOC_METHOD + 'get_complaint_route',
			args: { complaint: p.name },
			callback: (r) => {
				var d = r.message || {};
				if (!d.node) {
					box.html(__('No node known for this complaint (no Node ID, site or LINKID with a node), so no route to show.'));
					return;
				}
				var own = d.routes.filter((x) => x.own_site).length;
				var accent = this.themeColour('--ev-accent', '#2563eb');
				var violet = this.themeColour('--ev-violet', '#7c3aed');
				// a node's routes can spread over the whole city, so the view fits the complaint with its
				// own building's routes, else with the node's routes within 3 km of it
				var near = (c) => this.map.distance([p.lat, p.lng], c) <= 3000;
				var focus = [[p.lat, p.lng]];
				// 2026-11-27: lines grouped by building, so hovering one violet route lights up every
				// route to that building; a route with no building lights up alone
				var byBuilding = {};
				// lights a building's routes up (bold, full colour, on top) or puts them back
				var light = (key, on) => (byBuilding[key] || []).forEach((l) => {
					if (on) l.setStyle({ weight: 6, opacity: 1 }).bringToFront();
					else l.setStyle(l.nocStyle);
				});
				d.routes.forEach((x) => {
					var style = { color: x.own_site ? accent : violet, weight: x.own_site ? 5 : 2.5, opacity: x.own_site ? 0.95 : 0.55 };
					var lineEl = L.polyline(x.coords, style)
						.bindTooltip(noc_esc(x.title || x.name) + (x.length_m ? ' · ' + Math.round(x.length_m) + ' m' : '') +
							(x.site ? '<br>' + __('Building: {0}', [noc_esc(x.site_name || x.site)]) : ''), { sticky: true })
						.addTo(this.routeLayer);
					lineEl.nocStyle = style;
					var key = x.site || x.name;
					(byBuilding[key] = byBuilding[key] || []).push(lineEl);
					if (!x.own_site) {
						lineEl.on('mouseover', () => light(key, true));
						lineEl.on('mouseout', () => light(key, false));
					}
					if (own ? x.own_site : x.coords.some(near)) focus = focus.concat(x.coords);
				});
				// 2026-11-27: building points (user's request), cyan squares so they differ from the
				// round complaint dots in shape and colour; the complaint's own building is larger with a
				// blue border. Hovering one lights up its routes, like hovering a route.
				(d.buildings || []).forEach((b) => {
					var size = b.own_site ? 16 : 11;
					var pin = L.marker([b.lat, b.lng], {
						pane: 'nocBuildings',
						icon: L.divIcon({
							className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
							html: '<div class="noc-bldg' + (b.own_site ? ' own' : '') + '"></div>',
						}),
					}).bindTooltip('<b>' + noc_esc(b.site_name || b.site) + '</b>' + (b.site_name ? ' · ' + noc_esc(b.site) : '') +
						'<br>' + (b.own_site ? __('This complaint\'s building') + ' · ' : '') + __('{0} fibre routes', [b.routes]))
						.addTo(this.routeLayer);
					pin.on('mouseover', () => light(b.site, true));
					pin.on('mouseout', () => light(b.site, false));
				});
				if (focus.length > 1) this.map.fitBounds(focus, { padding: [50, 50], maxZoom: 17 });
				else this.map.setView([p.lat, p.lng], Math.max(this.map.getZoom(), 15));
				box.html(
					'<b>' + __('Node {0}', [noc_esc(d.node)]) + '</b>: ' +
					(d.routes.length
						? __('{0} fibre routes drawn', [d.routes.length]) + (own ? ', ' + __('{0} to this building (thick blue)', [own]) : '') +
							(d.limited ? ' ' + __('(first 400 only)') : '')
						: __('no KMZ routes uploaded for this node yet')) +
					((d.buildings || []).length ? '; ' + __('{0} buildings shown', [d.buildings.length]) : '') +
					(d.no_pin ? ' ' + __('({0} without a KMZ pin, not shown)', [d.no_pin]) : '') +
					'<div style="margin-top:8px"><button class="btn btn-default btn-xs" data-kmz>' + __('Open node on KMZ Map') + '</button> ' +
					(d.routes.length ? '<button class="btn btn-default btn-xs" data-hide>' + __('Hide routes') + '</button>' : '') + '</div>'
				);
				box.find('[data-kmz]').on('click', () => {
					frappe.route_options = { gis: d.node };
					frappe.set_route('kmz-map');
				});
				box.find('[data-hide]').on('click', () => {
					this.routeLayer.clearLayers();
					box.find('[data-hide]').remove();
				});
			},
		});
	}

	// open past the 4 h limit = red, open = amber, closed in SLA = green, closed late = grey
	markerColour(p) {
		if (p.open) return this.themeColour(p.overdue ? '--ev-bad' : '--ev-warn', p.overdue ? '#dc2626' : '#d97706');
		return p.sla === 'In' ? this.themeColour('--ev-ok', '#15803d') : '#94a3b8';
	}

	renderMap(d) {
		this.makeMap();
		this.markers.clearLayers();
		this.mapPoints = d.points;
		var status = this.mapStatus.get_value() || 'Open';
		var bounds = [];
		this.pinOf = {};
		// closed first, so open complaints are drawn on top
		d.points.slice().sort((a, b) => (a.open === b.open ? 0 : a.open ? 1 : -1)).forEach((p) => {
			var colour = this.markerColour(p);
			var m;
			if (p.open) {
				// 2026-11-26: open = dot + pulsing ring + age badge (user asked for a visual for open complaints)
				m = L.marker([p.lat, p.lng], {
					riseOnHover: true,
					zIndexOffset: p.overdue ? 1000 : 500,
					icon: L.divIcon({
						className: '', iconSize: [18, 18], iconAnchor: [9, 9],
						html: '<div class="noc-pin" style="color:' + colour + '"><span class="ring"></span>' +
							'<span class="dot" style="background:' + colour + '"></span>' +
							(p.age ? '<span class="age" style="background:' + colour + '"><b>' + this.shortAge(p.age) + '</b></span>' : '') + '</div>',
					}),
				});
			} else {
				m = L.circleMarker([p.lat, p.lng], {
					radius: 6, color: '#ffffff', weight: 1.5, fillColor: colour, fillOpacity: 0.9, renderer: this.complaintRenderer,
				});
			}
			m.addTo(this.markers);
			m.bindTooltip(noc_esc(p.name + (p.site ? ' · ' + p.site : '')));
			m.on('click', () => this.showComplaint(p));
			this.pinOf[p.name] = m;
			bounds.push([p.lat, p.lng]);
		});
		if (bounds.length) this.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
		setTimeout(() => this.map.invalidateSize(), 50);

		var scope = status === 'Open' ? __('open complaints') : status === 'Closed' ? __('closed complaints') : __('complaints');
		this.slot('map-sub').text(__('{0} of {1} {2} on the map. Click one to see its details.', [d.points.length, d.total, scope]));
		// 2026-11-26: the key (index) is drawn on the map itself (mapKey); only notes stay below it
		this.mapKey(d.mttr_limit_hours);
		var legend = '';
		if (d.missing) {
			legend += '<span class="warn">' + __('{0} not on the map: no coordinates, LINKID or site pin', [d.missing]) + '</span>';
		}
		if (d.limited) legend += '<span class="warn">' + __('Only the latest 5,000 are loaded: narrow the dates') + '</span>';
		this.slot('map-legend').html(legend);

		// 2026-11-26: open complaints at a glance: counts above the map, list in the side panel
		var open = d.points.filter((p) => p.open).sort((a, b) => (b.age || 0) - (a.age || 0));
		var late = open.filter((p) => p.overdue).length;
		this.slot('map-stats').html(open.length
			? '<span><b style="color:' + this.themeColour('--ev-warn', '#d97706') + '">' + open.length + '</b>' + __('open on the map') + '</span>' +
				'<span><b style="color:' + this.themeColour('--ev-bad', '#dc2626') + '">' + late + '</b>' + __('open over {0} h', [d.mttr_limit_hours]) + '</span>' +
				'<span><b>' + this.shortAge(open[0].age || 0) + '</b>' + __('oldest open') + '</span>'
			: '');
		this.showOpenList(open, d.points.length);
	}

	// Side panel before a complaint is picked: open complaints, oldest first; a click zooms to it
	showOpenList(open, total) {
		this.openList = { open: open, total: total };
		if (!open.length) {
			this.slot('map-side').html('<div class="empty">' +
				(total ? __('Click a complaint on the map to see its details here.') : __('No complaint in this selection has a location yet.')) + '</div>');
			return;
		}
		var rows = open.map((p, i) => '<div class="row" data-i="' + i + '">' +
			'<span class="sw" style="background:' + this.markerColour(p) + '"></span>' +
			'<div><div class="nm">' + noc_esc(p.site || p.link || p.name) + '</div>' +
			'<div class="mt">' + noc_esc([p.name, p.state, p.team || p.vendor].filter(Boolean).join(' · ')) + '</div></div>' +
			'<span class="ag" style="color:' + this.markerColour(p) + '">' + (p.age ? this.shortAge(p.age) : '') + '</span></div>').join('');
		this.slot('map-side').html('<div class="noc-openlist"><div class="h">' + __('Open complaints, oldest first') + '</div>' + rows + '</div>');
		this.slot('map-side').find('.row').on('click', (e) => {
			var p = open[$(e.currentTarget).data('i')];
			this.map.setView([p.lat, p.lng], Math.max(this.map.getZoom(), 15));
			this.showComplaint(p);
		});
	}

	// seconds -> "30d" / "5h" / "40m" for the pin badge
	shortAge(seconds) {
		var m = Math.floor(seconds / 60);
		if (m < 60) return m + 'm';
		var h = Math.floor(m / 60);
		return h < 48 ? h + 'h' : Math.floor(h / 24) + 'd';
	}

	showComplaint(p) {
		var pill = p.open
			? '<span class="noc-pill ' + (p.overdue ? 'late' : 'open') + '">' + noc_esc(p.state) + '</span>'
			: '<span class="noc-pill ' + (p.sla === 'In' ? 'ok' : 'done') + '">' + noc_esc(p.state) + (p.sla ? ' · SLA ' + noc_esc(p.sla) : '') + '</span>';
		var when = (v) => (v ? frappe.datetime.str_to_user(v) : '');
		var rows = [
			[__('Operator'), [p.operator, p.type].filter(Boolean).join(' · ')],
			[__('Received'), when(p.received)],
			[__('Open for'), p.open && p.age ? this.ageText(p.age) : ''],
			[__('Restored'), when(p.closed)],
			[__('MTTR'), p.mttr ? this.hours(p.mttr) + ' h' : ''],
			[__('Link status'), p.link_status],
			[__('Priority'), p.priority],
			[__('Team'), p.team],
			[__('Vendor'), p.vendor],
			[__('Splicer'), p.splicer],
			[__('Rider'), p.rider],
			[__('Area'), p.area],
			[__('Site'), p.site],
			[__('LINKID'), p.linkid],
			[__('Link'), p.link],
			[__('Complaint code'), p.code],
			[__('Unique cut'), p.cut],
			[__('Airtel INC'), p.inc],
			[__('Map position'), p.source],
		].filter((r) => r[1]);
		this.slot('map-side').html(
			'<div class="t">' + noc_esc(p.site || p.link || p.name) + '</div>' +
			'<div class="s">' + noc_esc(p.name) + '</div>' + pill +
			'<dl style="margin-top:12px">' + rows.map((r) => '<dt>' + r[0] + '</dt><dd>' + noc_esc(r[1]) + '</dd>').join('') + '</dl>' +
			// 2026-11-26: node and its fibre routes (filled by drawRoute)
			'<div class="noc-route" data-route>' + __('Loading the node route…') + '</div>' +
			'<button class="btn btn-primary btn-sm" data-open>' + __('Open complaint') + '</button>' +
			// 2026-11-26: back to the list of open complaints
			(this.openList && this.openList.open.length
				? ' <button class="btn btn-default btn-sm" data-list>' + __('All open complaints') + '</button>' : '')
		);
		this.slot('map-side').find('[data-open]').on('click', () => frappe.set_route('Form', 'Complaint Information', p.name));
		this.slot('map-side').find('[data-list]').on('click', () => {
			this.routeLayer.clearLayers();
			this.showOpenList(this.openList.open, this.openList.total);
		});
		this.drawRoute(p);
	}

	// seconds -> "5 h 20 m" / "2 d 3 h"
	ageText(seconds) {
		var h = Math.floor(seconds / 3600);
		return h >= 24 ? Math.floor(h / 24) + ' d ' + (h % 24) + ' h' : h + ' h ' + Math.floor((seconds % 3600) / 60) + ' m';
	}

	control(slot, df, onChange) {
		df.change = onChange;
		return frappe.ui.form.make_control({ parent: this.slot(slot), df: df, render_input: true });
	}

	// ---- complaints overview ---------------------------------------------

	refresh() {
		frappe.call({
			method: NOC_METHOD + 'get_dashboard_data',
			args: { closed_date: this.closedDate.get_value() || frappe.datetime.get_today() },
			callback: (r) => r.message && this.render(r.message),
		});
	}

	render(d) {
		var closedDay = frappe.datetime.str_to_user(d.closed_date);
		var limit = d.mttr_limit_hours;

		this.slot('updated').text(__('Updated {0}', [moment().format('HH:mm')]));
		// 2026-11-26: open cuts on the Live complaints tab, seen from the other tabs too
		this.slot('live-count').text(d.status.unique_cut || '').toggle(!!d.status.unique_cut);
		this.slot('overview').html(
			this.kpis(d, closedDay) +
			'<div class="noc-grid">' +
				this.groupedCard(__('By Area / Vendor'), __('Open cuts'), d.status_description) +
				this.companyCard(d.company) +
				this.flatCard(__('Who Is Working'), __('WIP cuts'), d.working, __('Nobody is on a complaint right now'), { avatar: true }) +
				this.groupedCard(__('Above {0} Hrs MTTR', [limit]), __('Cuts · oldest age'), d.overdue, __('Every open cut is within {0} hours', [limit]), true) +
				this.flatCard(__('Closed on {0}', [closedDay]), __('Cuts closed'), d.closed, __('Nothing closed on this date'), { avatar: true, tone: 'ok' }) +
			'</div>'
		);

		this.slot('overview').find('.noc-kpi.clickable').on('click', (e) => {
			var states = $(e.currentTarget).data('states');
			frappe.set_route('List', 'Complaint Information', states ? { workflow_state: ['in', states] } : {});
		});
	}

	kpis(d, closedDay) {
		// Tile colours are status colours: orange = waiting, purple = in work, red = breached, green = fine.
		var tones = { 'NEED TO ASSIGN': ['orange', 'person'], WIP: ['purple', 'users'] };
		var tiles = [{
			label: __('Open Cuts'), tone: 'blue', icon: 'list', value: d.status.unique_cut,
			hint: __('{0} SR received', [d.status.sr_received]), link: true,
		}];
		d.status.rows.forEach((r) => {
			var tone = tones[r.label] || ['blue', 'list'];
			tiles.push({
				label: this.title(r.label), tone: tone[0], icon: tone[1], value: r.unique_cut,
				hint: __('{0} SR received', [r.sr_received]), link: true, states: r.states,
			});
		});
		tiles.push({
			label: __('Above {0} Hrs MTTR', [d.mttr_limit_hours]), tone: d.overdue.unique_cut ? 'red' : 'green',
			icon: d.overdue.unique_cut ? 'alert' : 'check', value: d.overdue.unique_cut,
			hint: d.overdue.unique_cut ? __('Past MTTR limit') : __('All within limit'),
		});
		tiles.push({ label: __('Closed'), tone: 'green', icon: 'check', value: d.closed.unique_cut, hint: closedDay });
		return '<div class="noc-kpis">' + tiles.map((t) => this.kpi(t)).join('') + '</div>';
	}

	kpi(t) {
		var states = t.states ? " data-states='" + noc_esc(JSON.stringify(t.states)) + "'" : '';
		return '<div class="noc-kpi t-' + t.tone + (t.link ? ' clickable' : '') + '"' + states +
			(t.link ? ' title="' + __('Click to open the list') + '"' : '') + '>' +
			'<div class="noc-kpi-icon">' + NOC_ICONS[t.icon] + '</div><div class="noc-kpi-body">' +
			'<div class="val">' + t.value + '</div>' +
			'<div class="lbl">' + noc_esc(t.label) + '</div>' +
			(t.hint ? '<div class="hint">' + noc_esc(t.hint) + '</div>' : '') + '</div></div>';
	}

	// ---- performance (NOC report workbook) ---------------------------------
	// Date: 2026-11-26

	perfFilters() {
		return {
			from_date: this.perfFrom.get_value() || frappe.datetime.month_start(),
			to_date: this.perfTo.get_value() || frappe.datetime.get_today(),
			team: this.perfTeam.get_value() || '',
		};
	}

	refreshPerf() {
		if (!this.perfFrom || !this.perfTo || !this.stale) return; // controls still being built
		// hidden tab: load when it is opened (refreshTab)
		if (this.tab !== 'perf') { this.stale.perf = true; return; }
		this.stale.perf = false;
		this.slot('perf').html('<div class="noc-loading">' + __('Loading…') + '</div>');
		frappe.call({
			method: NOC_PERF_METHOD,
			args: this.perfFilters(),
			callback: (r) => r.message && this.renderPerf(r.message),
		});
	}

	// Opens a NOC report with the section's dates and team
	openReport(name) {
		var f = this.perfFilters();
		frappe.route_options = { from_date: f.from_date, to_date: f.to_date };
		if (f.team) frappe.route_options.team = f.team;
		frappe.set_route('query-report', name);
	}

	// Quick ranges beside the date filters; the active one is highlighted (none for custom dates)
	perfRanges() {
		// moment, because frappe.datetime.month_start() ignores its argument (always this month)
		var today = frappe.datetime.get_today();
		var ymd = (m) => m.format('YYYY-MM-DD');
		this.ranges = [
			[__('This month'), ymd(moment().startOf('month')), today],
			[__('Last month'), ymd(moment().subtract(1, 'month').startOf('month')), ymd(moment().subtract(1, 'month').endOf('month'))],
			[__('Last 3 months'), ymd(moment().subtract(2, 'month').startOf('month')), today],
		];
		var wrap = this.slot('perf-ranges').empty();
		this.ranges.forEach((r) => {
			$('<button type="button"></button>').text(r[0]).appendTo(wrap).on('click', () => {
				this.perfFrom.set_value(r[1]);
				this.perfTo.set_value(r[2]);
			});
		});
	}

	markRange(f) {
		var buttons = this.slot('perf-ranges').find('button');
		(this.ranges || []).forEach((r, i) => buttons.eq(i).toggleClass('on', r[1] === f.from_date && r[2] === f.to_date));
	}

	// Colours read from the theme, so the chart matches light and dark mode
	themeColour(name, fallback) {
		var v = getComputedStyle(this.root[0]).getPropertyValue(name).trim();
		return v || fallback;
	}

	renderPerf(d) {
		var k = d.kpis;
		var f = this.perfFilters();
		this.markRange(f);
		var range = moment(d.from_date).format('D MMM') + ' – ' + moment(d.to_date).format('D MMM YYYY');
		this.slot('perf-sub').text(range + ', ' + (f.team || __('all teams')) + ', ' + __('own fibre faults'));

		if (!k.received && !k.closed && !k.opening) {
			this.slot('perf').html('<div class="noc-perf-empty"><div class="t">' + __('No complaints in this period') + '</div>' +
				'<div class="s">' + __('Nothing was received or closed between {0}. Pick an earlier period.', [range]) + '</div></div>');
			return;
		}

		this.slot('perf').html(
			this.flowStrip(k) +
			'<div class="noc-grid">' +
				this.card(noc_esc(__('Day by day')), __('SRs received and closed, pending at day end'),
					'<div class="noc-chart" data-slot="perf-chart"></div>', null, null, 'w12') +
				this.card(noc_esc(__('Teams')), __('SRs in this period'), this.teamTable(d.teams), __('No team complaints'), null, 'w8') +
				this.tatCard(d.tat) +
				this.card(noc_esc(__('Busiest days')), __('Two days with the most new cuts, per team and month'),
					this.outageTable(d.outages), __('No cuts in this period'), null, 'w12') +
			'</div>'
		);
		this.perfChart(d.daily);
	}

	// The NOC sheet's own rule as one line: opening + received - closed = pending, then the SLA split
	flowStrip(k) {
		var term = (cls, n, label) => '<div class="noc-term ' + cls + '"><div class="n">' + n + '</div><div class="l">' + label + '</div></div>';
		var op = (s) => '<div class="noc-op">' + s + '</div>';
		var closed = k.in_sla + k.out_sla;
		var inPct = closed ? (100 * k.in_sla / closed) : 0;
		var sla = k.sla_pct == null
			? '<div class="cap">' + __('Nothing closed in this period') + '</div>'
			: '<div class="top"><div class="pct ' + (k.sla_pct >= 80 ? 'good' : 'poor') + '">' + k.sla_pct + '%</div>' +
				'<div class="cap">' + __('closed within 4 hours') + '</div></div>' +
				'<div class="noc-split"><div class="in" style="width:' + inPct + '%"></div><div class="out" style="width:' + (100 - inPct) + '%"></div></div>' +
				'<div class="noc-facts"><span><b>' + k.in_sla + '</b> ' + __('in SLA') + '</span><span><b>' + k.out_sla + '</b> ' + __('out of SLA') + '</span>' +
				'<span>' + __('Average MTTR') + ' <b>' + (k.avg_mttr_hours == null ? '–' : k.avg_mttr_hours + ' h') + '</b></span>' +
				'<span><b>' + k.new_cuts + '</b> ' + __('new cuts') + '</span></div>';
		return '<div class="noc-flow"><div class="noc-eq">' +
			term('', k.opening, __('Opening pending')) + op('+') +
			term('recv', k.received, __('SRs received')) + op('−') +
			term('done', k.closed, __('Team SRs closed')) + op('=') +
			term('left' + (k.pending ? '' : ' zero'), k.pending, __('Pending now')) +
			'</div><div class="noc-sla">' + sla + '</div></div>';
	}

	perfChart(daily) {
		var el = this.slot('perf-chart')[0];
		if (!el || !daily.length) return;
		var long = daily.length > 45;
		var chart = new frappe.Chart(el, {
			type: 'axis-mixed',
			height: 250,
			colors: [this.themeColour('--ev-accent', '#2563eb'), this.themeColour('--ev-ok', '#16a34a'), this.themeColour('--ev-warn', '#d97706')],
			data: {
				// 2026-11-26: day numbers; over several months each month gets a named band (evision.month_bands)
				labels: daily.map((r) => moment(r.date).format('D')),
				datasets: [
					{ name: __('Received'), chartType: 'bar', values: daily.map((r) => r.new) },
					{ name: __('Closed'), chartType: 'bar', values: daily.map((r) => r.closed) },
					{ name: __('Pending'), chartType: 'line', values: daily.map((r) => r.pending) },
				],
			},
			barOptions: { spaceRatio: 0.35 },
			lineOptions: { regionFill: 0, dotSize: long ? 0 : 3 },
			axisOptions: { xIsSeries: 1, xAxisMode: 'tick', yAxisMode: 'span' },
			tooltipOptions: { formatTooltipY: (v) => v },
		});
		evision.month_bands(chart, daily.map((r) => r.date));
	}

	slaCell(inSla, outSla, pct) {
		if (pct == null) return '<td class="zero">–</td>';
		var total = inSla + outSla;
		var w = total ? 100 * inSla / total : 0;
		return '<td><div class="slacell"><div class="noc-split sm"><div class="in" style="width:' + w + '%"></div>' +
			'<div class="out" style="width:' + (100 - w) + '%"></div></div><span class="' + (pct >= 80 ? 'good' : 'poor') + '">' + pct + '%</span></div></td>';
	}

	teamTable(teams) {
		if (!teams.length) return '';
		var cell = (v, cls) => '<td class="' + (v ? (cls || '') : 'zero') + '">' + (v ? v : '–') + '</td>';
		var rows = teams.map((t) => '<tr><td>' + noc_esc(this.title(t.team)) + '</td>' + cell(t.received) + cell(t.closed) +
			cell(t.pending, 'pend') + this.slaCell(t.in_sla, t.out_sla, t.sla_pct) + cell(t.new_cuts) + '</tr>');
		var cols = [__('Team'), __('Received'), __('Closed'), __('Pending'), __('In SLA'), __('New cuts')];
		return '<div class="noc-table-wrap"><table class="noc-table"><thead><tr>' +
			cols.map((c) => '<th>' + c + '</th>').join('') + '</tr></thead><tbody>' + rows.join('') + '</tbody></table></div>';
	}

	// One bar split by bucket, with a legend; faster buckets green, slow ones amber to red
	tatCard(tat) {
		var total = tat.reduce((s, t) => s + t.count, 0);
		if (!total) return this.card(noc_esc(__('Time to close')), '', '', __('No complaints in this period'));
		var colours = {
			'Within 1 Day': this.themeColour('--ev-ok', '#16a34a'), '1 Day': this.themeColour('--ev-accent', '#2563eb'),
			'2 Days': this.themeColour('--ev-warn', '#d97706'), '3+ Days': this.themeColour('--ev-bad', '#dc2626'),
			Open: this.themeColour('--ev-text-5', '#999'),
		};
		var labels = { 'Within 1 Day': __('Same day'), '1 Day': __('Next day'), '2 Days': __('2 days'), '3+ Days': __('3 days or more'), Open: __('Still open') };
		var bar = '<div class="noc-tat-bar">' + tat.filter((t) => t.count).map((t) =>
			'<div title="' + noc_esc(labels[t.bucket] + ': ' + t.count) + '" style="width:' + (100 * t.count / total) + '%;background:' + colours[t.bucket] + '"></div>').join('') + '</div>';
		var rows = tat.map((t) => '<div class="noc-tat-row"><span class="sw" style="background:' + colours[t.bucket] + '"></span>' +
			'<span class="nm">' + noc_esc(labels[t.bucket]) + '</span><span class="ct">' + t.count + '</span>' +
			'<span class="pc">' + Math.round(100 * t.count / total) + '%</span></div>').join('');
		return this.card(noc_esc(__('Time to close')), __('SRs received'), bar + rows, null, total);
	}

	// Grouped by month, busiest day first; rank 1 marked
	outageTable(outages) {
		if (!outages.length) return '';
		var month = null;
		var rows = [];
		outages.forEach((o) => {
			if (o.month !== month) {
				month = o.month;
				rows.push('<tr class="noc-month"><td colspan="8">' + moment(o.month).format('MMMM YYYY') + '</td></tr>');
			}
			rows.push('<tr><td>' + noc_esc(this.title(o.team)) + '</td>' +
				'<td><span class="noc-rank' + (o.rank === 1 ? ' r1' : '') + '">' + o.rank + '</span></td>' +
				'<td>' + moment(o.date).format('ddd D MMM') + '</td><td>' + o.new + '</td><td>' + o.closed + '</td>' +
				'<td class="' + (o.closing ? 'pend' : 'zero') + '">' + (o.closing || '–') + '</td>' +
				'<td class="' + (o.out_sla ? '' : 'zero') + '">' + (o.out_sla ? '<span class="poor">' + o.out_sla + '</span>' : '–') + '</td>' +
				'<td class="wrap">' + noc_esc(this.title(o.who_closed)) + '</td></tr>');
		});
		var cols = [__('Team'), __('Rank'), __('Day'), __('New cuts'), __('Closed'), __('Pending'), __('Out of SLA'), __('Closed by')];
		return '<div class="noc-table-wrap"><table class="noc-table"><thead><tr>' +
			cols.map((c, i) => '<th' + (i === cols.length - 1 ? ' class="left"' : '') + '>' + c + '</th>').join('') +
			'</tr></thead><tbody>' + rows.join('') + '</tbody></table></div>';
	}

	// ---- cards -----------------------------------------------------------

	// 2026-11-26: optional width class (w8 / w12) for the Performance cards
	card(title, sub, body, emptyText, count, width) {
		return '<div class="noc-card' + (width ? ' ' + width : '') + '"><div class="noc-card-head">' +
			'<div class="title">' + title + (count != null ? ' <span class="count">(' + count + ')</span>' : '') + '</div>' +
			'<div class="sub">' + noc_esc(sub) + '</div></div>' +
			(body || '<div class="noc-empty">' + noc_esc(emptyText || __('No open complaints')) + '</div>') + '</div>';
	}

	group(label, total) {
		return '<div class="noc-group"><span>' + noc_esc(this.title(label)) + '</span><span>' + total + '</span></div>';
	}

	// One horizontal bar: bars in a card share one scale so lengths compare across groups.
	bar(label, value, max, opts) {
		opts = opts || {};
		var name = this.title(label);
		var width = max ? Math.round((value / max) * 100) : 0;
		return '<div class="noc-bar" title="' + noc_esc(name + ': ' + value) + '">' +
			'<div class="line"><span class="name">' + (opts.avatar ? noc_avatar(name) : '') + noc_esc(name) + '</span>' +
			'<span class="num">' + (opts.extra || '') + value + '</span></div>' +
			'<div class="track"><div class="fill ' + (opts.tone || '') + '" style="width:' + width + '%"></div></div></div>';
	}

	flatCard(title, sub, f, emptyText, opts) {
		var max = Math.max.apply(null, f.rows.map((r) => r.unique_cut).concat(0));
		var body = f.rows.map((r) => this.bar(r.label, r.unique_cut, max, opts)).join('');
		return this.card(noc_esc(title), sub, body, emptyText, f.unique_cut);
	}

	groupedCard(title, sub, g, emptyText, withAge) {
		var max = 0;
		g.rows.forEach((group) => group.children.forEach((c) => { max = Math.max(max, c.unique_cut); }));
		var body = g.rows.map((group) => {
			return this.group(group.label, group.unique_cut) + group.children.map((c) => {
				return this.bar(c.label, c.unique_cut, max, withAge ? { extra: this.ageChip(c.age), tone: 'warn' } : {});
			}).join('');
		}).join('');
		return this.card(noc_esc(title), sub, body, emptyText, g.unique_cut);
	}

	companyCard(c) {
		var max = 0;
		c.rows.forEach((op) => op.children.forEach((t) => { max = Math.max(max, t.total); }));
		var body = c.rows.map((op) => {
			return this.group(op.label, op.total) + op.children.map((t) => this.bar(t.label, t.total, max)).join('');
		}).join('');
		return this.card(noc_esc(__('By Operator')), __('Open cuts by type'), body, null, c.total);
	}

	// ---- employee / area supervisor monthly sheet -------------------------

	refreshSheet() {
		if (!this.stale) return; // controls still being built
		// 2026-11-26: hidden tab: load when it is opened (refreshTab)
		if (this.tab !== 'sheet') { this.stale.sheet = true; return; }
		this.stale.sheet = false;
		var employee = this.employee.get_value();
		if (!employee) {
			this.slot('sheet').html('<div class="noc-card"><div class="noc-empty">' +
				__('Pick an employee above to see their month') + '</div></div>');
			return;
		}
		frappe.call({
			method: NOC_METHOD + 'get_employee_sheet',
			args: { employee: employee, month: this.sheetMonth.get_value() || frappe.datetime.get_today() },
			callback: (r) => r.message && this.renderSheet(r.message),
		});
	}

	renderSheet(s) {
		var t = s.total;
		var tiles = [
			{ label: __('Field Hours'), tone: 'green', icon: 'pin', value: this.hours(t.field) },
			{ label: __('Home Hours'), tone: 'purple', icon: 'home', value: this.hours(t.home) },
			{ label: __('Office Hours'), tone: 'blue', icon: 'office', value: this.hours(t.office) },
			{ label: __('Other Hours'), tone: 'orange', icon: 'clock', value: this.hours(t.other) },
			{ label: __('Complaints Received'), tone: 'blue', icon: 'list', value: t.complaints },
			{ label: __('Restored'), tone: 'green', icon: 'check', value: t.restored, hint: __('{0} in SLA · {1} out', [t.in_sla, t.out_sla]) },
			{ label: __('Average MTTR'), tone: 'purple', icon: 'clock', value: t.mttr ? this.hours(t.mttr) : '–' },
		].map((tile) => this.kpi(tile)).join('');

		var cell = (value, text, split) => {
			return '<td class="' + (value ? '' : 'zero') + (split ? ' split' : '') + '">' + (value ? text : '–') + '</td>';
		};
		var cells = (r) => {
			return ['field', 'home', 'office', 'other'].map((k, i) => cell(r[k], this.hours(r[k]), i === 0)).join('') +
				['complaints', 'restored', 'in_sla', 'out_sla'].map((k, i) => cell(r[k], r[k], i === 0)).join('') +
				cell(r.mttr, this.hours(r.mttr), true);
		};
		var today = frappe.datetime.get_today();
		var rows = s.rows.map((r) => {
			var day = moment(r.date);
			var cls = (r.date === today ? 'today' : '') + (day.day() === 0 ? ' off' : '');
			return '<tr class="' + cls + '"><td>' + frappe.datetime.str_to_user(r.date) +
				'<span class="day">' + day.format('ddd') + '</span></td>' + cells(r) + '</tr>';
		});
		var cols = [__('Field'), __('Home'), __('Office'), __('Other'), __('Received'), __('Restored'), __('In SLA'), __('Out SLA'), __('MTTR')];
		var splits = [0, 4, 8];

		var table = '<div class="noc-table-wrap"><table class="noc-table"><thead>' +
			'<tr class="groups"><th></th><th colspan="4" class="split">' + __('Hours by Location') + '</th>' +
			'<th colspan="4" class="split">' + __('Complaints') + '</th><th class="split"></th></tr>' +
			'<tr class="cols"><th>' + __('Date') + '</th>' +
			cols.map((c, i) => '<th' + (splits.includes(i) ? ' class="split"' : '') + '>' + c + '</th>').join('') +
			'</tr></thead><tbody>' + rows.join('') +
			'<tr class="total"><td>' + __('Total') + '</td>' + cells(t) + '</tr></tbody></table></div>';

		var person = '<div class="noc-person">' + noc_avatar(s.employee_name, 'lg') + '<div><div class="name">' + noc_esc(s.employee_name) +
			'</div><div class="meta">' + noc_esc(s.month) + '</div></div></div>';
		this.slot('sheet').html('<div class="noc-kpis">' + tiles + '</div>' + this.card(person, __('h:mm per day'), table));
	}

	// ---- helpers ---------------------------------------------------------

	// seconds -> h:mm
	hours(seconds) {
		var minutes = Math.round(seconds / 60);
		return Math.floor(minutes / 60) + ':' + String(minutes % 60).padStart(2, '0');
	}

	ageChip(seconds) {
		var s = Math.floor(seconds);
		var hours = Math.floor(s / 3600);
		var text = hours + 'h ' + String(Math.floor((s % 3600) / 60)).padStart(2, '0') + 'm';
		return '<span class="noc-chip ' + (hours >= 24 ? 'red' : 'orange') + '">' + text + '</span>';
	}

	// "NEED TO ASSIGN" -> "Need To Assign"; codes like WIP / FTTH stay as they are
	title(label) {
		return String(label).split(' ').map((w) => {
			return ['WIP', 'FTTH', 'VI'].includes(w) ? w : w.charAt(0) + w.slice(1).toLowerCase();
		}).join(' ');
	}
}

function noc_esc(v) {
	return frappe.utils.escape_html(v == null ? '' : String(v));
}

// Initials in a coloured circle, same as the Manager Dashboard cards; colour is stable per name.
function noc_avatar(name, size) {
	var s = String(name || '?');
	var initials = s.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');
	var hash = 0;
	for (var i = 0; i < s.length; i++) hash = (hash * 31 + s.charCodeAt(i)) >>> 0;
	return '<span class="noc-avatar' + (size ? ' ' + size : '') + '" style="background:' +
		NOC_AVATAR_PALETTE[hash % NOC_AVATAR_PALETTE.length] + '">' + noc_esc(initials) + '</span>';
}
