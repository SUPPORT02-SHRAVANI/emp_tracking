// EVision Dashboards — Frappe Desk page
// Route: /app/workforce-dashboard/<dashboard>   e.g. /app/workforce-dashboard/hr
//
// One page hosts all role-based dashboards (Employee, Team, HR, Field, Tasks, Claims,
// Performance, Management, Exceptions). The server decides which tabs a user gets and
// whose data they see; this file only draws what workforce_dashboard.py returns.
//
// Every number is clickable: KPI -> list -> record detail -> action (approve, reassign, ...).
// Colours come from the desk theme variables so light and dark mode both work.
//
// Change log:
//   2026-10-09  Desk sidebar renamed from "EVision" to "OverHead Project" (EV_SIDEBAR); the
//               dashboards page now also has its own "Dashboard" desk tile (see setup.py).
//   2026-10-09  OH Project links (New Project, Network Link, Fiber Pulling Team, Teams, Vendors)
//               added to EV_LINKS, so each user sees only the ones they can open.
//   2026-10-09  One menu everywhere: pin_sidebar filters the Dashboard, OverHead Project and
//               Helpdesk NOC menus (OH_SIDEBARS) and keeps whichever is open.

frappe.pages['workforce-dashboard'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('EVision Dashboards'),
		single_column: true,
	});
	wrapper.workforce = new WorkforceDashboard(page);
};

frappe.pages['workforce-dashboard'].on_page_show = function (wrapper) {
	if (wrapper.workforce) wrapper.workforce.show_from_route();
};

var WD_API = 'emp_tracking.emp_tracking.page.workforce_dashboard.workforce_dashboard.';
var WD_REFRESH_MS = 5 * 60 * 1000;

