// Manager Dashboard — Frappe Desk page
// Route: /app/manager-dashboard
//
// Mirrors the logic in the mobile app's services/api.js `fetchManagerOverview`
// and screens/ManagerDashboardScreen.tsx, but as a browser page inside Frappe
// so managers can check live tracking without opening the mobile app.
//
// Reads from: Employee, Employee Checkin, Location Ping, Employee Home Location,
// Leave Application (all existing doctypes — nothing new was created for this).
//
// Overview, Live Location and Card View have real data behind them. Timeline,
// Compliance Status and Site Attendance are placeholders — there's no
// doctype/data model for those in this app yet.

frappe.pages['manager-dashboard'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Manager Dashboard',
		single_column: true,
	});

	new ManagerDashboard(page);
};

// ---- field-name constants: keep these in sync with your doctypes ----------
var FIELD_TIMESTAMP = 'timestamp';
var FIELD_SPEED = 'speed';
var FIELD_BATTERY = 'battery';
var OFFLINE_AFTER_MINUTES = 15;
var LOW_BATTERY_PERCENT = 15;
var REFRESH_INTERVAL_MS = 10000;

var STATUS_COLORS = {
	MOVING: '#16a34a',
	STOPPED: '#f97316',
	OFFLINE: '#94a3b8',
};

var AVATAR_PALETTE = ['#2563eb', '#0d9488', '#9333ea', '#ea580c', '#0891b2', '#4f46e5', '#be185d', '#16803d'];

// ---- inline icons (kept currentColor-friendly, unlike emoji) --------------
var ICON_SEARCH = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>';
var ICON_PIN = '<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/></svg>';
var ICON_FUNNEL = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16l-6.5 7.5v6L10.5 20v-7.5z"/></svg>';
var ICON_MENU = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>';
var ICON_USERS = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>';
var ICON_PLAY = '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
var ICON_PAUSE = '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>';
var ICON_OFFLINE = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><path d="M10.71 5.05A16 16 0 0 1 22.58 9"/><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>';
var ICON_ROUTE = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h7a2 2 0 0 0 2-2v-1a2 2 0 0 0-2-2H9a2 2 0 0 1-2-2v-1a2 2 0 0 1 2-2h7"/></svg>';

var TABS = [
	{ key: 'overview', icon: '📊', label: 'Overview' },
	{ key: 'live', icon: '📍', label: 'Live Location' },
	{ key: 'timeline', icon: '⏱', label: 'Timeline' },
	{ key: 'cardview', icon: '▦', label: 'Card View' },
];

class ManagerDashboard {
	constructor(page) {
		this.page = page;
		this.punchFilter = 'ALL';
		this.statusFilter = 'ALL';
		this.batteryFilter = 'ALL';
		this.search = '';
		this.showSites = true;
		this.employees = [];
		this.homeLocations = [];
		this.offDuty = [];
		this.map = null;
		this.markersLayer = null;
		this.leafletReady = false;

		this.geocodeCache = new Map();
		this.geocodeQueue = [];
		this.geocodeQueued = new Set();
		this.geocodeDraining = false;
		this.geocodeRefreshTimer = null;

		this.timelineMap = null;
		this.timelineMarkersLayer = null;
		this.timelineInitialized = false;
		this.timelineDataLoaded = false;
		this.currentTimelinePayload = null;
		this.timelineEmployeeId = null;
		this.timelineDate = frappe.datetime.get_today();

		this.page.set_indicator('Loading…', 'orange');

		this.render_shell();
		this.load_leaflet(() => {
			this.init_map();
			this.load_data();
		});

		this._interval = setInterval(() => this.load_data(), REFRESH_INTERVAL_MS);
	}

