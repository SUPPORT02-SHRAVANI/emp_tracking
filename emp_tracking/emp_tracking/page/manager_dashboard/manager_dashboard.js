// Manager Dashboard — Frappe Desk page
// Route: /app/manager-dashboard
//
// Mirrors the logic in the mobile app's services/api.js `fetchManagerOverview`
// and screens/ManagerDashboardScreen.tsx, but as a browser page inside Frappe
// so managers can check live tracking without opening the mobile app.
//
// Reads from: Employee, Employee Checkin, Location Ping, Employee Home Location.
// If your fieldnames on Location Ping differ from timestamp/latitude/longitude/
// speed/battery, update FIELD_* constants below to match.
//
// Only "Live Location" has real data behind it. The other tabs (Overview,
// Timeline, Card View, Compliance Status, Site Attendance) are placeholders —
// there's no doctype/data model for them in this app yet.

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

var TABS = [
	{ key: 'live', icon: '📍', label: 'Live Location' },
	{ key: 'overview', icon: '📊', label: 'Overview' },
	{ key: 'timeline', icon: '⏱', label: 'Timeline' },
	{ key: 'cardview', icon: '▦', label: 'Card View' },
	{ key: 'compliance', icon: '✅', label: 'Compliance Status' },
	{ key: 'siteattendance', icon: '📌', label: 'Site Attendance' },
];