// Same visual language as the Manager Dashboard page (md-*): white cards, slate text,
// coloured top borders on stat tiles, blue underline tabs, uppercase table headers.
var WD_STYLE = [
	'<style>',
	'.wd-root{padding:12px 16px 28px}',
	'@media (max-width:480px){.wd-root{padding:10px 12px 24px}}',
	// tabs
	'.wd-tabs{display:flex;gap:22px;border-bottom:1px solid #e5e7eb;margin:0 16px 4px;flex-wrap:wrap}',
	'.wd-tab{display:flex;align-items:center;gap:6px;padding:10px 2px;font-size:13px;font-weight:700;color:#64748b;cursor:pointer;',
	'  border:0;background:none;border-bottom:2px solid transparent;white-space:nowrap;margin-bottom:-1px}',
	'.wd-tab:hover{color:#334155}',
	'.wd-tab.active{color:#2563eb;border-bottom-color:#2563eb}',
	// page head
	'.wd-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:6px 0 16px}',
	'.wd-head-left{display:flex;align-items:center;gap:12px;min-width:0}',
	'.wd-title{font-size:16px;font-weight:800;color:#0f172a;line-height:1.2}',
	'.wd-sub{font-size:12px;color:#64748b;margin-top:2px}',
	'.wd-head-right{display:flex;align-items:center;gap:8px;flex-wrap:wrap}',
	'.wd-badge{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:700;color:#475569;background:#fff;',
	'  border:1px solid #e2e8f0;border-radius:8px;padding:6px 10px;white-space:nowrap}',
	'.wd-badge .dot{width:7px;height:7px;border-radius:50%;background:#16a34a}',
	// stat tiles
	'.wd-kpis{display:grid;grid-template-columns:repeat(var(--wd-cols,4),minmax(0,1fr));gap:12px;margin-bottom:18px}',
	'.wd-score{display:inline-flex;align-items:center;gap:8px;font-size:11.5px;font-weight:700;color:#475569;background:#fff;',
	'  border:1px solid #e2e8f0;border-radius:8px;padding:4px 10px 4px 4px;cursor:pointer;white-space:nowrap}',
	'.wd-score:hover{border-color:#93c5fd}',
	'.wd-score .ring{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;',
	'  font-size:11px;font-weight:800;color:#fff}',
	'.wd-score .ring.green{background:#16a34a}.wd-score .ring.orange{background:#f97316}.wd-score .ring.red{background:#ef4444}',
	'.wd-score .ring.gray{background:#94a3b8}',
	'.wd-score .m{color:#94a3b8;font-weight:600}',
	'.wd-kpi{background:#fff;border:1px solid #e5e7eb;border-top:3px solid #2563eb;border-radius:12px;padding:13px 14px;',
	'  display:flex;align-items:center;gap:12px;box-shadow:0 1px 2px rgba(15,23,42,.04);transition:box-shadow .15s,transform .15s;min-width:0}',
	'.wd-kpi.clickable{cursor:pointer}',
	'.wd-kpi.clickable:hover{box-shadow:0 4px 10px rgba(15,23,42,.08);transform:translateY(-1px)}',
	'.wd-kpi-icon{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;',
	'  background:#eff6ff;color:#2563eb}',
	'.wd-kpi-body{min-width:0;flex:1}',
	'.wd-kpi .val{font-size:19px;font-weight:800;color:#0f172a;line-height:1.15;font-variant-numeric:tabular-nums;white-space:nowrap;',
	'  overflow:hidden;text-overflow:ellipsis}',
	'.wd-kpi .lbl{font-size:10.5px;color:#64748b;margin-top:2px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
	'.wd-kpi .hint{font-size:10.5px;color:#94a3b8;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
	'.wd-kpi.t-blue{border-top-color:#2563eb}.wd-kpi.t-blue .wd-kpi-icon{background:#eff6ff;color:#2563eb}',
	'.wd-kpi.t-green{border-top-color:#16a34a}.wd-kpi.t-green .wd-kpi-icon{background:#f0fdf4;color:#16a34a}.wd-kpi.t-green .val{color:#16a34a}',
	'.wd-kpi.t-orange{border-top-color:#f97316}.wd-kpi.t-orange .wd-kpi-icon{background:#fff7ed;color:#f97316}.wd-kpi.t-orange .val{color:#f97316}',
	'.wd-kpi.t-red{border-top-color:#ef4444}.wd-kpi.t-red .wd-kpi-icon{background:#fef2f2;color:#ef4444}.wd-kpi.t-red .val{color:#ef4444}',
	'.wd-kpi.t-purple{border-top-color:#7c3aed}.wd-kpi.t-purple .wd-kpi-icon{background:#f5f3ff;color:#7c3aed}.wd-kpi.t-purple .val{color:#7c3aed}',
	'.wd-kpi .val .wd-chip{font-size:12px;vertical-align:middle}',
	// layout + cards
	'.wd-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px;align-items:stretch}',
	'.wd-w-full{grid-column:span 12}.wd-w-two-thirds{grid-column:span 8}.wd-w-half{grid-column:span 6}.wd-w-third{grid-column:span 4}',
	'@media (max-width:1100px){.wd-w-third{grid-column:span 6}.wd-w-two-thirds{grid-column:span 12}}',
	'@media (max-width:767px){.wd-w-two-thirds,.wd-w-half,.wd-w-third{grid-column:span 12}}',
	'.wd-card{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:14px 16px;min-width:0;display:flex;flex-direction:column;',
	'  box-shadow:0 1px 2px rgba(15,23,42,.04)}',
	'.wd-card-head{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:12px;min-height:26px}',
	'.wd-card-head .title{font-size:13.5px;font-weight:800;color:#0f172a}',
	'.wd-card-head .count{color:#64748b;font-weight:700}',
	'.wd-card-head .sub{font-size:11px;color:#94a3b8;font-weight:600;margin-top:2px}',
	'.wd-btn{font-size:11px;font-weight:800;color:#fff;background:#2563eb;border:none;border-radius:6px;padding:5px 10px;cursor:pointer;',
	'  white-space:nowrap;line-height:1.3}',
	'.wd-btn:hover{background:#1d4ed8}',
	'.wd-btn.light{color:#2563eb;background:#eff6ff;border:1px solid #bfdbfe}.wd-btn.light:hover{background:#dbeafe}',
	'.wd-btn.green{background:#16a34a}.wd-btn.green:hover{background:#15803d}',
	'.wd-btn.red{background:#fff;color:#dc2626;border:1px solid #fecaca}.wd-btn.red:hover{background:#fef2f2}',
	'.wd-link{font-size:11.5px;font-weight:700;color:#2563eb;cursor:pointer;white-space:nowrap}',
	'.wd-link:hover{text-decoration:underline}',
	// tables
	'.wd-table-wrap{overflow:auto;max-height:340px;flex:1}',
	'.wd-table{width:100%;border-collapse:collapse}',
	'.wd-table thead th{position:sticky;top:0;background:#fff;text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.03em;',
	'  color:#94a3b8;font-weight:700;padding:6px 8px;border-bottom:1px solid #f1f5f9;white-space:nowrap;z-index:1}',
	'.wd-table tbody td{padding:8px;font-size:12px;color:#334155;border-bottom:1px solid #f8fafc;vertical-align:middle;max-width:260px;',
	'  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
	'.wd-table .num{text-align:right;font-variant-numeric:tabular-nums}',
	'.wd-table tr.clickable{cursor:pointer}',
	'.wd-table tr.clickable:hover td{background:#f8fafc}',
	'.wd-emp-cell{display:flex;align-items:center;gap:8px;min-width:0}',
	'.wd-emp-name{font-weight:700;color:#0f172a;overflow:hidden;text-overflow:ellipsis}',
	'.wd-avatar{width:26px;height:26px;border-radius:13px;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;',
	'  font-size:10.5px;flex-shrink:0}',
	'.wd-avatar.lg{width:42px;height:42px;border-radius:21px;font-size:14px}',
	'.wd-actions-cell{text-align:right;white-space:nowrap}',
	'.wd-actions-cell .wd-btn{margin-left:4px}',
	'.wd-empty{text-align:center;padding:30px 14px;color:#94a3b8;font-size:12.5px}',
	// chips (status pills)
	'.wd-chip{display:inline-block;font-size:10.5px;font-weight:700;padding:3px 9px;border-radius:20px;white-space:nowrap;line-height:1.4}',
	'.wd-chip.green{color:#15803d;background:#dcfce7}.wd-chip.red{color:#b91c1c;background:#fee2e2}',
	'.wd-chip.orange{color:#c2410c;background:#ffedd5}.wd-chip.blue{color:#1d4ed8;background:#dbeafe}',
	'.wd-chip.purple{color:#6d28d9;background:#ede9fe}.wd-chip.gray{color:#475569;background:#f1f5f9}',
	// bars
	'.wd-bar{padding:6px 0;border-bottom:1px solid #f8fafc}',
	'.wd-bar:last-child{border-bottom:0}',
	'.wd-bar.clickable{cursor:pointer}',
	'.wd-bar .line{display:flex;justify-content:space-between;gap:12px;font-size:12.5px;font-weight:600;color:#334155;margin-bottom:5px}',
	'.wd-bar .line .name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
	'.wd-bar .line .num{font-weight:800;color:#0f172a;font-variant-numeric:tabular-nums;white-space:nowrap}',
	'.wd-bar .track{height:7px;border-radius:4px;background:#f1f5f9}',
	'.wd-bar .fill{height:7px;border-radius:4px;min-width:3px;background:#2563eb}',
	'.wd-bar .fill.ok{background:#16a34a}.wd-bar .fill.warn{background:#f97316}.wd-bar .fill.bad{background:#ef4444}',
	'.wd-bar.clickable:hover .line .name{color:#2563eb}',
	// stats
	'.wd-stats{display:grid;grid-template-columns:1fr 1fr;gap:10px}',
	'.wd-stat{background:#f8fafc;border:1px solid #f1f5f9;border-radius:10px;padding:10px 12px;min-width:0}',
	'.wd-stat.clickable{cursor:pointer}.wd-stat.clickable:hover{border-color:#93c5fd;background:#eff6ff}',
	'.wd-stat .v{font-size:16px;font-weight:800;color:#0f172a;font-variant-numeric:tabular-nums;line-height:1.2}',
	'.wd-stat .l{font-size:9.5px;color:#64748b;font-weight:700;margin-top:4px;text-transform:uppercase;letter-spacing:.02em;',
	'  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
	// timeline
	'.wd-timeline{overflow-y:auto;max-height:340px}',
	'.wd-tl-row{display:flex;gap:10px;padding:10px 0;border-bottom:1px solid #f1f5f9}',
	'.wd-tl-row:last-child{border-bottom:none}',
	'.wd-tl-mark{width:12px;height:12px;border-radius:50%;flex-shrink:0;margin-top:3px;border:2px solid #fff;box-shadow:0 0 0 1px #e5e7eb;background:#94a3b8}',
	'.wd-tl-mark.ok{background:#16a34a}.wd-tl-mark.info{background:#2563eb}.wd-tl-mark.neutral{background:#dc2626}',
	'.wd-tl-top{display:flex;justify-content:space-between;gap:8px}',
	'.wd-tl-title{font-size:12.5px;font-weight:800;color:#0f172a}',
	'.wd-tl-time{font-size:11px;font-weight:700;color:#64748b;white-space:nowrap}',
	'.wd-tl-sub{font-size:11px;color:#94a3b8;margin-top:3px}',
	// map + charts
	'.wd-map{height:360px;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;background:#f8fafc;z-index:0}',
	'.wd-map-list{font-size:12.5px}',
	'.wd-map-label{background:#fff;padding:1px 7px;border-radius:6px;font-size:11px;font-weight:700;box-shadow:0 1px 3px rgba(0,0,0,.3);',
	'  border:0;color:#0f172a}',
	'.wd-chart{min-height:230px}',
	'.wd-message{padding:40px 16px;text-align:center;color:#64748b;font-size:13px}',
	'.wd-loading{padding:60px 0;text-align:center;color:#94a3b8;font-size:13px}',
	'.wd-updated{color:#94a3b8;font-size:11px;text-align:right;margin-top:14px}',
	'.wd-print-head{display:none}',
	// drill-down + detail dialog
	'.wd-dlg-bar{display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap}',
	'.wd-dlg-bar input{max-width:300px;border:1px solid #e2e8f0;border-radius:10px;padding:7px 12px;font-size:12.5px;background:#f8fafc}',
	'.wd-dlg-bar .count{font-size:12px;font-weight:700;color:#64748b;margin-left:auto}',
	'.wd-dlg .wd-table-wrap{max-height:60vh}',
	'.wd-detail-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:14px}',
	'.wd-detail-head h4{margin:0 0 4px;font-size:16px;font-weight:800;color:#0f172a}',
	'.wd-detail-head .sub{font-size:12px;color:#64748b}',
	'.wd-fields{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px 18px;margin-bottom:14px}',
	'.wd-field .label{font-size:9.5px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.02em}',
	'.wd-field .value{font-size:13px;font-weight:600;color:#0f172a;word-break:break-word;margin-top:2px}',
	'.wd-field.wide{grid-column:1/-1}',
	'.wd-person{display:flex;gap:12px;align-items:center;padding:12px 14px;border-radius:12px;background:#f8fafc;border:1px solid #f1f5f9;margin-bottom:14px}',
	'.wd-person .name{font-weight:800;font-size:13.5px;color:#0f172a}',
	'.wd-person .meta{font-size:11.5px;color:#64748b;margin-top:2px}',
	'.wd-related{border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px;margin-bottom:12px}',
	'.wd-related .title{font-size:12px;font-weight:800;color:#0f172a;margin-bottom:10px;display:flex;justify-content:space-between}',
	'.wd-detail-actions{display:flex;gap:8px;flex-wrap:wrap;padding-top:14px;border-top:1px solid #f1f5f9}',
	'.wd-detail-actions .wd-btn{padding:8px 14px;font-size:12px}',
	'.wd-mini-map{height:200px;border-radius:12px;border:1px solid #e5e7eb;margin-bottom:14px;z-index:0}',
	'@media print{',
	'  .navbar,.page-head,.page-form,.wd-tabs,.wd-no-print,.wd-link,.wd-btn,.wd-actions-cell,.layout-side-section,.footer-powered{display:none!important}',
	'  .wd-print-head{display:block;margin-bottom:12px}',
	'  .wd-table-wrap{max-height:none;overflow:visible}',
	'  .wd-card,.wd-kpi{break-inside:avoid}',
	'  .wd-grid{display:block}.wd-grid>.wd-card{margin-bottom:12px}',
	'}',
	'</style>',
].join('');