	render_shell() {
		this.page.body.empty();
		this.$root = $(`
			<div class="md-root">
				<style>
					.md-root { padding: 12px 16px 28px 16px; }
					.md-live-toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }
					@media (max-width: 480px) {
						.md-root { padding: 10px 12px 24px 12px; }
						.md-live-toolbar { row-gap: 14px; column-gap: 8px; margin-bottom: 14px; }
						.md-toolbar-search { min-width: 0; flex-basis: 140px; }
						.md-attention { margin-bottom: 10px; padding: 10px 12px; }
						.md-section-head { margin-bottom: 8px; }
					}

					.md-tabbar { display: flex; gap: 22px; border-bottom: 1px solid #e5e7eb; margin-bottom: 16px; flex-wrap: wrap; }
					.md-tab { display: flex; align-items: center; gap: 6px; padding: 10px 2px; font-size: 13px; font-weight: 700;
						color: #64748b; cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap; }
					.md-tab:hover { color: #334155; }
					.md-tab.active { color: #2563eb; border-bottom-color: #2563eb; }
					.md-tab-icon { font-size: 13px; }
					.md-tab-panel { display: none; }
					.md-tab-panel.active { display: block; }
					.md-updated { font-size: 12px; color: #64748b; margin-bottom: 14px; }

					.md-stats { display: flex; gap: 12px; margin-bottom: 22px; flex-wrap: wrap; }
					.md-stat { flex: 1; min-width: 150px; background: #fff; border: 1px solid #e5e7eb; border-top: 3px solid transparent;
						border-radius: 12px; padding: 13px 14px; display: flex; align-items: center; gap: 12px;
						box-shadow: 0 1px 2px rgba(15,23,42,0.04); transition: box-shadow .15s, transform .15s; }
					.md-stat:hover { box-shadow: 0 4px 10px rgba(15,23,42,0.08); transform: translateY(-1px); }
					.md-stat-icon { width: 34px; height: 34px; border-radius: 10px; display: flex; align-items: center;
						justify-content: center; flex-shrink: 0; }
					.md-stat .val { font-size: 19px; font-weight: 800; color: #0f172a; line-height: 1.15; }
					.md-stat .lbl { font-size: 10.5px; color: #64748b; margin-top: 2px; font-weight: 600; }
					.md-stat.stat-active { border-top-color: #2563eb; }
					.md-stat.stat-active .md-stat-icon { background: #eff6ff; color: #2563eb; }
					.md-stat.stat-moving { border-top-color: #16a34a; }
					.md-stat.stat-moving .md-stat-icon { background: #f0fdf4; color: #16a34a; }
					.md-stat.stat-moving .val { color: #16a34a; }
					.md-stat.stat-stopped { border-top-color: #f97316; }
					.md-stat.stat-stopped .md-stat-icon { background: #fff7ed; color: #f97316; }
					.md-stat.stat-stopped .val { color: #f97316; }
					.md-stat.stat-offline { border-top-color: #ef4444; }
					.md-stat.stat-offline .md-stat-icon { background: #fef2f2; color: #ef4444; }
					.md-stat.stat-offline .val { color: #ef4444; }
					.md-stat.stat-distance { border-top-color: #7c3aed; }
					.md-stat.stat-distance .md-stat-icon { background: #f5f3ff; color: #7c3aed; }
					.md-stat.stat-distance .val { color: #7c3aed; }

					.md-attention { background: linear-gradient(180deg, #fff, #fef2f2); border: 1px solid #fecdd3; border-radius: 14px;
						padding: 16px 20px; margin-bottom: 22px; display: none; box-shadow: 0 1px 3px rgba(153,27,27,0.06); }
					.md-attention.show { display: block; }
					.md-attention-title { font-size: 13px; font-weight: 800; color: #991b1b; margin-bottom: 10px;
						display: flex; align-items: center; gap: 7px; }
					.md-attention-title .warn-icon { width: 18px; height: 18px; border-radius: 50%; background: #fee2e2; color: #dc2626;
						display: flex; align-items: center; justify-content: center; font-size: 11px; flex-shrink: 0; }
					.md-attention-row { display: flex; justify-content: space-between; align-items: center; padding: 9px 0;
						font-size: 12.5px; border-bottom: 1px solid #fee2e2; }
					.md-attention-row:last-child { border-bottom: none; padding-bottom: 2px; }
					.md-attention-row .name { font-weight: 700; color: #111827; display: flex; align-items: center; gap: 8px; }
					.md-attention-row .name::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: #dc2626;
						flex-shrink: 0; }
					.md-attention-row .reason { color: #b91c1c; font-weight: 700; font-size: 11px; background: #fee2e2;
						padding: 4px 10px; border-radius: 20px; white-space: nowrap; }

					.md-section-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;
						gap: 10px; margin-bottom: 18px; }
					.md-section-title { font-size: 16px; font-weight: 800; color: #0f172a; }
					.md-pills { display: flex; gap: 8px; flex-wrap: wrap; }
					.md-pill { border-radius: 20px; padding: 6px 14px; font-size: 11.5px; font-weight: 800; color: #fff;
						cursor: pointer; white-space: nowrap; opacity: 0.92; transition: transform .1s, opacity .1s; }
					.md-pill:hover { opacity: 1; }
					.md-pill.active { box-shadow: 0 0 0 2px rgba(15,23,42,0.35) inset; opacity: 1; }
					.md-pill.all { background: #2563eb; }
					.md-pill.in { background: #16a34a; }
					.md-pill.out { background: #dc2626; }

					.md-toolbar-row { display: flex; align-items: center; justify-content: space-between; gap: 10px;
						flex-wrap: wrap; margin-bottom: 18px; }
					.md-toolbar-search { position: relative; flex: 1; min-width: 200px; max-width: 340px; }
					.md-toolbar-search input { width: 100%; box-sizing: border-box; border: 1px solid #e2e8f0; border-radius: 10px;
						padding: 8px 12px 8px 30px; font-size: 12.5px; background: #f8fafc; outline: none; transition: border-color .15s; }
					.md-toolbar-search input:focus { border-color: #93c5fd; background: #fff; }
					.md-toolbar-search-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #94a3b8; }
					.md-toolbar-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
					.md-filter-icon-btn { width: 32px; height: 32px; border-radius: 8px; border: 1px solid #93c5fd; background: #eff6ff;
						color: #2563eb; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background .15s; }
					.md-filter-icon-btn:hover { background: #dbeafe; }
					.md-checkbox-toggle { display: flex; align-items: center; gap: 5px; font-size: 11.5px; font-weight: 600;
						color: #475569; cursor: pointer; user-select: none; }
					.md-checkbox-toggle input { cursor: pointer; accent-color: #2563eb; }
					.md-drawer-toggle-btn { width: 32px; height: 32px; border-radius: 8px; border: 1px solid #e2e8f0; background: #fff;
						color: #475569; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0;
						transition: border-color .15s, color .15s; }
					.md-drawer-toggle-btn:hover { border-color: #93c5fd; color: #2563eb; }

					.md-map-full-wrap { position: relative; flex: 1; min-width: 0; }
					.md-map-area-live { height: 600px; border: 1px solid #e5e7eb; border-radius: 14px; overflow: hidden;
						background: #fff; box-shadow: 0 1px 3px rgba(15,23,42,0.06); }
					.md-drawer { position: absolute; top: 0; left: 0; bottom: 0; width: 340px; background: #fff;
						box-shadow: 2px 0 14px rgba(15,23,42,0.18); transform: translateX(-100%); transition: transform .25s ease;
						z-index: 1100; display: flex; flex-direction: column; }
					.md-drawer.open { transform: translateX(0); }
					.md-drawer-head { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px;
						border-bottom: 1px solid #f1f5f9; font-weight: 800; font-size: 13px; color: #0f172a; }
					.md-drawer-close { border: none; background: none; font-size: 20px; line-height: 1; cursor: pointer; color: #94a3b8; }
					.md-drawer-close:hover { color: #334155; }
					.md-drawer .md-cardlist { flex: 1; overflow-y: auto; padding: 10px; }

					.md-cardlist { flex: 1; overflow-y: auto; padding: 10px 10px 14px; }
					.md-emp-card { display: flex; gap: 10px; background: #fff; border: 1px solid #e5e7eb; border-left: 4px solid #cbd5e1;
						border-radius: 10px; padding: 10px 12px; margin-bottom: 9px; cursor: pointer;
						box-shadow: 0 1px 2px rgba(15,23,42,0.04); transition: border-color .15s, box-shadow .15s, transform .1s; }
					.md-emp-card:hover { border-color: #93c5fd; border-left-color: #93c5fd; box-shadow: 0 4px 10px rgba(37,99,235,0.12);
						transform: translateY(-1px); }
					.md-emp-card.punch-in { border-left-color: #16a34a; }
					.md-emp-card.punch-out { border-left-color: #dc2626; }
					.md-avatar { width: 36px; height: 36px; border-radius: 18px; display: flex; align-items: center; justify-content: center;
						color: #fff; font-weight: 800; font-size: 12px; flex-shrink: 0; margin-top: 1px; }
					.md-card-body { flex: 1; min-width: 0; }
					.md-card-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 6px; }
					.md-card-name { font-size: 13px; font-weight: 800; color: #0f172a; }
					.md-card-name .device-id { color: #2563eb; font-weight: 700; }
					.md-card-phone { font-size: 11px; color: #64748b; margin-top: 1px; }
					.md-card-meta { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
					.md-meta-chip { font-size: 10.5px; font-weight: 700; display: flex; align-items: center; gap: 3px; }
					.md-battery-icon { display: inline-block; width: 15px; height: 8px; border: 1.4px solid currentColor; border-radius: 2px;
						position: relative; padding: 1px; box-sizing: border-box; }
					.md-battery-icon::after { content: ''; position: absolute; right: -3.5px; top: 2px; width: 2px; height: 3px;
						background: currentColor; border-radius: 0 1px 1px 0; }
					.md-battery-icon > span { display: block; height: 100%; border-radius: 1px; }
					.md-punch-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 7px; }
					.md-punch-label { font-size: 10.5px; font-weight: 700; padding: 3px 8px; border-radius: 6px; }
					.md-punch-label.in { color: #15803d; background: #dcfce7; }
					.md-punch-label.out { color: #b91c1c; background: #fee2e2; }
					.md-timeline-btn { font-size: 10px; font-weight: 800; color: #fff; background: #2563eb; border: none;
						border-radius: 6px; padding: 4px 9px; cursor: pointer; white-space: nowrap; }
					.md-timeline-btn:hover { background: #1d4ed8; }
					.md-card-address { font-size: 11px; color: #475569; margin-top: 7px; }
					.md-inline-pin { color: #94a3b8; display: inline-flex; vertical-align: -1px; }
					.md-card-ago { font-size: 10.5px; color: #94a3b8; margin-top: 2px; }
					.md-empty { text-align: center; padding: 30px 14px; color: #94a3b8; font-size: 13px; }

					.md-select { border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px 8px; font-size: 11.5px; color: #334155;
						background: #f8fafc; font-weight: 600; }
					.md-reset-btn { border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px 10px;
						font-size: 11.5px; font-weight: 700; color: #475569; background: #fff; cursor: pointer; }
					.md-reset-btn:hover { border-color: #cbd5e1; }

					.md-map-area { flex: 1; position: relative; }
					.md-map { position: absolute; inset: 0; }
					.md-view-toggle { position: absolute; top: 10px; right: 10px; z-index: 1000; background: #fff; border-radius: 8px;
						overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.25); display: flex; }
					.md-view-btn { border: none; background: #fff; padding: 6px 12px; font-size: 11.5px; font-weight: 700;
						color: #475569; cursor: pointer; }
					.md-view-btn.active { background: #2563eb; color: #fff; }
					.md-map-name-pin { display: flex; align-items: center; gap: 4px; white-space: nowrap; }
					.md-map-name-dot { width: 12px; height: 12px; border-radius: 50%; border: 2px solid #fff;
						box-shadow: 0 0 4px rgba(0,0,0,.4); flex-shrink: 0; }
					.md-map-name-label { background: #fff; padding: 1px 7px; border-radius: 6px; font-size: 11px; font-weight: 700;
						box-shadow: 0 1px 3px rgba(0,0,0,.3); }

					.md-cardview-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }

					.md-tl-toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
					.md-tl-hide-btn { border: 1px solid #e2e8f0; background: #fff; color: #475569; border-radius: 8px;
						padding: 7px 12px; font-size: 12px; font-weight: 700; cursor: pointer; }
					.md-tl-hide-btn:hover { border-color: #cbd5e1; }
					.md-tl-emp-select { min-width: 220px; }
					.md-tl-date-nav { display: flex; align-items: center; gap: 4px; }
					.md-tl-date-nav button { width: 28px; height: 28px; border: 1px solid #e2e8f0; background: #fff; border-radius: 7px;
						color: #475569; cursor: pointer; font-size: 14px; }
					.md-tl-date-nav button:hover { border-color: #93c5fd; color: #2563eb; }
					.md-tl-date-input { border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px 8px; font-size: 12px; color: #334155; }

					.md-tl-body { display: flex; gap: 16px; height: 640px; }
					@media (max-width: 900px) { .md-tl-body { flex-direction: column; height: auto; } }
					.md-tl-details { width: 360px; flex-shrink: 0; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; }
					@media (max-width: 900px) { .md-tl-details { width: 100%; } }
					.md-tl-stats-row { display: flex; gap: 8px; flex-wrap: wrap; }
					.md-tl-stat { flex: 1; min-width: 62px; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px;
						padding: 8px 6px; text-align: center; box-shadow: 0 1px 2px rgba(15,23,42,0.04); }
					.md-tl-stat .v { font-size: 12px; font-weight: 800; color: #0f172a; }
					.md-tl-stat .l { font-size: 8.5px; color: #64748b; font-weight: 600; margin-top: 2px; }
					.md-tl-badges { display: flex; gap: 8px; flex-wrap: wrap; }
					.md-tl-badge { font-size: 11.5px; font-weight: 700; padding: 7px 12px; border-radius: 8px; border: 1px solid #e2e8f0;
						background: #fff; color: #475569; }
					.md-tl-badge.good { background: #dcfce7; border-color: #bbf7d0; color: #15803d; }
					.md-tl-badge.poor { background: #fef2f2; border-color: #fecaca; color: #b91c1c; }

					.md-tl-events { flex: 1; overflow-y: auto; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px;
						padding: 4px 12px; }
					.md-tl-event { display: flex; gap: 10px; padding: 12px 0; border-bottom: 1px solid #f1f5f9; }
					.md-tl-event:last-child { border-bottom: none; }
					.md-tl-event-num { width: 22px; height: 22px; border-radius: 50%; color: #fff; font-size: 11px; font-weight: 800;
						display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px; }
					.md-tl-event-num.in { background: #16a34a; }
					.md-tl-event-num.out { background: #dc2626; }
					.md-tl-event-num.halt { background: #64748b; }
					.md-tl-event-body { flex: 1; min-width: 0; }
					.md-tl-event-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
					.md-tl-event-time { font-size: 11.5px; font-weight: 700; color: #334155; }
					.md-tl-event-gap { font-size: 9.5px; color: #94a3b8; font-weight: 600; margin-left: 4px; }
					.md-tl-event-battery { font-size: 10.5px; font-weight: 700; display: flex; align-items: center; gap: 3px; }
					.md-tl-event-address { font-size: 11.5px; color: #334155; font-weight: 700; margin-top: 3px; }
					.md-tl-event-sub { font-size: 10.5px; color: #64748b; margin-top: 4px; display: flex; align-items: center; gap: 5px; }
					.md-tl-event-sub .tag { background: #f1f5f9; color: #475569; padding: 1px 6px; border-radius: 5px; font-weight: 700; }
					.md-tl-travel-row { display: flex; align-items: center; gap: 8px; padding: 8px 0 8px 32px; font-size: 11px;
						color: #64748b; font-weight: 700; border-bottom: 1px solid #f1f5f9; }
					.md-tl-empty { text-align: center; color: #94a3b8; font-size: 12.5px; padding: 30px 10px; }

					.md-tl-body.details-hidden .md-tl-details { display: none; }

					.md-ov-top { display: flex; gap: 14px; margin-bottom: 16px; flex-wrap: wrap; }
					.md-ov-col-left { flex: 2; min-width: 320px; display: flex; gap: 14px; flex-wrap: wrap; }
					.md-ov-card { flex: 1; min-width: 176px; background: #fff; border: 1px solid #e5e7eb; border-radius: 14px; padding: 16px; }
					@media (max-width: 480px) {
						.md-ov-col-left { flex-direction: column; min-width: 0; }
						.md-ov-card { min-width: 0; width: 100%; }
					}
					.md-ov-card-title { font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 10px; display: flex;
						align-items: center; gap: 5px; }
					.md-ov-legend { display: flex; gap: 16px; margin-bottom: 6px; font-size: 11.5px; font-weight: 700; }
					.md-ov-legend span.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; }
					.md-gauge { width: 130px; height: 130px; border-radius: 50%; position: relative; margin: 6px auto 0; }
					.md-gauge::before { content: ''; position: absolute; inset: 16px; background: #fff; border-radius: 50%; }
					.md-gauge-label { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center;
						justify-content: center; text-align: center; }
					.md-gauge-label .n { font-size: 20px; font-weight: 800; color: #0f172a; }
					.md-gauge-label .l { font-size: 9.5px; color: #64748b; font-weight: 700; }
					.md-ov-big { font-size: 30px; font-weight: 800; color: #0f172a; text-align: center; margin-top: 18px; }
					.md-ov-ratio { font-size: 26px; font-weight: 800; color: #0f172a; text-align: center; margin-top: 18px; }

					.md-ov-teams { flex: 1; min-width: 260px; background: #fff; border: 1px solid #e5e7eb; border-radius: 14px;
						padding: 16px; max-height: 220px; overflow-y: auto; }
					.md-ov-team-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0;
						font-size: 12.5px; font-weight: 600; color: #334155; border-bottom: 1px solid #f8fafc; }
					.md-ov-team-counts { display: flex; gap: 12px; font-weight: 700; font-size: 12px; }
					.md-ov-team-counts .g { color: #16a34a; } .md-ov-team-counts .r { color: #dc2626; }

					.md-ov-tables { display: flex; gap: 14px; flex-wrap: wrap; }
					.md-ov-table-card { flex: 1; min-width: 340px; background: #fff; border: 1px solid #e5e7eb; border-radius: 14px;
						padding: 14px; }
					.md-ov-table-head { display: flex; align-items: center; justify-content: space-between; gap: 8px;
						flex-wrap: wrap; margin-bottom: 10px; }
					.md-ov-table-title { font-size: 13.5px; font-weight: 800; color: #0f172a; }
					.md-ov-table-controls { display: flex; gap: 6px; }
					.md-ov-table-controls input { border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px 8px; font-size: 11.5px;
						width: 120px; }
					.md-ov-table { width: 100%; border-collapse: collapse; }
					.md-ov-table thead th { text-align: left; font-size: 10.5px; text-transform: uppercase; letter-spacing: .03em;
						color: #94a3b8; font-weight: 700; padding: 6px 6px; border-bottom: 1px solid #f1f5f9; }
					.md-ov-table tbody td { padding: 8px 6px; font-size: 12px; color: #334155; border-bottom: 1px solid #f8fafc;
						vertical-align: top; }
					.md-ov-emp-cell { display: flex; align-items: center; gap: 8px; }
					.md-ov-emp-name { font-weight: 700; color: #0f172a; }
					.md-ov-scroll { max-height: 320px; overflow-y: auto; }
				</style>

				<div class="md-tabbar"></div>

				<div class="md-tab-panel active" data-panel="overview">
					<div class="md-toolbar-row">
						<div class="md-section-title">Realtime Dashboard</div>
						<button class="md-timeline-btn md-export-btn" style="padding:8px 14px;font-size:12px;">⬇ Attendance Status</button>
					</div>

					<div class="md-ov-top">
						<div class="md-ov-col-left">
							<div class="md-ov-card">
								<div class="md-ov-card-title">Real Time Status</div>
								<div class="md-ov-legend">
									<span><span class="dot" style="background:#16a34a"></span><span class="md-ov-in-count">0</span> Punched In</span>
									<span><span class="dot" style="background:#dc2626"></span><span class="md-ov-out-count">0</span> Punched Out</span>
								</div>
								<div class="md-gauge">
									<div class="md-gauge-label"><span class="n md-ov-total">0</span><span class="l">All Employees</span></div>
								</div>
							</div>
							<div class="md-ov-card">
								<div class="md-ov-card-title">Punched In (Inactive) Employees</div>
								<div class="md-ov-big md-ov-inactive">0</div>
							</div>
							<div class="md-ov-card">
								<div class="md-ov-card-title">Staffing Strength</div>
								<div class="md-ov-ratio md-ov-strength">0 / 0</div>
							</div>
						</div>
						<div class="md-ov-teams">
							<div class="md-ov-card-title">Teamwise Attendance</div>
							<div class="md-ov-teams-list"></div>
						</div>
					</div>

					<div class="md-ov-tables">
						<div class="md-ov-table-card">
							<div class="md-ov-table-head">
								<div class="md-ov-table-title">Employees (<span class="md-ov-emp-total">0</span>)</div>
								<div class="md-ov-table-controls">
									<select class="md-select md-ov-emp-filter">
										<option value="ALL">All</option>
										<option value="IN">Punched In</option>
										<option value="OUT">Punched Out</option>
									</select>
									<input type="text" class="md-ov-emp-search" placeholder="Search Here">
								</div>
							</div>
							<div class="md-ov-scroll">
								<table class="md-ov-table">
									<thead><tr><th>Employee</th><th>Attendance</th><th>Punch Location</th><th>Last Location</th></tr></thead>
									<tbody class="md-ov-emp-body"></tbody>
								</table>
							</div>
						</div>
						<div class="md-ov-table-card">
							<div class="md-ov-table-head">
								<div class="md-ov-table-title">Off Duty Employees (<span class="md-ov-offduty-total">0</span>)</div>
								<div class="md-ov-table-controls">
									<select class="md-select md-ov-offduty-filter">
										<option value="ALL">All</option>
									</select>
									<input type="text" class="md-ov-offduty-search" placeholder="Search Here">
								</div>
							</div>
							<div class="md-ov-scroll">
								<table class="md-ov-table">
									<thead><tr><th>Employee</th><th>Team Name</th><th>Status</th></tr></thead>
									<tbody class="md-ov-offduty-body"></tbody>
								</table>
							</div>
						</div>
					</div>
				</div>

				<div class="md-tab-panel" data-panel="live">
					<div class="md-updated">Updated: <span class="md-updated-time">—</span></div>

					<div class="md-stats">
						<div class="md-stat stat-active"><div class="md-stat-icon">${ICON_USERS}</div><div><div class="val md-v-active">0</div><div class="lbl">Active</div></div></div>
						<div class="md-stat stat-moving"><div class="md-stat-icon">${ICON_PLAY}</div><div><div class="val md-v-moving">0</div><div class="lbl">Moving</div></div></div>
						<div class="md-stat stat-stopped"><div class="md-stat-icon">${ICON_PAUSE}</div><div><div class="val md-v-stopped">0</div><div class="lbl">Stopped</div></div></div>
						<div class="md-stat stat-offline"><div class="md-stat-icon">${ICON_OFFLINE}</div><div><div class="val md-v-offline">0</div><div class="lbl">Offline</div></div></div>
						<div class="md-stat stat-distance"><div class="md-stat-icon">${ICON_ROUTE}</div><div><div class="val md-v-distance">0</div><div class="lbl">Total km</div></div></div>
					</div>

					<div class="md-attention">
						<div class="md-attention-title"><span class="warn-icon">!</span><span class="md-attention-count">0</span> employee(s) need attention</div>
						<div class="md-attention-list"></div>
					</div>

					<div class="md-section-head">
						<div class="md-section-title">Employees (<span class="md-emp-count">0</span>)</div>
						<div class="md-pills">
							<div class="md-pill all active" data-punch="ALL"><span class="md-pill-count md-pc-all">0</span> All Employees</div>
							<div class="md-pill in" data-punch="IN"><span class="md-pill-count md-pc-in">0</span> Punched In</div>
							<div class="md-pill out" data-punch="OUT"><span class="md-pill-count md-pc-out">0</span> Punched Out</div>
						</div>
					</div>

					<div class="md-live-toolbar">
						<button class="md-drawer-toggle-btn" title="Employee list">${ICON_MENU}</button>
						<div class="md-toolbar-search">
							<span class="md-toolbar-search-icon">${ICON_SEARCH}</span>
							<input type="text" class="md-search-input" placeholder="Search Employee...">
						</div>
						<div class="md-toolbar-right">
							<select class="md-select md-battery-filter">
								<option value="ALL">Battery: All</option>
								<option value="LOW">Battery: Low (≤15%)</option>
								<option value="MED">Battery: Medium</option>
								<option value="GOOD">Battery: Good</option>
							</select>
							<select class="md-select md-gps-filter">
								<option value="ALL">GPS: All</option>
								<option value="MOVING">GPS: Moving</option>
								<option value="STOPPED">GPS: Stopped</option>
								<option value="OFFLINE">GPS: Offline</option>
							</select>
							<label class="md-checkbox-toggle"><input type="checkbox" data-toggle="sites" checked> Show Sites</label>
							<button class="md-filter-icon-btn md-reset-btn" title="Reset filters">${ICON_FUNNEL}</button>
						</div>
					</div>

					<div class="md-map-full-wrap">
						<div class="md-map-area md-map-area-live">
							<div class="md-view-toggle">
								<button class="md-view-btn active" data-view="map">Map</button>
								<button class="md-view-btn" data-view="sat">Satellite</button>
							</div>
							<div class="md-map" id="md-map"></div>
							<div class="md-drawer">
								<div class="md-drawer-head"><span>Employees</span><button class="md-drawer-close">&times;</button></div>
								<div class="md-cardlist"></div>
							</div>
						</div>
					</div>
				</div>

				<div class="md-tab-panel" data-panel="timeline">
					<div class="md-tl-toolbar">
						<button class="md-tl-hide-btn">&times; Hide Details</button>
						<select class="md-select md-tl-emp-select"></select>
						<div class="md-tl-date-nav">
							<button class="md-tl-date-prev">‹</button>
							<input type="date" class="md-tl-date-input">
							<button class="md-tl-date-next">›</button>
						</div>
						<button class="md-timeline-btn md-tl-apply-btn" style="padding:7px 16px;">Apply</button>
						<button class="md-filter-icon-btn md-tl-reset-btn" title="Reset" style="margin-left:auto">${ICON_FUNNEL}</button>
					</div>

					<div class="md-tl-body">
						<div class="md-tl-details">
							<div class="md-tl-stats-row">
								<div class="md-tl-stat"><div class="v md-tl-att-status">-</div><div class="l">Attendance Status</div></div>
								<div class="md-tl-stat"><div class="v md-tl-att-hours">-</div><div class="l">Attendance Hours</div></div>
								<div class="md-tl-stat"><div class="v md-tl-time-tracked">-</div><div class="l">Time Tracked</div></div>
								<div class="md-tl-stat"><div class="v md-tl-gps-distance">-</div><div class="l">GPS Distance</div></div>
								<div class="md-tl-stat"><div class="v md-tl-activities">-</div><div class="l">Activities</div></div>
							</div>
							<div class="md-tl-badges">
								<div class="md-tl-badge md-tl-location-setting">Location Setting : —</div>
							</div>
							<div class="md-tl-events"></div>
						</div>
						<div class="md-map-full-wrap md-tl-mapwrap">
							<div class="md-map-area md-map-area-live">
								<div class="md-view-toggle">
									<button class="md-view-btn active md-tl-view-btn" data-view="map">Map</button>
									<button class="md-view-btn md-tl-view-btn" data-view="sat">Satellite</button>
								</div>
								<div class="md-map" id="md-timeline-map"></div>
							</div>
						</div>
					</div>
				</div>

				<div class="md-tab-panel" data-panel="cardview">
					<div class="md-toolbar-row">
						<div class="md-section-title">Employees (<span class="md-cv-emp-count">0</span>)</div>
						<div class="md-toolbar-right">
							<div class="md-pills md-cv-pills">
								<div class="md-pill all active" data-punch="ALL"><span class="md-pill-count md-cv-pc-all">0</span> All Employees</div>
								<div class="md-pill in" data-punch="IN"><span class="md-pill-count md-cv-pc-in">0</span> Punched In</div>
								<div class="md-pill out" data-punch="OUT"><span class="md-pill-count md-cv-pc-out">0</span> Punched Out</div>
							</div>
						</div>
					</div>
					<div class="md-toolbar-row">
						<div class="md-toolbar-search">
							<span class="md-toolbar-search-icon">${ICON_SEARCH}</span>
							<input type="text" class="md-cv-search-input" placeholder="Search Here">
						</div>
						<div class="md-toolbar-right">
							<select class="md-select md-cv-battery-filter">
								<option value="ALL">Battery: All</option>
								<option value="LOW">Battery: Low (≤15%)</option>
								<option value="MED">Battery: Medium</option>
								<option value="GOOD">Battery: Good</option>
							</select>
							<select class="md-select md-cv-gps-filter">
								<option value="ALL">GPS: All</option>
								<option value="MOVING">GPS: Moving</option>
								<option value="STOPPED">GPS: Stopped</option>
								<option value="OFFLINE">GPS: Offline</option>
							</select>
							<button class="md-filter-icon-btn md-cv-reset-btn" title="Reset filters">${ICON_FUNNEL}</button>
						</div>
					</div>
					<div class="md-cardview-grid"></div>
				</div>

			</div>
		`).appendTo(this.page.body);

		this.render_tabbar();

		this.$root.find('.md-pill').on('click', (e) => {
			this.punchFilter = $(e.currentTarget).data('punch');
			this.$root.find('.md-pill').removeClass('active');
			this.$root.find(`.md-pill[data-punch="${this.punchFilter}"]`).addClass('active');
			this.render_all_filtered();
		});

		this.$root.find('.md-search-input, .md-cv-search-input').on('input', (e) => {
			this.search = $(e.currentTarget).val().trim().toLowerCase();
			this.$root.find('.md-search-input, .md-cv-search-input').val($(e.currentTarget).val());
			this.render_all_filtered();
		});

		this.$root.find('.md-battery-filter, .md-cv-battery-filter').on('change', (e) => {
			this.batteryFilter = $(e.currentTarget).val();
			this.$root.find('.md-battery-filter, .md-cv-battery-filter').val(this.batteryFilter);
			this.render_all_filtered();
		});

		this.$root.find('.md-gps-filter, .md-cv-gps-filter').on('change', (e) => {
			this.statusFilter = $(e.currentTarget).val();
			this.$root.find('.md-gps-filter, .md-cv-gps-filter').val(this.statusFilter);
			this.render_all_filtered();
		});

		this.$root.find('[data-toggle="sites"]').on('change', (e) => {
			this.showSites = $(e.currentTarget).prop('checked');
			this.render_map_and_list();
		});

		this.$root.find('.md-reset-btn, .md-cv-reset-btn').on('click', () => {
			this.punchFilter = 'ALL';
			this.statusFilter = 'ALL';
			this.batteryFilter = 'ALL';
			this.search = '';
			this.showSites = true;
			this.$root.find('.md-search-input, .md-cv-search-input').val('');
			this.$root.find('.md-battery-filter, .md-cv-battery-filter').val('ALL');
			this.$root.find('.md-gps-filter, .md-cv-gps-filter').val('ALL');
			this.$root.find('.md-pill').removeClass('active');
			this.$root.find('.md-pill.all').addClass('active');
			this.$root.find('[data-toggle="sites"]').prop('checked', true);
			this.render_all_filtered();
		});

		this.$root.find('.md-drawer-toggle-btn').on('click', () => {
			this.$root.find('.md-drawer').toggleClass('open');
		});
		this.$root.find('.md-drawer-close').on('click', () => {
			this.$root.find('.md-drawer').removeClass('open');
		});

		this.$root.find('.md-view-btn').on('click', (e) => {
			var view = $(e.currentTarget).data('view');
			this.$root.find('.md-view-btn').removeClass('active');
			$(e.currentTarget).addClass('active');
			if (this.tileStreets && this.tileSatellite) {
				if (view === 'sat') {
					this.map.removeLayer(this.tileStreets);
					this.tileSatellite.addTo(this.map);
				} else {
					this.map.removeLayer(this.tileSatellite);
					this.tileStreets.addTo(this.map);
				}
			}
		});

		this.$root.find('.md-export-btn').on('click', () => this.export_attendance_csv());

		this.$root.find('.md-ov-emp-filter, .md-ov-emp-search').on('change input', () => this.render_overview_employee_table());
		this.$root.find('.md-ov-offduty-search').on('input', () => this.render_overview_offduty_table());

		this.$root.find('.md-tl-hide-btn').on('click', (e) => {
			var hidden = this.$root.find('.md-tl-body').toggleClass('details-hidden').hasClass('details-hidden');
			$(e.currentTarget).html(hidden ? '☰ Show Details' : '&times; Hide Details');
			if (this.timelineMap) setTimeout(() => this.timelineMap.invalidateSize(), 260);
		});

		this.$root.find('.md-tl-apply-btn').on('click', () => this.load_timeline());

		this.$root.find('.md-tl-date-prev').on('click', () => this.shift_timeline_date(-1));
		this.$root.find('.md-tl-date-next').on('click', () => this.shift_timeline_date(1));

		this.$root.find('.md-tl-reset-btn').on('click', () => {
			this.timelineDate = frappe.datetime.get_today();
			this.$root.find('.md-tl-date-input').val(this.timelineDate);
			if (this.employees.length) {
				this.timelineEmployeeId = this.employees[0].employeeId;
				this.$root.find('.md-tl-emp-select').val(this.timelineEmployeeId);
			}
			this.load_timeline();
		});

		this.$root.find('.md-tl-view-btn').on('click', (e) => {
			var view = $(e.currentTarget).data('view');
			this.$root.find('.md-tl-view-btn').removeClass('active');
			this.$root.find(`.md-tl-view-btn[data-view="${view}"]`).addClass('active');
			if (this.timelineTileStreets && this.timelineTileSatellite) {
				if (view === 'sat') {
					this.timelineMap.removeLayer(this.timelineTileStreets);
					this.timelineTileSatellite.addTo(this.timelineMap);
				} else {
					this.timelineMap.removeLayer(this.timelineTileSatellite);
					this.timelineTileStreets.addTo(this.timelineMap);
				}
			}
		});
	}

