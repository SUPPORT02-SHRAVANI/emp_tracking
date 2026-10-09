// NOC Dashboard — Frappe Desk page
// Route: /app/noc-dashboard
//
// Two sections on one page, both built from Complaint Information:
//   1. Complaints Overview — open complaints right now (noc_dashboard.py `get_dashboard_data`)
//   2. Employee Sheet — one employee's month, day by day (noc_dashboard.py `get_employee_sheet`)
// All counting happens in Python; this file only draws.

frappe.pages['noc-dashboard'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('NOC Dashboard'),
		single_column: true,
	});

	new NocDashboard(page);
};

var NOC_REFRESH_INTERVAL_MS = 60000;
var NOC_METHOD = 'emp_tracking.emp_tracking.page.noc_dashboard.noc_dashboard.';

// Same visual language as the Manager Dashboard (md-*) and Workforce Dashboards (wd-*) pages:
// white cards, slate text, coloured top borders on stat tiles, uppercase table headers.
var NOC_STYLE = [
	'<style>',
	'.noc-root{padding:12px 16px 28px}',
	'@media (max-width:480px){.noc-root{padding:10px 12px 24px}}',
	// section head
	'.noc-head{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;margin:26px 0 16px}',
	'.noc-head:first-child{margin-top:6px}',
	'.noc-title{font-size:16px;font-weight:800;color:#0f172a;line-height:1.2}',
	'.noc-sub{font-size:12px;color:#64748b;margin-top:2px}',
	'.noc-head-right{display:flex;align-items:flex-end;gap:10px;flex-wrap:wrap}',
	'.noc-badge{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:700;color:#475569;background:#fff;',
	'  border:1px solid #e2e8f0;border-radius:8px;padding:6px 10px;white-space:nowrap}',
	'.noc-badge .dot{width:7px;height:7px;border-radius:50%;background:#16a34a}',
	'.noc-filters{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end}',
	'.noc-filters .frappe-control{margin:0;min-width:180px}',
	'.noc-filters .form-group{margin:0}',
	'.noc-filters .control-label{font-size:9.5px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.02em;margin-bottom:3px}',
	// stat tiles
	'.noc-kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(178px,1fr));gap:12px;margin-bottom:18px}',
	'.noc-kpi{background:#fff;border:1px solid #e5e7eb;border-top:3px solid #2563eb;border-radius:12px;padding:13px 14px;',
	'  display:flex;align-items:center;gap:12px;box-shadow:0 1px 2px rgba(15,23,42,.04);transition:box-shadow .15s,transform .15s;min-width:0}',
	'.noc-kpi.clickable{cursor:pointer}',
	'.noc-kpi.clickable:hover{box-shadow:0 4px 10px rgba(15,23,42,.08);transform:translateY(-1px)}',
	'.noc-kpi-icon{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;',
	'  background:#eff6ff;color:#2563eb}',
	'.noc-kpi-body{min-width:0;flex:1}',
	'.noc-kpi .val{font-size:19px;font-weight:800;color:#0f172a;line-height:1.15;font-variant-numeric:tabular-nums;white-space:nowrap}',
	'.noc-kpi .lbl{font-size:10.5px;color:#64748b;margin-top:2px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
	'.noc-kpi .hint{font-size:10.5px;color:#94a3b8;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
	'.noc-kpi.t-blue{border-top-color:#2563eb}.noc-kpi.t-blue .noc-kpi-icon{background:#eff6ff;color:#2563eb}',
	'.noc-kpi.t-green{border-top-color:#16a34a}.noc-kpi.t-green .noc-kpi-icon{background:#f0fdf4;color:#16a34a}.noc-kpi.t-green .val{color:#16a34a}',
	'.noc-kpi.t-orange{border-top-color:#f97316}.noc-kpi.t-orange .noc-kpi-icon{background:#fff7ed;color:#f97316}.noc-kpi.t-orange .val{color:#f97316}',
	'.noc-kpi.t-red{border-top-color:#ef4444}.noc-kpi.t-red .noc-kpi-icon{background:#fef2f2;color:#ef4444}.noc-kpi.t-red .val{color:#ef4444}',
	'.noc-kpi.t-purple{border-top-color:#7c3aed}.noc-kpi.t-purple .noc-kpi-icon{background:#f5f3ff;color:#7c3aed}.noc-kpi.t-purple .val{color:#7c3aed}',
	// cards
	'.noc-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px;align-items:stretch}',
	'.noc-grid>.noc-card{grid-column:span 4}',
	'@media (max-width:1100px){.noc-grid>.noc-card{grid-column:span 6}}',
	'@media (max-width:767px){.noc-grid>.noc-card{grid-column:span 12}}',
	'.noc-card{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:14px 16px;min-width:0;display:flex;flex-direction:column;',
	'  box-shadow:0 1px 2px rgba(15,23,42,.04)}',
	'.noc-card-head{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:12px;min-height:26px}',
	'.noc-card-head .title{font-size:13.5px;font-weight:800;color:#0f172a;display:flex;align-items:center;gap:10px}',
	'.noc-card-head .count{color:#64748b;font-weight:700}',
	'.noc-card-head .sub{font-size:11px;color:#94a3b8;font-weight:600}',
	'.noc-group{display:flex;justify-content:space-between;font-size:10.5px;text-transform:uppercase;letter-spacing:.03em;color:#94a3b8;',
	'  font-weight:700;padding:10px 0 4px;border-bottom:1px solid #f1f5f9}',
	'.noc-group:first-of-type{padding-top:0}',
	// bars
	'.noc-bar{padding:7px 0;border-bottom:1px solid #f8fafc}',
	'.noc-bar:last-child{border-bottom:0}',
	'.noc-bar .line{display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:12.5px;font-weight:600;color:#334155;margin-bottom:5px}',
	'.noc-bar .line .name{display:flex;align-items:center;gap:8px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
	'.noc-bar .line .num{display:flex;align-items:center;gap:8px;font-weight:800;color:#0f172a;font-variant-numeric:tabular-nums;white-space:nowrap}',
	'.noc-bar .track{height:7px;border-radius:4px;background:#f1f5f9}',
	'.noc-bar .fill{height:7px;border-radius:4px;min-width:3px;background:#2563eb}',
	'.noc-bar .fill.warn{background:#f97316}.noc-bar .fill.bad{background:#ef4444}.noc-bar .fill.ok{background:#16a34a}',
	'.noc-avatar{width:26px;height:26px;border-radius:13px;display:inline-flex;align-items:center;justify-content:center;color:#fff;font-weight:800;',
	'  font-size:10.5px;flex-shrink:0}',
	'.noc-avatar.lg{width:42px;height:42px;border-radius:21px;font-size:14px}',
	'.noc-chip{display:inline-block;font-size:10.5px;font-weight:700;padding:3px 9px;border-radius:20px;white-space:nowrap;line-height:1.4}',
	'.noc-chip.red{color:#b91c1c;background:#fee2e2}.noc-chip.orange{color:#c2410c;background:#ffedd5}',
	'.noc-empty{text-align:center;padding:30px 14px;color:#94a3b8;font-size:12.5px}',
	'.noc-loading{padding:60px 0;text-align:center;color:#94a3b8;font-size:13px}',
	// employee sheet
	'.noc-person{display:flex;gap:12px;align-items:center}',
	'.noc-person .name{font-weight:800;font-size:13.5px;color:#0f172a}',
	'.noc-person .meta{font-size:11.5px;color:#64748b;margin-top:2px}',
	'.noc-table-wrap{overflow:auto;max-height:520px}',
	'.noc-table{width:100%;border-collapse:separate;border-spacing:0}',
	'.noc-table thead th{position:sticky;top:0;background:#fff;text-align:right;font-size:10.5px;text-transform:uppercase;letter-spacing:.03em;',
	'  color:#94a3b8;font-weight:700;padding:6px 10px;border-bottom:1px solid #f1f5f9;white-space:nowrap;z-index:1}',
	'.noc-table tr.groups th{text-align:center;color:#64748b;border-bottom:0;padding-bottom:0}',
	'.noc-table tr.cols th{top:22px}',
	'.noc-table tbody td{padding:8px 10px;font-size:12px;color:#334155;border-bottom:1px solid #f8fafc;text-align:right;white-space:nowrap;',
	'  font-variant-numeric:tabular-nums}',
	'.noc-table th:first-child,.noc-table td:first-child{text-align:left}',
	'.noc-table td:first-child{font-weight:700;color:#0f172a}',
	'.noc-table .split{border-left:1px solid #f1f5f9}',
	'.noc-table td.zero{color:#cbd5e1}',
	'.noc-table td .day{color:#94a3b8;font-size:10.5px;font-weight:600;margin-left:6px}',
	'.noc-table tr.off td{background:#f8fafc}',
	'.noc-table tr.today td:first-child{color:#2563eb;box-shadow:inset 3px 0 0 #2563eb}',
	'.noc-table tbody tr:hover td{background:#f8fafc}',
	'.noc-table tr.total td{position:sticky;bottom:0;background:#f8fafc;font-weight:800;color:#0f172a;border-top:1px solid #e5e7eb;border-bottom:0}',
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

var NOC_LAYOUT = [
	'<div class="noc-root">',
	'<div class="noc-head"><div><div class="noc-title">' + __('Complaints Overview') + '</div>',
	'<div class="noc-sub">' + __('Open complaints right now') + '</div></div>',
	'<div class="noc-head-right"><div class="noc-filters" data-slot="overview-filters"></div>',
	'<span class="noc-badge"><span class="dot"></span><span data-slot="updated">' + __('Loading…') + '</span></span></div></div>',
	'<div data-slot="overview"></div>',
	'<div class="noc-head"><div><div class="noc-title">' + __('Employee Sheet') + '</div>',
	'<div class="noc-sub">' + __('Day-by-day hours by location and complaints for one employee or area supervisor') + '</div></div>',
	'<div class="noc-head-right"><div class="noc-filters" data-slot="sheet-filters"></div></div></div>',
	'<div data-slot="sheet"></div>',
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
		this.closedDate.set_value(frappe.datetime.get_today());
		this.sheetMonth.set_value(frappe.datetime.get_today());

		page.set_primary_action(__('Refresh'), () => { this.refresh(); this.refreshSheet(); }, 'refresh');
		page.add_inner_button(__('View Complaints'), () => frappe.set_route('List', 'Complaint Information'));

		this.slot('overview').html('<div class="noc-loading">' + __('Loading…') + '</div>');
		this.refresh();
		this.refreshSheet();
		this.timer = setInterval(() => {
			if (frappe.get_route()[0] === 'noc-dashboard') this.refresh();
		}, NOC_REFRESH_INTERVAL_MS);
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

	// ---- cards -----------------------------------------------------------

	card(title, sub, body, emptyText, count) {
		return '<div class="noc-card"><div class="noc-card-head">' +
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