var AVATAR_PALETTE = ['#2563eb', '#0d9488', '#9333ea', '#ea580c', '#0891b2', '#4f46e5', '#be185d', '#16803d'];

// Inline icons, currentColor so the tile colour drives them.
var WD_ICONS = {
	person: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
	users: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
	clock: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
	route: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h7a2 2 0 0 0 2-2v-1a2 2 0 0 0-2-2H9a2 2 0 0 1-2-2v-1a2 2 0 0 1 2-2h7"/></svg>',
	money: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4h12M6 9h12M14 20 7 13h2a4 4 0 0 0 0-8"/></svg>',
	chart: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
	star: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/></svg>',
	list: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 6h11M9 12h11M9 18h11"/><path d="m4 6 1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"/></svg>',
	alert: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
	calendar: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/></svg>',
	pin: '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/></svg>',
};

var WD_TAB_ICONS = {
	employee: '👤', team: '👥', hr: '🗂', field: '📍', tasks: '✅', claims: '⛽', performance: '📈', management: '📊', exceptions: '⚠',
};

// Status text -> indicator colour. Anything unknown is gray.
var WD_COLORS = {
	green: ['Present', 'Completed', 'Approved', 'In Office', 'Active'],
	blue: ['In Field', 'In Progress', 'Working', 'Leave', 'Medium', 'Work From Home', 'halted', 'background'],
	orange: ['On Leave', 'Pending', 'Open', 'Half Day', 'Not Checked In', 'Pending Review', 'Regularization', 'Low GPS accuracy',
		'GPS signal gap', 'Manual location', 'manual'],
	red: ['Absent', 'Rejected', 'Delayed', 'Overdue', 'High', 'Urgent', 'Unrealistic speed', 'Cancelled'],
	purple: ['Petrol Claim'],
	gray: ['Holiday', 'Checked Out', 'Draft', 'Low', 'Template'],
};
var WD_STATUS_COLOR = {};
Object.keys(WD_COLORS).forEach(function (c) {
	WD_COLORS[c].forEach(function (s) { WD_STATUS_COLOR[s] = c; });
});

class WorkforceDashboard {
	constructor(page) {
		this.page = page;
		this.current = null;
		this.data = null;
		this.charts = [];
		this.maps = [];
		this.request = 0;

		$(WD_STYLE).appendTo(page.main);
		this.$tabs = $('<div class="wd-tabs wd-no-print"></div>').appendTo(page.main);
		this.$body = $('<div class="wd-root"><div class="wd-loading">' + __('Loading…') + '</div></div>').appendTo(page.main);

		page.set_primary_action(__('Refresh'), () => this.refresh(), 'refresh');
		page.add_inner_button(__('Excel'), () => this.export_excel(), __('Export'));
		page.add_inner_button(__('PDF / Print'), () => this.print(), __('Export'));

		frappe.call({ method: WD_API + 'get_boot' }).then((r) => {
			this.boot = r.message;
			this.make_tabs();
			this.make_filters();
			this.pin_sidebar();
			this.show_from_route();
		});

		frappe.router.on('change', () => {
			if (frappe.get_route()[0] === 'workforce-dashboard') this.show_from_route();
		});
		this.timer = setInterval(() => {
			if (frappe.get_route()[0] === 'workforce-dashboard' && !document.hidden) this.refresh(true);
		}, WD_REFRESH_MS);
	}

	// ---- navigation ------------------------------------------------------

	allowed(key) {
		return this.boot && this.boot.dashboards.some((d) => d.key === key);
	}

	// The desk picks a sidebar from the URL; /workforce-dashboard/<tab> matches none, so it would keep
	// whatever sidebar was last open (often HR). Always show our own EVision sidebar here, trimmed to
	// the links this user can actually open.
	// 2026-10-09: all three EVisions menus (OH_SIDEBARS) carry the same links. Filter the workforce
	// links in each, and keep whichever of them is open instead of always switching to one.
	pin_sidebar() {
		var sidebar = frappe.app && frappe.app.sidebar;
		var all = frappe.boot.workspace_sidebar_item || {};
		if (!sidebar || !all[EV_SIDEBAR.toLowerCase()] || !this.boot) return;
		var changed = false;
		OH_SIDEBARS.forEach((name) => {
			var data = all[name.toLowerCase()];
			if (data && !data.wd_filtered) {
				data.items = ev_menu_items(data.items, this.boot.scope);
				data.wd_filtered = true;
				changed = true;
			}
		});
		var current = sidebar.sidebar_title;
		var keep = OH_SIDEBARS.includes(current) && all[(current || '').toLowerCase()];
		// Rebuild only when the links were just filtered or another app's menu is open.
		if (changed || !keep) sidebar.setup(keep ? current : EV_SIDEBAR);
	}