	render_tabbar() {
		var $bar = this.$root.find('.md-tabbar').empty();
		TABS.forEach((t, i) => {
			$bar.append(
				`<div class="md-tab${i === 0 ? ' active' : ''}" data-tab="${t.key}">
					<span class="md-tab-icon">${t.icon}</span>${frappe.utils.escape_html(t.label)}
				</div>`
			);
		});
		$bar.find('.md-tab').on('click', (e) => {
			var key = $(e.currentTarget).data('tab');
			$bar.find('.md-tab').removeClass('active');
			$(e.currentTarget).addClass('active');
			this.$root.find('.md-tab-panel').removeClass('active');
			this.$root.find(`.md-tab-panel[data-panel="${key}"]`).addClass('active');
			if (key === 'live' && this.map) {
				setTimeout(() => this.map.invalidateSize(), 150);
			}
			if (key === 'timeline') {
				this.ensure_timeline_ready();
			}
		});
	}

	load_leaflet(done) {
		if (window.L) {
			this.leafletReady = true;
			done();
			return;
		}
		if (!$('link[data-md-leaflet]').length) {
			$('<link>', {
				rel: 'stylesheet',
				href: 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
				'data-md-leaflet': '1',
			}).appendTo('head');
		}
		var script = document.createElement('script');
		script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
		script.onload = () => {
			this.leafletReady = true;
			done();
		};
		document.head.appendChild(script);
	}