class ManagerDashboard {
	constructor(page) {
		this.page = page;
		this.punchFilter = 'ALL';
		this.statusFilter = 'ALL';
		this.batteryFilter = 'ALL';
		this.search = '';
		this.showSites = true;
		this.showClients = false;
		this.employees = [];
		this.homeLocations = [];
		this.map = null;
		this.markersLayer = null;
		this.leafletReady = false;

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
					.md-root { padding: 4px 2px 24px 2px; }

					.md-tabbar { display: flex; gap: 22px; border-bottom: 1px solid #e5e7eb; margin-bottom: 16px; flex-wrap: wrap; }
					.md-tab { display: flex; align-items: center; gap: 6px; padding: 10px 2px; font-size: 13px; font-weight: 700;
						color: #64748b; cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap; }
					.md-tab:hover { color: #334155; }
					.md-tab.active { color: #2563eb; border-bottom-color: #2563eb; }
					.md-tab-icon { font-size: 13px; }
					.md-tab-panel { display: none; }
					.md-tab-panel.active { display: block; }
					.md-placeholder { text-align: center; padding: 70px 20px; color: #94a3b8; font-size: 13.5px;
						background: #fff; border: 1px solid #e5e7eb; border-radius: 14px; }

					.md-updated { font-size: 12px; color: #64748b; margin-bottom: 14px; }

					.md-stats { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
					.md-stat { flex: 1; min-width: 90px; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px;
						padding: 12px; text-align: center; }
					.md-stat .val { font-size: 20px; font-weight: 800; color: #0f172a; }
					.md-stat .lbl { font-size: 11px; color: #64748b; margin-top: 2px; }

					.md-attention { background: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; padding: 12px 14px;
						margin-bottom: 16px; display: none; }
					.md-attention.show { display: block; }
					.md-attention-title { font-size: 13px; font-weight: 800; color: #991b1b; margin-bottom: 8px; }
					.md-attention-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; font-size: 12.5px; }
					.md-attention-row .name { font-weight: 700; color: #111827; }
					.md-attention-row .reason { color: #991b1b; }

					.md-section-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;
						gap: 10px; margin-bottom: 12px; }
					.md-section-title { font-size: 16px; font-weight: 800; color: #0f172a; }
					.md-pills { display: flex; gap: 8px; flex-wrap: wrap; }
					.md-pill { border-radius: 20px; padding: 6px 14px; font-size: 11.5px; font-weight: 800; color: #fff;
						cursor: pointer; white-space: nowrap; opacity: 0.92; transition: transform .1s, opacity .1s; }
					.md-pill:hover { opacity: 1; }
					.md-pill.active { box-shadow: 0 0 0 2px rgba(15,23,42,0.35) inset; opacity: 1; }
					.md-pill.all { background: #2563eb; }
					.md-pill.in { background: #16a34a; }
					.md-pill.out { background: #dc2626; }

					.md-body { display: flex; gap: 16px; height: 620px; }
					@media (max-width: 900px) { .md-body { flex-direction: column; height: auto; } }

					.md-sidebar { width: 360px; flex-shrink: 0; display: flex; flex-direction: column; background: #fff;
						border: 1px solid #e5e7eb; border-radius: 14px; overflow: hidden; }
					@media (max-width: 900px) { .md-sidebar { width: 100%; } }
					.md-search { padding: 12px; border-bottom: 1px solid #f1f5f9; position: relative; }
					.md-search input { width: 100%; box-sizing: border-box; border: 1px solid #e2e8f0; border-radius: 10px;
						padding: 8px 12px 8px 30px; font-size: 12.5px; background: #f8fafc; outline: none; }
					.md-search input:focus { border-color: #93c5fd; background: #fff; }
					.md-search::before { content: '🔍'; position: absolute; left: 22px; top: 21px; font-size: 11px; opacity: .6; }

					.md-cardlist { flex: 1; overflow-y: auto; padding: 10px 10px 14px; }
					.md-emp-card { display: flex; gap: 10px; background: #fff; border: 1px solid #e5e7eb; border-left: 4px solid #cbd5e1;
						border-radius: 10px; padding: 10px 12px; margin-bottom: 9px; cursor: pointer; transition: border-color .1s; }
					.md-emp-card:hover { border-color: #93c5fd; border-left-color: #93c5fd; }
					.md-emp-card.punch-in { border-left-color: #16a34a; }
					.md-emp-card.punch-out { border-left-color: #dc2626; }
					.md-avatar { width: 36px; height: 36px; border-radius: 18px; display: flex; align-items: center; justify-content: center;
						background: #e2e8f0; color: #334155; font-weight: 800; font-size: 12px; flex-shrink: 0; margin-top: 1px; }
					.md-card-body { flex: 1; min-width: 0; }
					.md-card-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 6px; }
					.md-card-name { font-size: 13px; font-weight: 800; color: #0f172a; }
					.md-card-name .device-id { color: #2563eb; font-weight: 700; }
					.md-card-phone { font-size: 11px; color: #64748b; margin-top: 1px; }
					.md-card-meta { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
					.md-meta-chip { font-size: 10.5px; font-weight: 700; display: flex; align-items: center; gap: 2px; }
					.md-punch-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 7px; }
					.md-punch-label { font-size: 10.5px; font-weight: 700; padding: 3px 8px; border-radius: 6px; }
					.md-punch-label.in { color: #15803d; background: #dcfce7; }
					.md-punch-label.out { color: #b91c1c; background: #fee2e2; }
					.md-timeline-btn { font-size: 10px; font-weight: 800; color: #fff; background: #2563eb; border: none;
						border-radius: 6px; padding: 4px 9px; cursor: pointer; white-space: nowrap; }
					.md-timeline-btn:hover { background: #1d4ed8; }
					.md-card-address { font-size: 11px; color: #475569; margin-top: 7px; }
					.md-card-ago { font-size: 10.5px; color: #94a3b8; margin-top: 2px; }
					.md-empty { text-align: center; padding: 30px 14px; color: #94a3b8; font-size: 13px; }

					.md-mapwrap { flex: 1; min-width: 0; display: flex; flex-direction: column; background: #fff;
						border: 1px solid #e5e7eb; border-radius: 14px; overflow: hidden; }
					.md-map-toolbar { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-bottom: 1px solid #f1f5f9;
						flex-wrap: wrap; }
					.md-select { border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px 8px; font-size: 11.5px; color: #334155;
						background: #f8fafc; font-weight: 600; }
					.md-toggle-btn { border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px 10px; font-size: 11.5px;
						font-weight: 700; color: #475569; background: #fff; cursor: pointer; }
					.md-toggle-btn.on { background: #dbeafe; border-color: #93c5fd; color: #1d4ed8; }
					.md-reset-btn { margin-left: auto; border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px 10px;
						font-size: 11.5px; font-weight: 700; color: #475569; background: #fff; cursor: pointer; }
					.md-reset-btn:hover { border-color: #cbd5e1; }

					.md-map-area { flex: 1; position: relative; }
					.md-map { position: absolute; inset: 0; }
					.md-view-toggle { position: absolute; top: 10px; right: 10px; z-index: 1000; background: #fff; border-radius: 8px;
						overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.25); display: flex; }
					.md-view-btn { border: none; background: #fff; padding: 6px 12px; font-size: 11.5px; font-weight: 700;
						color: #475569; cursor: pointer; }
					.md-view-btn.active { background: #2563eb; color: #fff; }
				</style>

				<div class="md-tabbar"></div>

				<div class="md-tab-panel active" data-panel="live">
					<div class="md-updated">Updated: <span class="md-updated-time">—</span></div>

					<div class="md-stats">
						<div class="md-stat"><div class="val md-v-active">0</div><div class="lbl">Active</div></div>
						<div class="md-stat"><div class="val md-v-moving" style="color:#16a34a">0</div><div class="lbl">Moving</div></div>
						<div class="md-stat"><div class="val md-v-stopped" style="color:#f97316">0</div><div class="lbl">Stopped</div></div>
						<div class="md-stat"><div class="val md-v-offline" style="color:#ef4444">0</div><div class="lbl">Offline</div></div>
						<div class="md-stat"><div class="val md-v-distance" style="color:#7c3aed">0</div><div class="lbl">Total km</div></div>
					</div>

					<div class="md-attention">
						<div class="md-attention-title"><span class="md-attention-count">0</span> employee(s) need attention</div>
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

					<div class="md-body">
						<div class="md-sidebar">
							<div class="md-search"><input type="text" class="md-search-input" placeholder="Search Employee..."></div>
							<div class="md-cardlist"></div>
						</div>
						<div class="md-mapwrap">
							<div class="md-map-toolbar">
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
								<button class="md-toggle-btn" data-toggle="clients">Show Clients</button>
								<button class="md-toggle-btn on" data-toggle="sites">Show Sites</button>
								<button class="md-reset-btn">Reset Filters</button>
							</div>
							<div class="md-map-area">
								<div class="md-view-toggle">
									<button class="md-view-btn active" data-view="map">Map</button>
									<button class="md-view-btn" data-view="sat">Satellite</button>
								</div>
								<div class="md-map" id="md-map"></div>
							</div>
						</div>
					</div>
				</div>

				<div class="md-tab-panel" data-panel="overview">
					<div class="md-placeholder">Overview view is coming soon.</div>
				</div>
				<div class="md-tab-panel" data-panel="timeline">
					<div class="md-placeholder">Timeline view is coming soon.</div>
				</div>
				<div class="md-tab-panel" data-panel="cardview">
					<div class="md-placeholder">Card View is coming soon.</div>
				</div>
				<div class="md-tab-panel" data-panel="compliance">
					<div class="md-placeholder">Compliance Status is coming soon.</div>
				</div>
				<div class="md-tab-panel" data-panel="siteattendance">
					<div class="md-placeholder">Site Attendance is coming soon.</div>
				</div>
			</div>
		`).appendTo(this.page.body);

		this.render_tabbar();

		this.$root.find('.md-pill').on('click', (e) => {
			this.punchFilter = $(e.currentTarget).data('punch');
			this.$root.find('.md-pill').removeClass('active');
			$(e.currentTarget).addClass('active');
			this.render_map_and_list();
		});

		this.$root.find('.md-search-input').on('input', (e) => {
			this.search = $(e.currentTarget).val().trim().toLowerCase();
			this.render_map_and_list();
		});

		this.$root.find('.md-battery-filter').on('change', (e) => {
			this.batteryFilter = $(e.currentTarget).val();
			this.render_map_and_list();
		});

		this.$root.find('.md-gps-filter').on('change', (e) => {
			this.statusFilter = $(e.currentTarget).val();
			this.render_map_and_list();
		});

		this.$root.find('[data-toggle="sites"]').on('click', (e) => {
			this.showSites = !this.showSites;
			$(e.currentTarget).toggleClass('on', this.showSites);
			this.render_map_and_list();
		});

		this.$root.find('[data-toggle="clients"]').on('click', (e) => {
			this.showClients = !this.showClients;
			$(e.currentTarget).toggleClass('on', this.showClients);
		});

		this.$root.find('.md-reset-btn').on('click', () => {
			this.punchFilter = 'ALL';
			this.statusFilter = 'ALL';
			this.batteryFilter = 'ALL';
			this.search = '';
			this.showSites = true;
			this.$root.find('.md-search-input').val('');
			this.$root.find('.md-battery-filter').val('ALL');
			this.$root.find('.md-gps-filter').val('ALL');
			this.$root.find('.md-pill').removeClass('active');
			this.$root.find('.md-pill.all').addClass('active');
			this.$root.find('[data-toggle="sites"]').addClass('on');
			this.render_map_and_list();
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

			var [employees, checkins, pings, homes] = await Promise.all([
				frappe.db.get_list('Employee', {
					fields: ['name', 'employee_name', 'status', 'designation', 'cell_number', 'attendance_device_id'],
					limit: 500,
				}),
				frappe.db.get_list('Employee Checkin', {
					fields: ['employee', 'log_type', 'time'],
					filters: [['time', '>=', start], ['time', '<=', end]],
					order_by: 'time desc',
					limit: 2000,
				}),
				frappe.db.get_list('Location Ping', {
					fields: ['employee', FIELD_TIMESTAMP, 'latitude', 'longitude', FIELD_SPEED, FIELD_BATTERY],
					filters: [[FIELD_TIMESTAMP, '>=', start]],
					order_by: FIELD_TIMESTAMP + ' desc',
					limit: 2000,
				}).catch(() => []),
				frappe.db.get_list('Employee Home Location', {
					fields: ['employee', 'latitude', 'longitude', 'address'],
					limit: 500,
				}).catch(() => []),
			]);

			this.homeLocations = homes || [];
			this.employees = this.compute_employees(employees || [], checkins || [], pings || []);
			this.$root.find('.md-updated-time').text(new Date().toLocaleTimeString());
			this.render_stats();
			this.render_attention();
			this.render_map_and_list();
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

			return {
				employeeId: emp.name,
				employeeName: emp.employee_name || emp.name,
				cellNumber: emp.cell_number || '',
				deviceId: emp.attendance_device_id || '',
				status: status,
				isPunchedIn: isPunchedIn,
				punchTime: latestCheckin ? latestCheckin.time : null,
				lastPing: latestPing ? latestPing[FIELD_TIMESTAMP] : null,
				diffMins: diffMins,
				distanceKm: distanceKm,
				durationFormatted: durationFormatted,
				currentAddress: emp.designation || (lat != null ? lat.toFixed(4) + ', ' + lng.toFixed(4) : 'No location data'),
				latitude: lat,
				longitude: lng,
				batteryLevel: batteryLevel,
				batteryStale: batteryStale,
			};
		});
	}

	// ---- rendering ----------------------------------------------------------

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

	render_map_and_list() {
		var visible = this.get_visible_employees();

		this.$root.find('.md-emp-count').text(this.employees.length);
		this.$root.find('.md-pc-all').text(this.employees.length);
		this.$root.find('.md-pc-in').text(this.employees.filter((e) => e.isPunchedIn).length);
		this.$root.find('.md-pc-out').text(this.employees.filter((e) => !e.isPunchedIn).length);

		// --- map markers ---
		if (this.markersLayer) {
			this.markersLayer.clearLayers();
			var bounds = [];
			var homesById = {};
			this.homeLocations.forEach((h) => (homesById[h.employee] = h));

			visible.forEach((e) => {
				if (e.latitude != null && e.longitude != null) {
					var color = STATUS_COLORS[e.status] || '#2563eb';
					var icon = L.divIcon({
						className: '',
						html: '<div style="width:16px;height:16px;border-radius:50%;background:' + color +
							';border:2px solid #fff;box-shadow:0 0 6px rgba(0,0,0,0.4);"></div>',
						iconSize: [16, 16],
						iconAnchor: [8, 8],
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
						html: '<div style="width:14px;height:14px;border-radius:50%;background:#94a3b8;border:2px dashed #fff;"></div>',
						iconSize: [14, 14],
						iconAnchor: [7, 7],
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

		// --- employee list ---
		var $list = this.$root.find('.md-cardlist').empty();
		if (!visible.length) {
			$list.append('<div class="md-empty">No employees match this filter.</div>');
			return;
		}

		visible.forEach((e) => {
			var initials = (e.employeeName || '?').trim().split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase();
			var batteryColor = e.batteryLevel == null || e.batteryStale
				? '#94a3b8'
				: e.batteryLevel <= 15 ? '#ef4444' : e.batteryLevel <= 30 ? '#f97316' : '#16a34a';
			var batteryText = e.batteryLevel != null
				? '🔋' + e.batteryLevel + '%'
				: '🔋 --';
			var gpsColor = e.status === 'OFFLINE' ? '#ef4444' : '#16a34a';
			var punchClass = e.isPunchedIn ? 'punch-in' : 'punch-out';
			var punchLabelClass = e.isPunchedIn ? 'in' : 'out';
			var punchLabel = format_punch_label(e.punchTime, e.isPunchedIn);

			var $card = $(`
				<div class="md-emp-card ${punchClass}">
					<div class="md-avatar">${frappe.utils.escape_html(initials)}</div>
					<div class="md-card-body">
						<div class="md-card-top">
							<div>
								<div class="md-card-name">${frappe.utils.escape_html(e.employeeName)}${e.deviceId ? ' <span class="device-id">(' + frappe.utils.escape_html(e.deviceId) + ')</span>' : ''}</div>
								${e.cellNumber ? '<div class="md-card-phone">' + frappe.utils.escape_html(e.cellNumber) + '</div>' : ''}
							</div>
							<div class="md-card-meta">
								<span class="md-meta-chip" style="color:${batteryColor}">${batteryText}</span>
								<span class="md-meta-chip" style="color:${gpsColor}">📍</span>
							</div>
						</div>
						<div class="md-punch-row">
							<span class="md-punch-label ${punchLabelClass}">${punchLabel}</span>
							<button class="md-timeline-btn">Timeline ↗</button>
						</div>
						<div class="md-card-address">📍 ${frappe.utils.escape_html(e.currentAddress)}</div>
						<div class="md-card-ago">${time_ago(e.lastPing)}</div>
					</div>
				</div>
			`);
			$card.on('click', () => frappe.set_route('Form', 'Employee', e.employeeId));
			$card.find('.md-timeline-btn').on('click', (ev) => {
				ev.stopPropagation();
				frappe.set_route('List', 'Location Ping', { employee: e.employeeId });
			});
			$list.append($card);
		});
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
	if (!iso) return isPunchedIn ? 'Punched IN' : 'No punch record';
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