	show_from_route() {
		setTimeout(() => this.pin_sidebar(), 0);
		if (!this.boot) return;
		var key = frappe.get_route()[1];
		if (frappe.route_options && frappe.route_options.employee && this.filters.employee) {
			this.filters.employee.set_value(frappe.route_options.employee);
			frappe.route_options = null;
		}
		if (!key || !this.allowed(key)) {
			if (key) frappe.show_alert({ message: __('You do not have access to that dashboard'), indicator: 'orange' });
			key = this.boot.landing;
			frappe.set_route('workforce-dashboard', key);
			return;
		}
		if (key !== this.current) this.open(key);
	}

	make_tabs() {
		this.$tabs.empty();
		if (this.boot.dashboards.length < 2) this.$tabs.hide();
		this.boot.dashboards.forEach((d) => {
			$('<button class="wd-tab"></button>')
				.html('<span>' + (WD_TAB_ICONS[d.key] || '') + '</span><span>' + esc(d.label) + '</span>')
				.attr('data-key', d.key)
				.on('click', () => frappe.set_route('workforce-dashboard', d.key))
				.appendTo(this.$tabs);
		});
	}

	open(key) {
		this.current = key;
		this.$tabs.find('.wd-tab').removeClass('active').filter('[data-key="' + key + '"]').addClass('active');
		var label = this.boot.dashboards.find((d) => d.key === key).label;
		this.page.set_title(label + ' ' + __('Dashboard'));
		var today_first = this.boot.today_first.includes(key);
		this.filters.period.set_value(today_first ? 'Today' : 'Last 30 Days');
		this.toggle_filters();
		this.queue_refresh();
	}

	// Filter changes arrive one control at a time (and asynchronously); fold them into one request.
	queue_refresh() {
		clearTimeout(this.pending);
		this.pending = setTimeout(() => this.refresh(), 150);
	}

	// ---- filters ---------------------------------------------------------

	make_filters() {
		var b = this.boot;
		var change = () => this.queue_refresh();
		var blank = (opts) => [{ value: '', label: '' }].concat(opts);
		this.filters = {};
		this.filters.period = this.page.add_field({
			fieldname: 'period', label: __('Period'), fieldtype: 'Select',
			options: b.periods.map((p) => ({ value: p, label: __(p) })), default: 'Today',
			change: () => { this.toggle_filters(); change(); },
		});
		this.filters.from_date = this.page.add_field({
			fieldname: 'from_date', label: __('From'), fieldtype: 'Date', default: frappe.datetime.month_start(), change: change,
		});
		this.filters.to_date = this.page.add_field({
			fieldname: 'to_date', label: __('To'), fieldtype: 'Date', default: frappe.datetime.get_today(), change: change,
		});
		this.filters.department = this.page.add_field({
			fieldname: 'department', label: __('Department'), fieldtype: 'Select',
			options: blank(b.departments.map((d) => ({ value: d, label: d }))), change: change,
		});
		this.filters.team = this.page.add_field({
			fieldname: 'team', label: __('Team'), fieldtype: 'Select', options: blank(b.teams), change: change,
		});
		this.filters.employee = this.page.add_field({
			fieldname: 'employee', label: __('Employee'), fieldtype: 'Select', options: blank(b.employees), change: change,
		});
		this.filters.category = this.page.add_field({
			fieldname: 'category', label: __('Work Type'), fieldtype: 'Select',
			options: [{ value: '', label: __('Project + Maintenance') }, { value: 'Project', label: __('Project') }, { value: 'Maintenance', label: __('Maintenance') }],
			change: change,
		});
		this.filters.project = this.page.add_field({
			fieldname: 'project', label: __('Project'), fieldtype: 'Select', options: blank(b.projects), change: change,
		});
	}

	toggle_filters() {
		var custom = this.filters.period.get_value() === 'Custom';
		var self_only = this.boot.scope === 'self';
		var personal = this.current === 'employee';
		this.filters.from_date.$wrapper.toggle(custom);
		this.filters.to_date.$wrapper.toggle(custom);
		this.filters.department.$wrapper.toggle(!self_only && !personal && this.boot.departments.length > 1);
		this.filters.team.$wrapper.toggle(!self_only && !personal && this.boot.teams.length > 0);
		this.filters.employee.$wrapper.toggle(!self_only);
		this.filters.project.$wrapper.toggle(this.boot.projects.length > 0);
	}

	get_filters() {
		var out = {};
		Object.keys(this.filters).forEach((k) => {
			var v = this.filters[k].get_value();
			if (v) out[k] = v;
		});
		if (out.period !== 'Custom') { delete out.from_date; delete out.to_date; }
		return out;
	}

	// ---- data ------------------------------------------------------------

	refresh(silent) {
		if (!this.current) return;
		var id = ++this.request;
		var key = this.current;
		if (!silent) this.$body.html('<div class="wd-loading">' + __('Loading…') + '</div>');
		frappe.call({
			method: WD_API + 'get_dashboard',
			args: { dashboard: key, filters: this.get_filters() },
			error: () => this.$body.html('<div class="wd-message">' + __('Could not load this dashboard.') + '</div>'),
		}).then((r) => {
			if (id !== this.request || !r.message) return;
			this.data = r.message;
			this.render(r.message);
		});
	}

	// ---- rendering -------------------------------------------------------

	render(d) {
		this.destroy_widgets();
		var m = d.meta;
		var label = this.boot.dashboards.find((x) => x.key === this.current).label;
		var period = m.from_date === m.to_date
			? frappe.datetime.str_to_user(m.from_date)
			: frappe.datetime.str_to_user(m.from_date) + ' – ' + frappe.datetime.str_to_user(m.to_date);
		var updated = frappe.datetime.str_to_user(m.updated_at);


		var html = '<div class="wd-print-head"><h3>' + esc(label) + ' ' + __('Dashboard') + '</h3><div>' +
			esc(__(m.period)) + ': ' + esc(period) + ' · ' + __('Generated {0} by {1}', [esc(updated), esc(this.boot.user)]) + '</div></div>';

		var personal = this.current === 'employee' && d.title;
		html += '<div class="wd-head"><div class="wd-head-left">' +
			(personal ? avatar(d.title, 'lg') : '') +
			'<div><div class="wd-title">' + esc(personal ? d.title : label + ' ' + __('Dashboard')) + '</div>' +
			'<div class="wd-sub">' + esc(d.subtitle || __('{0} employee(s) in view', [m.employees])) + '</div></div></div>' +
			'<div class="wd-head-right">' + score_badge(d.score) +
			'<span class="wd-badge">' + WD_ICONS.calendar + esc(__(m.period)) + ' · ' + esc(period) + '</span>' +
			'<span class="wd-badge"><span class="dot"></span>' + __('Updated {0}', [moment(m.updated_at).format('HH:mm')]) + '</span>' +
			'</div></div>';

		if (d.message) {
			this.$body.html(html + '<div class="wd-card wd-message">' + esc(d.message) + '</div>');
			return;
		}

		html += '<div class="wd-kpis">' + (d.kpis || []).map((k, i) => this.kpi_html(k, i)).join('') + '</div>';
		html += '<div class="wd-grid">' + (d.sections || []).map((s, i) => this.section_html(s, i)).join('') + '</div>';
		html += '<div class="wd-updated">' + __('Last updated {0}', [esc(updated)]) + ' · ' + __('auto-refreshes every 5 minutes') + '</div>';
		this.$body.html(html);

		this.layout_kpis();
		this.bind(d);
		(d.sections || []).forEach((s, i) => {
			if (s.type === 'chart') this.draw_chart(s, i);
			if (s.type === 'map') this.draw_map(s, i);
		});
	}