	init_map() {
		this.map = L.map('md-map', { zoomControl: false }).setView([18.5204, 73.8567], 11);
		L.control.zoom({ position: 'bottomright' }).addTo(this.map);

		this.tileStreets = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(this.map);
		this.tileSatellite = L.tileLayer(
			'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
			{ maxZoom: 19, attribution: 'Tiles © Esri' }
		);

		this.markersLayer = L.layerGroup().addTo(this.map);
	}

	// ---- data loading, mirrors services/api.js fetchManagerOverview -------

	async load_data() {
		try {
			var today = frappe.datetime.get_today();
			var start = today + ' 00:00:00';
			var end = today + ' 23:59:59';

			var [employees, checkins, pings, homes, leaves] = await Promise.all([
				frappe.db.get_list('Employee', {
					fields: ['name', 'employee_name', 'status', 'department', 'cell_number', 'attendance_device_id'],
					filters: [['status', '=', 'Active']],
					limit: 1000,
				}),
				frappe.db.get_list('Employee Checkin', {
					fields: ['employee', 'log_type', 'time'],
					filters: [['time', '>=', start], ['time', '<=', end]],
					order_by: 'time desc',
					limit: 5000,
				}),
				frappe.db.get_list('Location Ping', {
					fields: ['employee', FIELD_TIMESTAMP, 'latitude', 'longitude', FIELD_SPEED, FIELD_BATTERY],
					filters: [[FIELD_TIMESTAMP, '>=', start]],
					order_by: FIELD_TIMESTAMP + ' desc',
					limit: 5000,
				}).catch(() => []),
				frappe.db.get_list('Employee Home Location', {
					fields: ['employee', 'latitude', 'longitude', 'address'],
					limit: 1000,
				}).catch(() => []),
				frappe.db.get_list('Leave Application', {
					fields: ['employee', 'employee_name', 'leave_type', 'from_date', 'to_date'],
					filters: [['status', '=', 'Approved'], ['from_date', '<=', today], ['to_date', '>=', today]],
					limit: 500,
				}).catch(() => []),
			]);

			this.homeLocations = homes || [];
			this.offDuty = leaves || [];
			this.employees = this.compute_employees(employees || [], checkins || [], pings || []);
			this.$root.find('.md-updated-time').text(new Date().toLocaleTimeString());
			this.render_stats();
			this.render_attention();
			this.render_all_filtered();
			this.render_overview();
			if (this.timelineInitialized) {
				this.populate_timeline_employee_select();
				if (!this.timelineDataLoaded) this.load_timeline();
			}
			this.page.set_indicator('Live', 'green');
		} catch (e) {
			console.error('Manager Dashboard load failed:', e);
			this.page.set_indicator('Error', 'red');
		}
	}