	// Pick a column count that splits the tiles into even rows for this width, then stretch the
	// last tile over any gap left in the final row, so no tile ever sits alone on a line.
	layout_kpis() {
		var $grid = this.$body.find('.wd-kpis');
		var $tiles = $grid.children('.wd-kpi');
		var n = $tiles.length;
		if (!n) return;
		var fit = Math.max(1, Math.floor(($grid.width() + 12) / (180 + 12)));
		var rows = Math.ceil(n / Math.min(fit, n));
		var cols = Math.ceil(n / rows);
		$grid.css('--wd-cols', cols);
		$tiles.css('grid-column', '');
		var gap = cols * rows - n;
		if (gap > 0) $tiles.last().css('grid-column', 'span ' + (gap + 1));
		if (!this.resize_bound) {
			this.resize_bound = true;
			$(window).on('resize', frappe.utils.debounce(() => this.layout_kpis(), 150));
		}
	}

	kpi_html(k, i) {
		var tone = { ok: 't-green', warn: 't-orange', bad: 't-red' }[k.tone] ||
			(k.fmt === 'km' || k.fmt === 'currency' ? 't-purple' : 't-blue');
		var icon = kpi_icon(k);
		return '<div class="wd-kpi ' + tone + (k.drill ? ' clickable' : '') + '" data-kpi="' + i + '"' +
			(k.drill ? ' title="' + __('Click for details') + '"' : '') + '>' +
			'<div class="wd-kpi-icon">' + icon + '</div><div class="wd-kpi-body">' +
			'<div class="val">' + fmt(k.value, k.fmt) + '</div>' +
			'<div class="lbl" title="' + esc(k.label) + '">' + esc(k.label) + '</div>' +
			(k.hint ? '<div class="hint" title="' + esc(k.hint) + '">' + esc(k.hint) + '</div>' : '') +
			'</div></div>';
	}

	card(s, i, body, extra_head, count) {
		return '<div class="wd-card wd-w-' + (s.width || 'full') + '" data-section="' + i + '"><div class="wd-card-head"><div>' +
			'<div class="title">' + esc(s.title) + (count != null ? ' <span class="count">(' + count + ')</span>' : '') + '</div>' +
			(s.subtitle ? '<div class="sub">' + esc(s.subtitle) + '</div>' : '') +
			'</div>' + (extra_head || '') + '</div>' + body + '</div>';
	}

	section_html(s, i) {
		if (s.type === 'table') {
			var more = s.drill && s.total
				? '<button class="wd-btn light" data-drill="' + esc(s.drill) + '">' + (s.total > s.rows.length ? __('View all') : __('Open list')) + ' ›</button>'
				: '';
			return this.card(s, i, table_html(s.columns, s.rows, s.empty, s.inline_actions), more, s.total);
		}
		if (s.type === 'chart') {
			var has = s.datasets.some((ds) => ds.values.some((v) => v));
			return this.card(s, i, has ? '<div class="wd-chart" id="wd-chart-' + i + '"></div>' : '<div class="wd-empty">' + __('No data for this period') + '</div>');
		}
		if (s.type === 'bars') {
			var max = Math.max.apply(null, s.items.map((x) => Math.abs(x.value || 0)).concat([1]));
			var body = s.items.length ? s.items.map((x, j) => {
				var w = Math.max(2, Math.round(100 * Math.abs(x.value || 0) / max));
				return '<div class="wd-bar' + (x.drill ? ' clickable' : '') + '"' + (x.drill ? ' data-drill="' + esc(x.drill) + '"' : '') + '>' +
					'<div class="line"><span class="name">' + esc(x.label) + '</span><span class="num">' + fmt(x.value, s.fmt) + '</span></div>' +
					'<div class="track"><div class="fill ' + (x.tone || '') + '" style="width:' + w + '%"></div></div></div>';
			}).join('') : '<div class="wd-empty">' + __('Nothing to show') + '</div>';
			return this.card(s, i, body);
		}
		if (s.type === 'stats') {
			return this.card(s, i, '<div class="wd-stats">' + s.items.map((x) =>
				'<div class="wd-stat' + (x.drill ? ' clickable' : '') + '"' + (x.drill ? ' data-drill="' + esc(x.drill) + '"' : '') + '>' +
				'<div class="v">' + fmt(x.value, x.fmt) + '</div><div class="l" title="' + esc(x.label) + '">' + esc(x.label) + '</div></div>'
			).join('') + '</div>');
		}
		if (s.type === 'timeline') {
			var items = s.items.length ? '<div class="wd-timeline">' + s.items.map((x) =>
				'<div class="wd-tl-row"><span class="wd-tl-mark ' + (x.tone || '') + '"></span><div style="flex:1;min-width:0">' +
				'<div class="wd-tl-top"><span class="wd-tl-title">' + esc(x.label) + '</span><span class="wd-tl-time">' + fmt(x.time, 'time') + '</span></div>' +
				(x.detail ? '<div class="wd-tl-sub">' + esc(x.detail) + '</div>' : '') + '</div></div>'
			).join('') + '</div>' : '<div class="wd-empty">' + __('No activity yet today') + '</div>';
			return this.card(s, i, items);
		}
		if (s.type === 'compare') {
			var rows = s.rows.map((r) => '<tr><td>' + esc(__(r.metric)) + '</td><td class="num">' + fmt(r.today, r.fmt) +
				'</td><td class="num">' + fmt(r.month, r.fmt) + '</td><td class="num">' + fmt(r.period, r.fmt) + '</td></tr>').join('');
			return this.card(s, i, '<div class="wd-table-wrap"><table class="wd-table"><thead><tr><th></th>' +
				s.columns.map((c) => '<th class="num">' + esc(c) + '</th>').join('') + '</tr></thead><tbody>' + rows + '</tbody></table></div>');
		}
		if (s.type === 'map') {
			var body2 = s.points.length
				? '<div class="wd-map" id="wd-map-' + i + '"></div>'
				: '<div class="wd-empty">' + __('No GPS locations received yet') + '</div>';
			return this.card(s, i, body2, s.points.length ? '<span class="wd-badge">' + WD_ICONS.pin + __('{0} located', [s.points.length]) + '</span>' : '');
		}
		return '';
	}

	bind(d) {
		var me = this;
		this.$body.find('.wd-kpi.clickable').on('click', function () {
			var k = d.kpis[$(this).data('kpi')];
			me.open_drill(k.drill, k.label);
		});
		this.$body.find('[data-drill]').on('click', function (e) {
			e.stopPropagation();
			me.open_drill($(this).attr('data-drill'));
		});
		this.$body.find('.wd-card[data-section]').each(function () {
			var s = d.sections[$(this).data('section')];
			if (s.type === 'table') me.bind_table($(this), s.rows, () => me.refresh(true));
		});
	}

	bind_table($el, rows, after_action, dialog) {
		var me = this;
		$el.find('tr[data-row]').on('click', function () {
			var row = rows[$(this).data('row')];
			if (row._drill) me.open_drill(row._drill);
			else if (row._doctype) me.open_detail(row._doctype, row._name, dialog);
		});
		$el.find('[data-action]').on('click', function (e) {
			e.stopPropagation();
			var row = rows[$(this).closest('tr').data('row')];
			me.run_action(row._doctype, row._name, { action: $(this).data('action'), input: $(this).data('action') === 'reject' ? 'text' : null }, after_action);
		});
	}

	destroy_widgets() {
		this.maps.forEach((m) => m.remove());
		this.maps = [];
		this.charts = [];
	}

	draw_chart(s, i) {
		var el = document.getElementById('wd-chart-' + i);
		if (!el) return;
		var type = s.chart_type;
		var opts = {
			data: { labels: s.labels, datasets: s.datasets },
			type: type,
			height: 240,
			colors: s.colors || ['#2563eb', '#ef4444', '#f97316', '#16a34a', '#7c3aed'],
			axisOptions: { xIsSeries: true, xAxisMode: 'tick' },
			barOptions: { stacked: s.stacked ? 1 : 0, spaceRatio: 0.4 },
			lineOptions: { regionFill: 0, hideDots: s.labels.length > 20 ? 1 : 0 },
			tooltipOptions: {},
		};
		if (type === 'donut' || type === 'pie') {
			opts.colors = ['#16a34a', '#2563eb', '#f97316', '#ef4444'];
			opts.maxSlices = 6;
		}
		this.charts.push(new frappe.Chart(el, opts));
	}