	compute_employees(rawEmployees, checkins, pings) {
		var pingsByEmployee = {};
		pings.forEach((p) => {
			if (!pingsByEmployee[p.employee]) pingsByEmployee[p.employee] = [];
			pingsByEmployee[p.employee].push(p);
		});
		Object.keys(pingsByEmployee).forEach((k) =>
			pingsByEmployee[k].sort((a, b) => new Date(a[FIELD_TIMESTAMP]) - new Date(b[FIELD_TIMESTAMP]))
		);

		return rawEmployees.map((emp) => {
			var latestCheckin = checkins.find((c) => c.employee === emp.name);
			var isPunchedIn = latestCheckin ? latestCheckin.log_type === 'IN' : false;

			var empPings = pingsByEmployee[emp.name] || [];
			var latestPing = empPings.length ? empPings[empPings.length - 1] : null;
			var lat = latestPing ? Number(latestPing.latitude) : null;
			var lng = latestPing ? Number(latestPing.longitude) : null;

			var status = 'OFFLINE';
			var diffMins = null;
			if (latestPing) {
				diffMins = (Date.now() - new Date(latestPing[FIELD_TIMESTAMP]).getTime()) / 60000;
				if (diffMins > OFFLINE_AFTER_MINUTES) status = 'OFFLINE';
				else if ((latestPing[FIELD_SPEED] || 0) > 1) status = 'MOVING';
				else status = 'STOPPED';
			}

			var distanceMetersTotal = 0;
			for (var i = 1; i < empPings.length; i++) {
				distanceMetersTotal += haversine(
					Number(empPings[i - 1].latitude), Number(empPings[i - 1].longitude),
					Number(empPings[i].latitude), Number(empPings[i].longitude)
				);
			}
			var distanceKm = +(distanceMetersTotal / 1000).toFixed(2);

			var durationFormatted = '--';
			if (empPings.length >= 2) {
				var firstMs = new Date(empPings[0][FIELD_TIMESTAMP]).getTime();
				var lastMs = new Date(empPings[empPings.length - 1][FIELD_TIMESTAMP]).getTime();
				var totalMins = Math.floor((lastMs - firstMs) / 60000);
				durationFormatted = Math.floor(totalMins / 60) + 'h ' + (totalMins % 60) + 'm';
			}

			var pingWithBattery = [...empPings].reverse().find((p) => p[FIELD_BATTERY] != null);
			var batteryLevel = pingWithBattery ? Number(pingWithBattery[FIELD_BATTERY]) : null;
			var batteryStale = diffMins == null || diffMins > OFFLINE_AFTER_MINUTES;

			var currentAddress = this.resolve_address(lat, lng);

			// Punch location: address at the ping nearest to the punch time, not the
			// live/current position — a manager needs to see where someone actually
			// punched in/out, which can be hours (and places) apart from "now".
			var punchLat = null, punchLng = null;
			if (latestCheckin && empPings.length) {
				var punchMs = new Date(latestCheckin.time).getTime();
				var bestPing = null, bestDiff = Infinity;
				empPings.forEach((p) => {
					var diff = Math.abs(new Date(p[FIELD_TIMESTAMP]).getTime() - punchMs);
					if (diff < bestDiff) { bestDiff = diff; bestPing = p; }
				});
				if (bestPing && bestDiff <= 30 * 60000) {
					punchLat = Number(bestPing.latitude);
					punchLng = Number(bestPing.longitude);
				}
			}
			var punchAddress = latestCheckin ? this.resolve_address(punchLat, punchLng) : 'No punch record';

			return {
				employeeId: emp.name,
				employeeName: emp.employee_name || emp.name,
				department: (emp.department || '').split(' - ')[0] || 'Unassigned',
				cellNumber: emp.cell_number || '',
				deviceId: emp.attendance_device_id || '',
				status: status,
				isPunchedIn: isPunchedIn,
				punchTime: latestCheckin ? latestCheckin.time : null,
				punchAddress: punchAddress,
				punchLatitude: punchLat,
				punchLongitude: punchLng,
				lastPing: latestPing ? latestPing[FIELD_TIMESTAMP] : null,
				diffMins: diffMins,
				distanceKm: distanceKm,
				durationFormatted: durationFormatted,
				currentAddress: currentAddress,
				latitude: lat,
				longitude: lng,
				batteryLevel: batteryLevel,
				batteryStale: batteryStale,
			};
		});
	}

	// ---- reverse geocoding: turns lat/lng into a human-readable address --------
	// Cached per rounded coordinate and throttled to respect Nominatim's public
	// usage policy (max ~1 request/sec), so refreshes reuse resolved addresses
	// instead of re-geocoding unchanged positions every 10s.

	resolve_address(lat, lng) {
		if (lat == null || lng == null) return 'No location data';
		var cached = this.get_cached_address(lat, lng);
		if (cached) return cached;
		this.enqueue_geocode(lat, lng);
		return lat.toFixed(4) + ', ' + lng.toFixed(4);
	}

	get_cached_address(lat, lng) {
		return this.geocodeCache.get(geocode_key(lat, lng)) || null;
	}

	enqueue_geocode(lat, lng) {
		var key = geocode_key(lat, lng);
		if (this.geocodeCache.has(key) || this.geocodeQueued.has(key)) return;
		this.geocodeQueued.add(key);
		this.geocodeQueue.push({ key: key, lat: lat, lng: lng });
		this.drain_geocode_queue();
	}

	drain_geocode_queue() {
		if (this.geocodeDraining) return;
		this.geocodeDraining = true;
		var step = () => {
			var item = this.geocodeQueue.shift();
			if (!item) {
				this.geocodeDraining = false;
				return;
			}
			reverse_geocode(item.lat, item.lng).then((address) => {
				this.geocodeCache.set(item.key, address || 'Location unavailable');
				this.geocodeQueued.delete(item.key);
				this.schedule_geocode_refresh();
				setTimeout(step, 1100);
			});
		};
		step();
	}

	schedule_geocode_refresh() {
		if (this.geocodeRefreshTimer) return;
		this.geocodeRefreshTimer = setTimeout(() => {
			this.geocodeRefreshTimer = null;
			this.employees.forEach((e) => {
				if (e.latitude != null && e.longitude != null) {
					var cached = this.get_cached_address(e.latitude, e.longitude);
					if (cached) e.currentAddress = cached;
				}
				if (e.punchLatitude != null && e.punchLongitude != null) {
					var cachedPunch = this.get_cached_address(e.punchLatitude, e.punchLongitude);
					if (cachedPunch) e.punchAddress = cachedPunch;
				}
			});
			this.render_all_filtered();
			this.render_overview();
			if (this.currentTimelinePayload) this.render_timeline_payload(this.currentTimelinePayload);
		}, 1500);
	}

	// ---- rendering: stats / attention ---------------------------------------

	render_stats() {
		var moving = this.employees.filter((e) => e.status === 'MOVING').length;
		var stopped = this.employees.filter((e) => e.status === 'STOPPED').length;
		var offline = this.employees.filter((e) => e.status === 'OFFLINE').length;
		var totalKm = +this.employees.reduce((s, e) => s + (e.distanceKm || 0), 0).toFixed(2);

		this.$root.find('.md-v-active').text(this.employees.length);
		this.$root.find('.md-v-moving').text(moving);
		this.$root.find('.md-v-stopped').text(stopped);
		this.$root.find('.md-v-offline').text(offline);
		this.$root.find('.md-v-distance').text(totalKm);
	}

	render_attention() {
		var needsAttention = this.employees.filter((e) => {
			var offlineWhilePunchedIn = e.isPunchedIn && e.status === 'OFFLINE';
			var lowBattery = e.batteryLevel != null && !e.batteryStale && e.batteryLevel <= LOW_BATTERY_PERCENT;
			return offlineWhilePunchedIn || lowBattery;
		});

		var $box = this.$root.find('.md-attention');
		var $list = this.$root.find('.md-attention-list').empty();

		if (!needsAttention.length) {
			$box.removeClass('show');
			return;
		}
		$box.addClass('show');
		this.$root.find('.md-attention-count').text(needsAttention.length);

		needsAttention.forEach((e) => {
			var reason = e.isPunchedIn && e.status === 'OFFLINE'
				? 'Offline ' + Math.round(e.diffMins) + ' min'
				: 'Battery critical · ' + e.batteryLevel + '%';
			$list.append(
				$('<div class="md-attention-row">').append(
					$('<span class="name">').text(e.employeeName),
					$('<span class="reason">').text(reason)
				)
			);
		});
	}

	// ---- shared filtering ----------------------------------------------------

	get_visible_employees() {
		return this.employees.filter((e) => {
			if (this.punchFilter === 'IN' && !e.isPunchedIn) return false;
			if (this.punchFilter === 'OUT' && e.isPunchedIn) return false;
			if (this.statusFilter !== 'ALL' && e.status !== this.statusFilter) return false;
			if (this.batteryFilter !== 'ALL') {
				if (e.batteryLevel == null) return false;
				if (this.batteryFilter === 'LOW' && e.batteryLevel > LOW_BATTERY_PERCENT) return false;
				if (this.batteryFilter === 'MED' && (e.batteryLevel <= LOW_BATTERY_PERCENT || e.batteryLevel > 50)) return false;
				if (this.batteryFilter === 'GOOD' && e.batteryLevel <= 50) return false;
			}
			if (this.search) {
				var haystack = (e.employeeName + ' ' + e.cellNumber + ' ' + e.deviceId).toLowerCase();
				if (haystack.indexOf(this.search) === -1) return false;
			}
			return true;
		});
	}

	render_all_filtered() {
		this.render_map_and_list();
		this.render_card_view();
	}

	// ---- shared card markup ---------------------------------------------------