	draw_map(s, i) {
		var el = document.getElementById('wd-map-' + i);
		if (!el) return;
		if (!window.L) {
			$(el).replaceWith('<div class="wd-map-list">' + s.points.map((p) => '<div>' + esc(p.employee_name) + ' — ' +
				'<a target="_blank" href="https://www.openstreetmap.org/?mlat=' + p.lat + '&mlon=' + p.lng + '#map=15/' + p.lat + '/' + p.lng + '">' +
				p.lat.toFixed(5) + ', ' + p.lng.toFixed(5) + '</a> · ' + fmt(p.time, 'ago') + '</div>').join('') + '</div>');
			return;
		}
		var map = L.map(el, { scrollWheelZoom: false });
		L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
			maxZoom: 19, attribution: '&copy; OpenStreetMap',
		}).addTo(map);
		var palette = AVATAR_PALETTE;
		var bounds = [];
		s.points.forEach((p, j) => {
			var color = palette[j % palette.length];
			if (p.path && p.path.length > 1) {
				L.polyline(p.path, { color: color, weight: 3, opacity: 0.7 }).addTo(map);
				bounds = bounds.concat(p.path);
			}
			L.circleMarker([p.lat, p.lng], { radius: 8, color: '#fff', weight: 2, fillColor: color, fillOpacity: 1 })
				.bindPopup('<b>' + esc(p.employee_name) + '</b><br>' + esc(p.status || '') + '<br>' + (p.task ? esc(p.task) + '<br>' : '') +
					'<span class="text-muted">' + __('Updated') + ' ' + esc(frappe.datetime.str_to_user(p.time)) + '</span>')
				.bindTooltip(esc(p.employee_name), { permanent: s.points.length <= 6, direction: 'top', offset: [0, -8], className: 'wd-map-label' })
				.addTo(map);
			bounds.push([p.lat, p.lng]);
		});
		map.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });
		setTimeout(() => map.invalidateSize(), 200);
		this.maps.push(map);
	}

	// ---- drill-down ------------------------------------------------------

	open_drill(key, title) {
		var dialog = new frappe.ui.Dialog({ title: title || __('Details'), size: 'extra-large', fields: [{ fieldtype: 'HTML', fieldname: 'body' }] });
		var $b = dialog.fields_dict.body.$wrapper.addClass('wd-dlg').html('<div class="wd-loading">' + __('Loading…') + '</div>');
		dialog.show();
		var load = () => frappe.call({
			method: WD_API + 'get_drilldown',
			args: { dashboard: this.current, key: key, filters: this.get_filters() },
		}).then((r) => {
			var d = r.message;
			dialog.set_title(d.title);
			dialog.wd_list = () => this.render_list(dialog, $b, d, key, load);
			dialog.wd_list();
		});
		dialog.wd_reload = () => { load(); this.refresh(true); };
		load();
	}

	render_list(dialog, $b, d, key, reload) {
		$b.html('<div class="wd-dlg-bar"><input type="search" placeholder="' + __('Search this list') + '">' +
			'<button class="wd-btn light wd-export">⬇ ' + __('Export to Excel') + '</button>' +
			'<span class="count"></span></div><div class="wd-list"></div>');
		var draw = (rows) => {
			$b.find('.count').text(__('{0} record(s)', [rows.length]));
			var $list = $b.find('.wd-list').html(table_html(d.columns, rows, __('Nothing here'), rows.some((r) => inline_doctype(r._doctype))));
			this.bind_table($list, rows, () => dialog.wd_reload(), dialog);
		};
		draw(d.rows);
		$b.find('input').on('input', frappe.utils.debounce(function () {
			var q = $(this).val().toLowerCase();
			draw(!q ? d.rows : d.rows.filter((r) => d.columns.some((c) => String(r[c.key] == null ? '' : r[c.key]).toLowerCase().includes(q))));
		}, 200));
		$b.find('.wd-export').on('click', () => this.export_excel(key));
	}

	// ---- record detail + actions -----------------------------------------

	open_detail(doctype, name, dialog) {
		if (!dialog) {
			dialog = new frappe.ui.Dialog({ title: __(doctype), size: 'large', fields: [{ fieldtype: 'HTML', fieldname: 'body' }] });
			dialog.show();
			dialog.wd_reload = () => { this.open_detail(doctype, name, dialog); this.refresh(true); };
		}
		var $b = dialog.fields_dict.body.$wrapper;
		var back = dialog.wd_list;
		$b.html('<div class="wd-loading">' + __('Loading…') + '</div>');
		frappe.call({ method: WD_API + 'get_detail', args: { doctype: doctype, name: name } }).then((r) => {
			var d = r.message;
			var html = '';
			if (back) html += '<div class="wd-link wd-back" style="margin-bottom:10px">‹ ' + __('Back to list') + '</div>';
			html += '<div class="wd-detail-head"><div><h4>' + esc(d.title) + '</h4><div class="sub">' + esc(__(d.doctype)) + ' · ' + esc(d.name) + '</div></div>' +
				(d.status ? fmt(d.status, 'status') : '') + '</div>';
			if (d.employee) {
				var e = d.employee;
				html += '<div class="wd-person">' + avatar(e.employee_name, 'lg') + '<div>' +
					'<div class="name">' + esc(e.employee_name) + ' <span style="color:#94a3b8;font-weight:600">' + esc(e.name) + '</span></div>' +
					'<div class="meta">' + [e.designation, e.department, e.reports_to_name ? __('Reports to {0}', [e.reports_to_name]) : null, e.cell_number]
						.filter(Boolean).map(esc).join(' · ') + '</div>' +
					'<div class="meta"><span class="wd-link wd-emp-dash">' + __('Open employee dashboard') + ' ›</span></div></div></div>';
			}
			html += '<div class="wd-fields">' + d.fields.map((f) => '<div class="wd-field' + (f.fmt === 'html' ? ' wide' : '') + '"><div class="label">' +
				esc(f.label) + '</div><div class="value">' + fmt(f.value, f.fmt) + '</div></div>').join('') + '</div>';
			if (d.location) html += '<div class="wd-mini-map"></div>';
			d.related.forEach((rel) => {
				html += '<div class="wd-related"><div class="title"><span>' + esc(rel.title) + '</span>' +
					(rel.doctype ? '<span class="wd-link" data-open-dt="' + esc(rel.doctype) + '" data-open-name="' + esc(rel.name) + '">' + __('Open') + ' ›</span>' : '') +
					'</div><div class="wd-fields" style="margin:0">' + rel.fields.map((f) => '<div class="wd-field"><div class="label">' + esc(f.label) +
					'</div><div class="value">' + fmt(f.value, f.fmt) + '</div></div>').join('') + '</div></div>';
			});
			html += '<div class="wd-detail-actions">' + d.actions.map((a, i) =>
				'<button class="wd-btn ' + (a.style === 'primary' ? 'green' : a.style === 'danger' ? 'red' : 'light') + '" data-i="' + i + '">' + esc(a.label) + '</button>'
			).join('') + (d.can_open ? '<button class="wd-btn light wd-open-form">' + __('Open {0}', [__(d.doctype)]) + ' ›</button>' : '') +
				(!d.actions.length && !d.can_open ? '<span class="wd-sub">' + __('No actions available for this record') + '</span>' : '') + '</div>';

			$b.html(html);
			$b.find('.wd-back').on('click', () => back());
			$b.find('.wd-open-form').on('click', () => { dialog.hide(); frappe.set_route('Form', d.doctype, d.name); });
			$b.find('[data-open-dt]').on('click', function () { dialog.hide(); frappe.set_route('Form', $(this).data('open-dt'), $(this).data('open-name')); });
			$b.find('.wd-emp-dash').on('click', () => {
				dialog.hide();
				frappe.route_options = { employee: d.employee.name };
				if (this.current === 'employee') this.show_from_route();
				frappe.set_route('workforce-dashboard', 'employee');
			});
			$b.find('.wd-detail-actions [data-i]').on('click', (e) => {
				var a = d.actions[$(e.currentTarget).data('i')];
				this.run_action(d.doctype, d.name, a, () => dialog.wd_reload ? dialog.wd_reload() : this.refresh(true));
			});
			if (d.location && window.L) {
				var mm = L.map($b.find('.wd-mini-map')[0], { scrollWheelZoom: false }).setView([d.location.lat, d.location.lng], 15);
				L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(mm);
				L.circleMarker([d.location.lat, d.location.lng], { radius: 8, color: '#fff', weight: 2, fillColor: '#2563eb', fillOpacity: 1 }).addTo(mm);
				setTimeout(() => mm.invalidateSize(), 250);
			} else if (d.location) {
				$b.find('.wd-mini-map').replaceWith('<p><a target="_blank" href="https://www.openstreetmap.org/?mlat=' + d.location.lat + '&mlon=' +
					d.location.lng + '#map=16/' + d.location.lat + '/' + d.location.lng + '">' + __('View location on map') + '</a></p>');
			}
		});
	}

	run_action(doctype, name, a, after) {
		var go = (value) => frappe.call({
			method: WD_API + 'take_action',
			args: { doctype: doctype, name: name, action: a.action, value: value || null },
			freeze: true,
			freeze_message: __('Updating…'),
		}).then((r) => {
			frappe.show_alert({ message: r.message.message, indicator: 'green' });
			if (after) after();
		});

		if (a.input === 'select') {
			frappe.prompt({ fieldname: 'value', label: __('Reassign to'), fieldtype: 'Select', reqd: 1, options: a.options },
				(v) => go(v.value), a.label, __('Reassign'));
		} else if (a.input === 'date') {
			frappe.prompt({ fieldname: 'value', label: __('New due date'), fieldtype: 'Date', reqd: 1, default: frappe.datetime.add_days(frappe.datetime.get_today(), 2) },
				(v) => go(v.value), a.label, __('Save'));
		} else if (a.input === 'text') {
			frappe.prompt({ fieldname: 'value', label: __('Reason (optional)'), fieldtype: 'Small Text' },
				(v) => go(v.value), __('Reject'), __('Reject'));
		} else if (a.action === 'approve') {
			frappe.confirm(__('Approve {0} {1}?', [__(doctype), name]), () => go());
		} else {
			go();
		}
	}

	// ---- export ----------------------------------------------------------

	export_excel(key) {
		var args = { dashboard: this.current, filters: JSON.stringify(this.get_filters()) };
		if (key) args.key = key;
		window.open('/api/method/' + WD_API + 'export_excel?' + $.param(args));
	}

	print() {
		// Charts and maps are already drawn, so the browser's "Save as PDF" captures the dashboard as seen.
		window.print();
	}
}

// ---- OverHead Project menu ------------------------------------------------------

// Date: 2026-10-09 — renamed from 'EVision'; must match SIDEBAR in setup.py. The dashboard page
// shows this sidebar, trimmed by ev_menu_items() to the links the user can open.
var EV_SIDEBAR = 'OverHead Project';
// Date: 2026-10-09 — the three menus that carry the one EVisions menu (see oh_menu in setup.py).
var OH_SIDEBARS = ['Dashboard', 'OverHead Project', 'Helpdesk NOC'];

// Menu link -> the doctype it opens. Team links are for leads, HR, finance and management only:
// employees reach their own Employee record and leave allocation through the dashboard instead.
var EV_LINKS = {
	// 2026-10-09: OH Project screens.
	'/app/new-project': { doctype: 'New Project' },
	'/app/network-link': { doctype: 'Network Link' },
	'/app/fiber-pulling-team': { doctype: 'Fiber Pulling Team' },
	'/app/maintenance-team': { doctype: 'Maintenance Team' },
	'/app/maintenance-vendor': { doctype: 'Maintenance Vendor' },
	'/app/task': { doctype: 'Task' },
	'/app/employee-checkin': { doctype: 'Employee Checkin' },
	'/app/attendance': { doctype: 'Attendance' },
	'/app/attendance-request': { doctype: 'Attendance Request' },
	'/app/leave-application': { doctype: 'Leave Application' },
	'/app/leave-allocation': { doctype: 'Leave Allocation', team: true },
	'/app/expense-claim': { doctype: 'Expense Claim' },
	'/app/trip-2': { doctype: 'Trip 2', team: true },
	'/app/location-ping': { doctype: 'Location Ping', team: true },
	'/app/employee': { doctype: 'Employee', team: true },
	'/app/project': { doctype: 'Project', team: true },
};