	build_employee_card_html(e) {
		var initials = (e.employeeName || '?').trim().split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase();
		var avatarColor = AVATAR_PALETTE[Math.abs(hash_code(e.employeeId)) % AVATAR_PALETTE.length];
		var batteryColor = e.batteryLevel == null || e.batteryStale
			? '#94a3b8'
			: e.batteryLevel <= 15 ? '#ef4444' : e.batteryLevel <= 30 ? '#f97316' : '#16a34a';
		var batteryPct = e.batteryLevel != null ? e.batteryLevel : 0;
		var batteryText = e.batteryLevel != null ? e.batteryLevel + '%' : '--';
		var gpsColor = e.status === 'OFFLINE' ? '#ef4444' : '#16a34a';
		var punchClass = e.isPunchedIn ? 'punch-in' : 'punch-out';
		var punchLabelClass = e.isPunchedIn ? 'in' : 'out';
		var punchLabel = format_punch_label(e.punchTime, e.isPunchedIn);

		return `
			<div class="md-emp-card ${punchClass}" data-employee="${frappe.utils.escape_html(e.employeeId)}">
				<div class="md-avatar" style="background:${avatarColor}">${frappe.utils.escape_html(initials)}</div>
				<div class="md-card-body">
					<div class="md-card-top">
						<div>
							<div class="md-card-name">${frappe.utils.escape_html(e.employeeName)}${e.deviceId ? ' <span class="device-id">(' + frappe.utils.escape_html(e.deviceId) + ')</span>' : ''}</div>
							${e.cellNumber ? '<div class="md-card-phone">' + frappe.utils.escape_html(e.cellNumber) + '</div>' : ''}
						</div>
						<div class="md-card-meta">
							<span class="md-meta-chip" style="color:${batteryColor}">
								<span class="md-battery-icon"><span style="width:${batteryPct}%;background:${batteryColor}"></span></span>${batteryText}
							</span>
							<span class="md-meta-chip" style="color:${gpsColor}">${ICON_PIN}</span>
						</div>
					</div>
					<div class="md-punch-row">
						<span class="md-punch-label ${punchLabelClass}">${punchLabel}</span>
						<button class="md-timeline-btn md-card-timeline-btn">Timeline ↗</button>
					</div>
					<div class="md-card-address"><span class="md-inline-pin">${ICON_PIN}</span> ${frappe.utils.escape_html(e.currentAddress)}</div>
					<div class="md-card-ago">${time_ago(e.lastPing)}</div>
				</div>
			</div>
		`;
	}

	bind_card_events($container) {
		$container.find('.md-emp-card').on('click', (e) => {
			frappe.set_route('Form', 'Employee', $(e.currentTarget).data('employee'));
		});
		$container.find('.md-card-timeline-btn').on('click', (ev) => {
			ev.stopPropagation();
			var employeeId = $(ev.currentTarget).closest('.md-emp-card').data('employee');
			frappe.set_route('List', 'Location Ping', { employee: employeeId });
		});
	}

	// ---- Live Location tab: map + sidebar list -------------------------------

	render_map_and_list() {
		var visible = this.get_visible_employees();

		this.$root.find('.md-emp-count').text(this.employees.length);
		this.$root.find('.md-pc-all').text(this.employees.length);
		this.$root.find('.md-pc-in').text(this.employees.filter((e) => e.isPunchedIn).length);
		this.$root.find('.md-pc-out').text(this.employees.filter((e) => !e.isPunchedIn).length);

		// --- map markers: colored + name-labeled by punch status ---
		if (this.markersLayer) {
			this.markersLayer.clearLayers();
			var bounds = [];
			var homesById = {};
			this.homeLocations.forEach((h) => (homesById[h.employee] = h));

			visible.forEach((e) => {
				var punchColor = e.isPunchedIn ? '#16a34a' : '#dc2626';
				if (e.latitude != null && e.longitude != null) {
					var icon = L.divIcon({
						className: '',
						html: `<div class="md-map-name-pin">
								<span class="md-map-name-dot" style="background:${punchColor}"></span>
								<span class="md-map-name-label" style="color:${punchColor}">${frappe.utils.escape_html(e.employeeName)}</span>
							</div>`,
						iconSize: [10, 10],
						iconAnchor: [5, 5],
					});
					var marker = L.marker([e.latitude, e.longitude], { icon: icon });
					marker.bindPopup(
						'<b>' + frappe.utils.escape_html(e.employeeName) + '</b><br>' + e.status +
						'<br>' + (e.isPunchedIn ? 'Punched In' : 'Punched Out')
					);
					this.markersLayer.addLayer(marker);
					bounds.push([e.latitude, e.longitude]);
				} else if (this.showSites && homesById[e.employeeId]) {
					var home = homesById[e.employeeId];
					var offlineIcon = L.divIcon({
						className: '',
						html: `<div class="md-map-name-pin">
								<span class="md-map-name-dot" style="background:${punchColor};opacity:.5"></span>
								<span class="md-map-name-label" style="color:${punchColor}">${frappe.utils.escape_html(e.employeeName)}</span>
							</div>`,
						iconSize: [10, 10],
						iconAnchor: [5, 5],
					});
					var m = L.marker([home.latitude, home.longitude], { icon: offlineIcon });
					m.bindPopup('<b>' + frappe.utils.escape_html(e.employeeName) + '</b><br>OFFLINE — last known (home) location');
					this.markersLayer.addLayer(m);
					bounds.push([home.latitude, home.longitude]);
				}
			});

			if (bounds.length === 1) this.map.setView(bounds[0], 14);
			else if (bounds.length > 1) this.map.fitBounds(bounds, { padding: [30, 30] });
			setTimeout(() => this.map.invalidateSize(), 200);
		}

		// --- sidebar list ---
		var $list = this.$root.find('.md-cardlist').empty();
		if (!visible.length) {
			$list.append('<div class="md-empty">No employees match this filter.</div>');
			return;
		}
		visible.forEach((e) => $list.append(this.build_employee_card_html(e)));
		this.bind_card_events($list);
	}

	// ---- Card View tab --------------------------------------------------------

	render_card_view() {
		var visible = this.get_visible_employees();

		this.$root.find('.md-cv-emp-count').text(this.employees.length);
		this.$root.find('.md-cv-pc-all').text(this.employees.length);
		this.$root.find('.md-cv-pc-in').text(this.employees.filter((e) => e.isPunchedIn).length);
		this.$root.find('.md-cv-pc-out').text(this.employees.filter((e) => !e.isPunchedIn).length);

		var $grid = this.$root.find('.md-cardview-grid').empty();
		if (!visible.length) {
			$grid.append('<div class="md-empty">No employees match this filter.</div>');
			return;
		}
		visible.forEach((e) => $grid.append(this.build_employee_card_html(e)));
		this.bind_card_events($grid);
	}

	// ---- Overview tab -----------------------------------------------------------

	render_overview() {
		var total = this.employees.length;
		var inCount = this.employees.filter((e) => e.isPunchedIn).length;
		var outCount = total - inCount;
		var inactiveCount = this.employees.filter((e) => e.isPunchedIn && e.status === 'OFFLINE').length;
		var inPct = total ? Math.round((inCount / total) * 100) : 0;

		this.$root.find('.md-ov-in-count').text(inCount);
		this.$root.find('.md-ov-out-count').text(outCount);
		this.$root.find('.md-ov-total').text(total);
		this.$root.find('.md-ov-inactive').text(inactiveCount);
		this.$root.find('.md-ov-strength').text(inCount + ' / ' + total);
		this.$root.find('.md-gauge').css('background', `conic-gradient(#16a34a 0% ${inPct}%, #dc2626 ${inPct}% 100%)`);

		// Teamwise attendance — grouped by Employee.department (existing HRMS field)
		var byTeam = {};
		this.employees.forEach((e) => {
			if (!byTeam[e.department]) byTeam[e.department] = { in: 0, out: 0 };
			if (e.isPunchedIn) byTeam[e.department].in++;
			else byTeam[e.department].out++;
		});
		var $teams = this.$root.find('.md-ov-teams-list').empty();
		Object.keys(byTeam).sort().forEach((team) => {
			$teams.append(`
				<div class="md-ov-team-row">
					<span>${frappe.utils.escape_html(team)}</span>
					<span class="md-ov-team-counts"><span class="g">● ${byTeam[team].in}</span><span class="r">● ${byTeam[team].out}</span></span>
				</div>
			`);
		});

		this.render_overview_employee_table();
		this.render_overview_offduty_table();
	}

	render_overview_employee_table() {
		var filterVal = this.$root.find('.md-ov-emp-filter').val() || 'ALL';
		var searchVal = (this.$root.find('.md-ov-emp-search').val() || '').trim().toLowerCase();

		var rows = this.employees.filter((e) => {
			if (filterVal === 'IN' && !e.isPunchedIn) return false;
			if (filterVal === 'OUT' && e.isPunchedIn) return false;
			if (searchVal && e.employeeName.toLowerCase().indexOf(searchVal) === -1) return false;
			return true;
		});

		this.$root.find('.md-ov-emp-total').text(this.employees.length);
		var $body = this.$root.find('.md-ov-emp-body').empty();
		if (!rows.length) {
			$body.append('<tr><td colspan="4" style="text-align:center;color:#94a3b8;padding:16px;">No data found</td></tr>');
			return;
		}
		rows.forEach((e) => {
			var initials = (e.employeeName || '?').trim().split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase();
			var avatarColor = AVATAR_PALETTE[Math.abs(hash_code(e.employeeId)) % AVATAR_PALETTE.length];
			var punchColor = e.isPunchedIn ? '#15803d' : '#b91c1c';
			$body.append(`
				<tr>
					<td><div class="md-ov-emp-cell">
						<div class="md-avatar" style="width:26px;height:26px;font-size:10px;background:${avatarColor}">${frappe.utils.escape_html(initials)}</div>
						<span class="md-ov-emp-name">${frappe.utils.escape_html(e.employeeName)}</span>
					</div></td>
					<td><span style="color:${punchColor};font-weight:700">${format_punch_label(e.punchTime, e.isPunchedIn)}</span></td>
					<td>${frappe.utils.escape_html(e.punchAddress)}</td>
					<td>${frappe.utils.escape_html(e.currentAddress)}<br><span style="color:#94a3b8">${time_ago(e.lastPing)}</span></td>
				</tr>
			`);
		});
	}

	render_overview_offduty_table() {
		var searchVal = (this.$root.find('.md-ov-offduty-search').val() || '').trim().toLowerCase();
		var deptById = {};
		this.employees.forEach((e) => (deptById[e.employeeId] = e.department));

		var rows = this.offDuty.filter((l) => {
			if (searchVal && (l.employee_name || '').toLowerCase().indexOf(searchVal) === -1) return false;
			return true;
		});

		this.$root.find('.md-ov-offduty-total').text(this.offDuty.length);
		var $body = this.$root.find('.md-ov-offduty-body').empty();
		if (!rows.length) {
			$body.append('<tr><td colspan="3" style="text-align:center;color:#94a3b8;padding:16px;">No data found</td></tr>');
			return;
		}
		rows.forEach((l) => {
			$body.append(`
				<tr>
					<td>${frappe.utils.escape_html(l.employee_name || l.employee)}</td>
					<td>${frappe.utils.escape_html(deptById[l.employee] || '—')}</td>
					<td>${frappe.utils.escape_html(l.leave_type || 'On Leave')}</td>
				</tr>
			`);
		});
	}