function ev_menu_items(items, scope) {
	var allowed = [];
	items.forEach((item) => {
		var link = item.link_type === 'URL' && EV_LINKS[item.url];
		if (!link) return allowed.push(item);
		if (link.team && scope === 'self') return;
		if (!frappe.model.can_read(link.doctype)) return;
		// Stored as URL so Frappe lists it for everyone; turned back into a DocType link here so it
		// opens in this tab (URL links get target=_blank) and the list keeps the EVision sidebar.
		allowed.push(Object.assign({}, item, { link_type: 'DocType', link_to: link.doctype, url: null }));
	});
	// Drop section headings left with nothing under them.
	return allowed.filter((item, i) => {
		if (item.type !== 'Section Break') return true;
		var next = allowed[i + 1];
		return next && next.type !== 'Section Break';
	});
}

// ---- helpers -----------------------------------------------------------------

function esc(v) {
	return frappe.utils.escape_html(v == null ? '' : String(v));
}

function inline_doctype(dt) {
	return dt === 'Leave Application' || dt === 'Expense Claim' || dt === 'Attendance Request';
}

function table_html(columns, rows, empty, inline_actions) {
	if (!rows.length) return '<div class="wd-empty">' + esc(empty) + '</div>';
	var numeric = ['int', 'float', 'pct', 'hours', 'km', 'currency', 'score'];
	var head = columns.map((c) => '<th class="' + (numeric.includes(c.fmt) ? 'num' : '') + '">' + esc(c.label) + '</th>').join('');
	if (inline_actions) head += '<th></th>';
	var body = rows.map((r, i) => {
		var clickable = r._drill || r._doctype;
		var tds = columns.map((c) => {
			var raw = r[c.key];
			var title = c.fmt === 'text' && raw ? ' title="' + esc(raw) + '"' : '';
			var cell = c.key === 'employee_name' && raw
				? '<div class="wd-emp-cell">' + avatar(raw) + '<span class="wd-emp-name">' + esc(raw) + '</span></div>'
				: fmt(raw, c.fmt);
			return '<td class="' + (numeric.includes(c.fmt) ? 'num' : '') + '"' + title + '>' + cell + '</td>';
		}).join('');
		if (inline_actions) {
			tds += '<td class="wd-actions-cell">' + (inline_doctype(r._doctype)
				? '<button class="wd-btn green" data-action="approve">' + __('Approve') + '</button>' +
					(r._doctype !== 'Attendance Request' ? '<button class="wd-btn red" data-action="reject">' + __('Reject') + '</button>' : '')
				: '') + '</td>';
		}
		return '<tr data-row="' + i + '"' + (clickable ? ' class="clickable"' : '') + '>' + tds + '</tr>';
	}).join('');
	return '<div class="wd-table-wrap"><table class="wd-table"><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>';
}

function fmt(v, type) {
	var dash = '<span class="text-muted">–</span>';
	if (v === null || v === undefined || v === '') return dash;
	switch (type) {
		case 'int': return esc(format_number(v, null, 0));
		case 'float': return esc(format_number(v, null, Number.isInteger(v) ? 0 : 1));
		case 'pct': return esc(format_number(v, null, Number.isInteger(v) ? 0 : 1)) + '%';
		case 'score': {
			var c = v >= 75 ? 'green' : v >= 60 ? 'orange' : 'red';
			return '<span class="wd-chip ' + c + '">' + esc(Math.round(v)) + '</span>';
		}
		case 'hours': {
			var mins = Math.round(v * 60);
			return esc(Math.floor(mins / 60) + 'h ' + String(mins % 60).padStart(2, '0') + 'm');
		}
		case 'km': return esc(format_number(v, null, 1)) + ' km';
		case 'currency': return esc(format_currency(v));
		case 'date': return esc(frappe.datetime.str_to_user(String(v).slice(0, 10)));
		case 'datetime': return esc(frappe.datetime.str_to_user(v));
		case 'time': {
			var s = String(v);
			var m = s.match(/(\d{1,2}):(\d{2})(?::\d{2})?(?:\.\d+)?$/);
			return esc(m ? m[1].padStart(2, '0') + ':' + m[2] : s);
		}
		case 'ago': return esc(typeof prettyDate === 'function' ? prettyDate(v) : frappe.datetime.str_to_user(v));
		case 'check': return v ? __('Yes') : __('No');
		case 'status': {
			var color = WD_STATUS_COLOR[v] || 'gray';
			return '<span class="wd-chip ' + color + '">' + esc(__(v)) + '</span>';
		}
		case 'html': return esc($('<div>').html(v).text());
		default: return esc(v);
	}
}

// Initials in a coloured circle, same as the Manager Dashboard cards; colour is stable per name.
function avatar(name, size) {
	var s = String(name || '?');
	var initials = s.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');
	var hash = 0;
	for (var i = 0; i < s.length; i++) hash = (hash * 31 + s.charCodeAt(i)) >>> 0;
	return '<span class="wd-avatar' + (size ? ' ' + size : '') + '" style="background:' + AVATAR_PALETTE[hash % AVATAR_PALETTE.length] + '">' +
		esc(initials) + '</span>';
}

function score_badge(score) {
	if (!score) return '';
	var v = score.value;
	var c = v == null ? 'gray' : v >= 75 ? 'green' : v >= 60 ? 'orange' : 'red';
	return '<span class="wd-score" data-drill="' + esc(score.drill || '') + '" title="' + __('Click for details') + '">' +
		'<span class="ring ' + c + '">' + (v == null ? '–' : esc(Math.round(v))) + '</span>' + __('Performance Score') +
		'<span class="m">· ' + __('Month {0}', [score.month == null ? '–' : esc(Math.round(score.month))]) + '</span></span>';
}

function kpi_icon(k) {
	var label = (k.label || '').toLowerCase();
	if (k.fmt === 'hours') return WD_ICONS.clock;
	if (k.fmt === 'km') return WD_ICONS.route;
	if (k.fmt === 'currency') return WD_ICONS.money;
	if (k.fmt === 'score') return WD_ICONS.star;
	if (k.fmt === 'pct') return WD_ICONS.chart;
	if (k.fmt === 'status') return WD_ICONS.person;
	if (/leave/.test(label)) return WD_ICONS.calendar;
	if (/field|gps|site|trip|location/.test(label)) return WD_ICONS.pin;
	if (/delay|overdue|exception|absent|missing|late|sla|excess|low|reject/.test(label)) return WD_ICONS.alert;
	if (/task|approval|claim|request/.test(label)) return WD_ICONS.list;
	return WD_ICONS.users;
}