	export_attendance_csv() {
		var header = ['Employee', 'Department', 'Punch Status', 'Last Punch', 'Punch Location', 'Last Location'];
		var rows = this.employees.map((e) => [
			e.employeeName,
			e.department,
			e.isPunchedIn ? 'Punched In' : 'Punched Out',
			format_punch_label(e.punchTime, e.isPunchedIn),
			e.punchAddress,
			e.currentAddress,
		]);
		var csv = [header].concat(rows).map((r) => r.map((v) => '"' + String(v || '').replace(/"/g, '""') + '"').join(',')).join('\n');
		var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
		var link = document.createElement('a');
		link.href = URL.createObjectURL(blob);
		link.download = 'attendance-status-' + frappe.datetime.get_today() + '.csv';
		link.click();
	}

	// ---- Timeline tab -----------------------------------------------------------
	// Merges Employee Checkin (punches) with Trip / Trip Stop (halts — an existing
	// doctype already shaped exactly like a stay-point: address, start/end time,
	// distance, avg speed) and Location Ping (raw GPS trail + travel-distance
	// fallback when a day has no Trip records yet).

	ensure_timeline_ready() {
		if (!this.timelineInitialized) {
			this.timelineInitialized = true;
			this.$root.find('.md-tl-date-input').val(this.timelineDate);
			this.populate_timeline_employee_select();
			this.load_leaflet(() => {
				this.init_timeline_map();
				this.load_timeline();
			});
		} else if (this.timelineMap) {
			setTimeout(() => this.timelineMap.invalidateSize(), 150);
		}
	}

	populate_timeline_employee_select() {
		var $select = this.$root.find('.md-tl-emp-select').empty();
		this.employees.forEach((e) => {
			$select.append(`<option value="${frappe.utils.escape_html(e.employeeId)}">${frappe.utils.escape_html(e.employeeName)}</option>`);
		});
		if (!this.timelineEmployeeId && this.employees.length) this.timelineEmployeeId = this.employees[0].employeeId;
		$select.val(this.timelineEmployeeId);
		$select.off('change').on('change', (e) => {
			this.timelineEmployeeId = $(e.currentTarget).val();
		});
	}

	shift_timeline_date(days) {
		var current = this.$root.find('.md-tl-date-input').val() || this.timelineDate;
		var d = new Date(current + 'T00:00:00');
		d.setDate(d.getDate() + days);
		var pad = (n) => String(n).padStart(2, '0');
		this.timelineDate = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
		this.$root.find('.md-tl-date-input').val(this.timelineDate);
		this.load_timeline();
	}

	init_timeline_map() {
		this.timelineMap = L.map('md-timeline-map', { zoomControl: false }).setView([18.5204, 73.8567], 12);
		L.control.zoom({ position: 'bottomright' }).addTo(this.timelineMap);

		this.timelineTileStreets = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(this.timelineMap);
		this.timelineTileSatellite = L.tileLayer(
			'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
			{ maxZoom: 19, attribution: 'Tiles © Esri' }
		);

		this.timelineMarkersLayer = L.layerGroup().addTo(this.timelineMap);
	}

	async load_timeline() {
		var employeeId = this.$root.find('.md-tl-emp-select').val() || this.timelineEmployeeId;
		var date = this.$root.find('.md-tl-date-input').val() || this.timelineDate;
		if (!employeeId) return;
		this.timelineEmployeeId = employeeId;
		this.timelineDate = date;

		var dayStart = date + ' 00:00:00';
		var dayEnd = date + ' 23:59:59';
		var isToday = date === frappe.datetime.get_today();

		this.$root.find('.md-tl-events').html('<div class="md-tl-empty">Loading…</div>');

		try {
			// Employee Timeline is a per-employee-per-day cache: once a past day is
			// computed once, re-opening it is a single read instead of re-querying
			// Checkin/Trip/Trip Stop/Location Ping again. Today is always recomputed
			// since its data is still coming in throughout the day.
			var cachedRows = await frappe.db.get_list('Employee Timeline', {
				fields: ['name', 'attendance_status', 'attendance_hours', 'time_tracked_hours', 'gps_distance_km', 'activities_count', 'gps_quality', 'events_json'],
				filters: [['employee', '=', employeeId], ['date', '=', date]],
				limit: 1,
			}).catch(() => []);
			var cached = cachedRows[0] || null;

			if (cached && !isToday && cached.events_json) {
				try {
					var parsed = JSON.parse(cached.events_json);
					this.render_timeline_payload({
						attendanceStatus: cached.attendance_status,
						attendanceHours: cached.attendance_hours,
						timeTrackedHours: cached.time_tracked_hours,
						gpsDistanceKm: cached.gps_distance_km,
						activitiesCount: cached.activities_count,
						gpsQuality: cached.gps_quality,
						events: parsed.events || [],
						pings: parsed.pings || [],
					});
					return;
				} catch (parseErr) {
					console.error('Employee Timeline cache was unreadable, recomputing:', parseErr);
				}
			}

			var [checkins, trips, pings] = await Promise.all([
				frappe.db.get_list('Employee Checkin', {
					fields: ['log_type', 'time'],
					filters: [['employee', '=', employeeId], ['time', '>=', dayStart], ['time', '<=', dayEnd]],
					order_by: 'time asc',
					limit: 50,
				}),
				quiet_get_list('Trip', {
					fields: ['name', 'start_time', 'end_time', 'total_distance_km', 'total_duration_minutes', 'total_halt_minutes'],
					filters: [['employee', '=', employeeId], ['start_time', '>=', dayStart], ['start_time', '<=', dayEnd]],
					order_by: 'start_time asc',
					limit: 20,
				}),
				frappe.db.get_list('Location Ping', {
					fields: ['timestamp', 'latitude', 'longitude', 'speed', 'battery', 'source'],
					filters: [['employee', '=', employeeId], ['timestamp', '>=', dayStart], ['timestamp', '<=', dayEnd]],
					order_by: 'timestamp asc',
					limit: 3000,
				}).catch(() => []),
			]);

			var tripIds = trips.map((t) => t.name);
			var stops = [];
			if (tripIds.length) {
				stops = await quiet_get_list('Trip Stop', {
					fields: ['trip', 'stop_type', 'title', 'address', 'start_time', 'end_time', 'duration_minutes', 'distance_km', 'avg_speed_kmh', 'latitude', 'longitude'],
					filters: [['trip', 'in', tripIds]],
					order_by: 'start_time asc',
					limit: 200,
				});
			}

			var payload = this.compute_timeline_payload(checkins || [], trips || [], stops || [], pings || []);
			this.render_timeline_payload(payload);
			this.save_employee_timeline(employeeId, date, payload, cached ? cached.name : null);
		} catch (e) {
			console.error('Timeline load failed:', e);
			this.$root.find('.md-tl-events').html('<div class="md-tl-empty">Could not load timeline.</div>');
		}
	}

	compute_timeline_payload(checkins, trips, stops, pings) {
		var halts = stops.filter((s) => s.stop_type === 'halted');

		var firstIn = checkins.find((c) => c.log_type === 'IN');
		var lastOut = [...checkins].reverse().find((c) => c.log_type === 'OUT');
		var attendanceStatus = checkins.length ? 'Present' : '-';
		var attendanceHours = firstIn && lastOut ? (new Date(lastOut.time) - new Date(firstIn.time)) / 3600000 : null;

		var tripDistanceKm = trips.reduce((s, t) => s + (t.total_distance_km || 0), 0);
		var tripDurationMin = trips.reduce((s, t) => s + (t.total_duration_minutes || 0), 0);
		var pingDistanceKm = 0;
		for (var i = 1; i < pings.length; i++) {
			pingDistanceKm += haversine(
				Number(pings[i - 1].latitude), Number(pings[i - 1].longitude),
				Number(pings[i].latitude), Number(pings[i].longitude)
			) / 1000;
		}
		var pingDurationMin = pings.length >= 2
			? (new Date(pings[pings.length - 1].timestamp) - new Date(pings[0].timestamp)) / 60000
			: 0;

		var timeTrackedHours = (tripDurationMin || pingDurationMin) ? (tripDurationMin || pingDurationMin) / 60 : null;
		var gpsDistanceKm = (tripDistanceKm || pingDistanceKm) || null;
		var avgGapMin = pings.length >= 2 ? pingDurationMin / (pings.length - 1) : null;
		var gpsQuality = avgGapMin == null ? null : (avgGapMin <= 6 ? 'Good' : 'Poor');

		var nearest_ping = (time) => {
			var t = new Date(time).getTime();
			var best = null, bestDiff = Infinity;
			pings.forEach((p) => {
				var diff = Math.abs(new Date(p.timestamp).getTime() - t);
				if (diff < bestDiff) { bestDiff = diff; best = p; }
			});
			return bestDiff <= 10 * 60000 ? best : null;
		};

		var events = [];
		checkins.forEach((c) => {
			var ping = nearest_ping(c.time);
			events.push({
				kind: c.log_type === 'IN' ? 'in' : 'out',
				time: c.time,
				battery: ping && ping.battery != null ? ping.battery : null,
				source: ping ? ping.source : null,
				lat: ping ? Number(ping.latitude) : null,
				lng: ping ? Number(ping.longitude) : null,
			});
		});
		halts.forEach((h) => {
			var ping = nearest_ping(h.start_time);
			events.push({
				kind: 'halt',
				time: h.start_time,
				battery: ping && ping.battery != null ? ping.battery : null,
				address: h.address || 'Halt',
				durationMinutes: h.duration_minutes || null,
				lat: h.latitude != null ? Number(h.latitude) : null,
				lng: h.longitude != null ? Number(h.longitude) : null,
			});
		});
		events.sort((a, b) => new Date(a.time) - new Date(b.time));

		var pingsLite = pings.map((p) => ({ t: p.timestamp, lat: Number(p.latitude), lng: Number(p.longitude) }));

		return {
			attendanceStatus: attendanceStatus,
			attendanceHours: attendanceHours,
			timeTrackedHours: timeTrackedHours,
			gpsDistanceKm: gpsDistanceKm,
			activitiesCount: halts.length,
			gpsQuality: gpsQuality,
			events: events,
			pings: pingsLite,
		};
	}

	async save_employee_timeline(employeeId, date, payload, existingName) {
		var values = {
			employee: employeeId,
			date: date,
			attendance_status: payload.attendanceStatus || '',
			attendance_hours: payload.attendanceHours || 0,
			time_tracked_hours: payload.timeTrackedHours || 0,
			gps_distance_km: payload.gpsDistanceKm || 0,
			activities_count: payload.activitiesCount || 0,
			gps_quality: payload.gpsQuality || '',
			events_json: JSON.stringify({ events: payload.events, pings: payload.pings }),
		};
		try {
			if (existingName) {
				await frappe.db.set_value('Employee Timeline', existingName, values);
			} else {
				await frappe.db.insert(Object.assign({ doctype: 'Employee Timeline' }, values));
			}
		} catch (e) {
			console.error('Could not cache Employee Timeline:', e);
		}
	}

	render_timeline_payload(payload) {
		this.timelineDataLoaded = true;
		this.currentTimelinePayload = payload;
		var events = payload.events || [];
		var pings = payload.pings || [];

		// Halts already carry a real address from Trip Stop. Punches only have
		// lat/lng from the nearest ping, so reverse-geocode those the same way
		// Live Location does (cached + throttled) and let schedule_geocode_refresh
		// re-render this payload once resolved.
		events.forEach((ev) => {
			if (ev.address || ev.lat == null || ev.lng == null) return;
			var cachedAddr = this.get_cached_address(ev.lat, ev.lng);
			if (cachedAddr) ev.address = cachedAddr;
			else this.enqueue_geocode(ev.lat, ev.lng);
		});

		this.$root.find('.md-tl-att-status').text(payload.attendanceStatus || '-');
		this.$root.find('.md-tl-att-hours').text(payload.attendanceHours != null ? format_hm_from_minutes(payload.attendanceHours * 60) : '-');
		this.$root.find('.md-tl-time-tracked').text(payload.timeTrackedHours != null ? format_hm_from_minutes(payload.timeTrackedHours * 60) : '-');
		this.$root.find('.md-tl-gps-distance').text(payload.gpsDistanceKm != null ? Number(payload.gpsDistanceKm).toFixed(2) + ' KM' : '-');
		this.$root.find('.md-tl-activities').text(payload.activitiesCount != null ? payload.activitiesCount : '0');

		var $loc = this.$root.find('.md-tl-location-setting');
		if (!payload.gpsQuality) {
			$loc.removeClass('good poor').text('Location Setting : —');
		} else if (payload.gpsQuality === 'Good') {
			$loc.removeClass('poor').addClass('good').text('Location Setting : Good');
		} else {
			$loc.removeClass('good').addClass('poor').text('Location Setting : Poor');
		}

		var $events = this.$root.find('.md-tl-events').empty();
		if (!events.length) {
			$events.append('<div class="md-tl-empty">No activity recorded for this day.</div>');
		}

		var num = 1;
		var prevTime = null;
		events.forEach((ev, idx) => {
			if (prevTime != null) {
				var travelKm = 0;
				for (var i = 1; i < pings.length; i++) {
					var t = new Date(pings[i].t).getTime();
					if (t > prevTime && t <= new Date(ev.time).getTime()) {
						travelKm += haversine(pings[i - 1].lat, pings[i - 1].lng, pings[i].lat, pings[i].lng) / 1000;
					}
				}
				if (travelKm > 0.02) {
					$events.append(`<div class="md-tl-travel-row">↝ Travel: ${travelKm.toFixed(2)} KM</div>`);
				}
			}

			var batteryHtml = ev.battery != null
				? `<span class="md-tl-event-battery" style="color:${ev.battery <= 15 ? '#ef4444' : ev.battery <= 30 ? '#f97316' : '#16a34a'}">
					<span class="md-battery-icon"><span style="width:${ev.battery}%;background:currentColor"></span></span>${ev.battery}%</span>`
				: '';
			var gapLabel = idx === 0 ? '' : format_gap_since(events[0].time, ev.time);
			var addressText = ev.address || (ev.lat != null && ev.lng != null ? ev.lat.toFixed(4) + ', ' + ev.lng.toFixed(4) : 'No location data');

			if (ev.kind === 'halt') {
				$events.append(`
					<div class="md-tl-event">
						<div class="md-tl-event-num halt">${num}</div>
						<div class="md-tl-event-body">
							<div class="md-tl-event-top">
								<span class="md-tl-event-time">${format_time_12h(ev.time)}${gapLabel ? '<span class="md-tl-event-gap">(' + gapLabel + ')</span>' : ''}</span>
								${batteryHtml}
							</div>
							<div class="md-tl-event-address">${frappe.utils.escape_html(addressText)}</div>
							${ev.durationMinutes ? '<div class="md-tl-event-sub">Halted for ' + format_hm_from_minutes(ev.durationMinutes) + '</div>' : ''}
						</div>
					</div>
				`);
			} else {
				var isIn = ev.kind === 'in';
				$events.append(`
					<div class="md-tl-event">
						<div class="md-tl-event-num ${isIn ? 'in' : 'out'}">${num}</div>
						<div class="md-tl-event-body">
							<div class="md-tl-event-top">
								<span class="md-tl-event-time">${isIn ? 'Punch In' : 'Punch Out'}${gapLabel ? '<span class="md-tl-event-gap">(' + gapLabel + ')</span>' : ''}</span>
								${batteryHtml}
							</div>
							<div class="md-tl-event-address">${frappe.utils.escape_html(addressText)}</div>
							<div class="md-tl-event-sub"><span class="tag">${ev.source || 'App'}</span> ${format_time_12h(ev.time)}</div>
						</div>
					</div>
				`);
			}
			num++;
			prevTime = new Date(ev.time).getTime();
		});

		this.render_timeline_map(events, pings);
	}

	render_timeline_map(events, pings) {
		if (!this.timelineMarkersLayer) return;
		this.timelineMarkersLayer.clearLayers();
		var bounds = [];

		if (pings.length > 1) {
			var latlngs = pings.map((p) => [p.lat, p.lng]);
			L.polyline(latlngs, { color: '#16a34a', weight: 3, opacity: 0.8 }).addTo(this.timelineMarkersLayer);
			bounds = bounds.concat(latlngs);
		}

		var num = 1;
		events.forEach((ev) => {
			if (ev.lat == null || ev.lng == null) {
				num++;
				return;
			}
			var color = ev.kind === 'in' ? '#16a34a' : ev.kind === 'out' ? '#dc2626' : '#2563eb';
			var icon = L.divIcon({
				className: '',
				html: `<div style="width:24px;height:24px;border-radius:50%;background:${color};color:#fff;font-size:11px;font-weight:800;
						display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 0 6px rgba(0,0,0,.4);">${num}</div>`,
				iconSize: [24, 24],
				iconAnchor: [12, 12],
			});
			L.marker([ev.lat, ev.lng], { icon: icon }).addTo(this.timelineMarkersLayer);
			bounds.push([ev.lat, ev.lng]);
			num++;
		});

		if (bounds.length === 1) this.timelineMap.setView(bounds[0], 14);
		else if (bounds.length > 1) this.timelineMap.fitBounds(bounds, { padding: [30, 30] });
		setTimeout(() => this.timelineMap.invalidateSize(), 200);
	}
}

// ---- small helpers ----------------------------------------------------------

function haversine(lat1, lon1, lat2, lon2) {
	var R = 6371000;
	var toRad = (d) => (d * Math.PI) / 180;
	var dLat = toRad(lat2 - lat1);
	var dLon = toRad(lon2 - lon1);
	var a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
	return 2 * R * Math.asin(Math.sqrt(a));
}

function time_ago(iso) {
	if (!iso) return 'no data yet';
	var diffMs = Date.now() - new Date(iso).getTime();
	if (!isFinite(diffMs) || diffMs < 0) return 'just now';
	var mins = Math.floor(diffMs / 60000);
	if (mins < 1) return 'just now';
	if (mins < 60) return mins + ' min ago';
	var hrs = Math.floor(mins / 60);
	if (hrs < 24) return hrs + ' hr' + (hrs === 1 ? '' : 's') + ' ago';
	return Math.floor(hrs / 24) + ' day(s) ago';
}

function format_punch_label(iso, isPunchedIn) {
	if (!iso) return isPunchedIn ? 'Punched IN' : 'Never Punched In';
	var d = new Date(iso);
	var now = new Date();
	var startOfDay = (dt) => new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()).getTime();
	var diffDays = Math.round((startOfDay(now) - startOfDay(d)) / 86400000);
	var timeStr = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

	var dayStr;
	if (diffDays === 0) dayStr = 'Today';
	else if (diffDays === 1) dayStr = 'Yesterday';
	else if (diffDays > 1 && diffDays < 7) dayStr = 'Last ' + d.toLocaleDateString([], { weekday: 'long' });
	else dayStr = d.toLocaleDateString([], { day: 'numeric', month: 'short' });

	return (isPunchedIn ? 'Punched IN : ' : 'Punched OUT : ') + dayStr + ' at ' + timeStr;
}

// Like frappe.db.get_list, but never pops Frappe's default error dialog and
// always resolves (to []) even if the server rejects the query — used for
// Trip/Trip Stop, which are optional/best-effort inputs to the Timeline tab.
function quiet_get_list(doctype, args) {
	return new Promise((resolve) => {
		var callArgs = Object.assign({ doctype: doctype }, args);
		frappe.call({
			method: 'frappe.desk.reportview.get_list',
			args: callArgs,
			type: 'GET',
			silent: true,
			callback: (r) => resolve((r && r.message) || []),
			error: () => resolve([]),
		});
	});
}

function geocode_key(lat, lng) {
	return lat.toFixed(4) + ',' + lng.toFixed(4);
}

function reverse_geocode(lat, lng) {
	var url = 'https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=' + lat + '&lon=' + lng + '&zoom=16&addressdetails=0';
	return fetch(url, { headers: { Accept: 'application/json' } })
		.then((res) => (res.ok ? res.json() : null))
		.then((data) => (data && data.display_name ? data.display_name : null))
		.catch(() => null);
}

function format_time_12h(iso) {
	return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function format_hm_from_minutes(totalMins) {
	totalMins = Math.max(0, Math.round(totalMins));
	var h = Math.floor(totalMins / 60);
	var m = totalMins % 60;
	return h ? h + 'h ' + m + 'm' : m + 'm';
}

function format_gap_since(firstIso, thisIso) {
	var mins = Math.max(0, Math.round((new Date(thisIso) - new Date(firstIso)) / 60000));
	var h = Math.floor(mins / 60);
	var m = mins % 60;
	return h + 'h ' + m + 'm';
}

function hash_code(str) {
	var h = 0;
	for (var i = 0; i < (str || '').length; i++) {
		h = (h << 5) - h + str.charCodeAt(i);
		h |= 0;
	}
	return h;
}
