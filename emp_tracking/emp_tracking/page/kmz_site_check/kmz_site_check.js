// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt
// ---------------------------------------------------------------------------------------------
// KMZ Site Check (Desk page /app/kmz-site-check), created 2026-10-27.
//
// For checking Site (building) names against the KMZ pin names of the same GIS Node on screen.
// Each row is one Site with its match status, how many KMZ lines / pins are linked to it, and
// the 3 closest KMZ names. Nothing changes until a button is pressed on a row:
//   (a KMZ name whose pins are all linked to another Site shows "already used", with no buttons)
//   Link          - links that KMZ name's pins (and routes ending there) to the Site;
//   Rename & Link - also corrects the Site name (editable, the KMZ spelling without ODF /
//                   Encloser / JC is suggested). The old name is kept in a comment on the Site.
// Linked rows turn red / orange on the KMZ Map when the Site has an open complaint.
// Data comes from kmz_site_check.py.
//
// Change log
//   2026-10-27  Created.
//   2026-11-02  EVision design layer (public/css/evision.css): colours in the page's <style> are --ev-* tokens (Frappe
//               Espresso, light + dark mode) instead of hex; lighter type weights;
//               the loading box is a skeleton.
// ---------------------------------------------------------------------------------------------

const KSC_METHOD = "emp_tracking.emp_tracking.page.kmz_site_check.kmz_site_check.";

frappe.pages["kmz-site-check"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("KMZ Site Check"), single_column: true });
	wrapper.ksc = new KMZSiteCheck(page);
};

function ksc_esc(v) {
	return frappe.utils.escape_html(v == null ? "" : String(v));
}

const KSC_STYLE = `
<style>
.ksc-filters { display:flex; flex-wrap:wrap; gap:12px; align-items:flex-end; margin-bottom:12px; }
.ksc-filters .frappe-control { margin-bottom:0; min-width:180px; }
.ksc-kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:12px; }
.ksc-kpi { background:var(--card-bg); border:1px solid var(--border-color); border-radius:12px; padding:10px 14px;
	border-top:1px solid var(--ev-border); }
.ksc-kpi .v { font-size:20px; font-weight:500; color:var(--text-color); } .ksc-kpi .l { font-size:12px; color:var(--text-muted); }
.ksc-kpi.t-orange { border-top-color:var(--ev-border); } .ksc-kpi.t-red { border-top-color:var(--ev-border); }
.ksc-kpi.t-gray { border-top-color:var(--ev-border); }
.ksc-table { width:100%; background:var(--card-bg); }
.ksc-table td { vertical-align:top; }
.ksc-cand { display:flex; align-items:center; gap:8px; padding:3px 0; border-bottom:1px dashed var(--border-color); }
.ksc-cand:last-child { border-bottom:0; }
.ksc-cand .nm { flex:1; } .ksc-cand .sc { font-size:12px; color:var(--text-muted); white-space:nowrap; }
.ksc-badge { font-size:11px; font-weight:600; border-radius:10px; padding:1px 8px; white-space:nowrap; }
.ksc-badge.Exact { background:var(--green-100); color:var(--green-700); }
.ksc-badge.Partial { background:var(--orange-100); color:var(--orange-700); }
.ksc-badge.No { background:var(--red-100); color:var(--red-700); }
.ksc-help { font-size:12px; color:var(--text-muted); margin-bottom:10px; }
</style>`;

class KMZSiteCheck {
	constructor(page) {
		this.page = page;
		$(page.body).html(`${KSC_STYLE}
			<div class="ksc-help">${__("Check each building: if a KMZ name on the right is the same building, press Link (or Rename & Link to also correct the Site's spelling). Nothing changes until you press a button. KMZ names are not changed.")}</div>
			<div class="ksc-filters"></div><div class="ksc-kpis"></div><div class="ksc-list"></div>`);
		this.$ = (sel) => $(page.body).find(sel);
		this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");
		this.page.add_inner_button(__("KMZ Map"), () => frappe.set_route("kmz-map"));
		const make = (df) => frappe.ui.form.make_control({
			parent: $("<div>").appendTo(this.$(".ksc-filters")),
			df: { ...df, change: () => { if (this.ready) this.refresh(); } },
			render_input: true,
		});
		this.f_node = make({ fieldname: "node", label: __("GIS Node"), fieldtype: "Select", options: [""] });
		this.f_show = make({ fieldname: "show", label: __("Show"), fieldtype: "Select",
			options: ["Needs Check", "Not Linked", "All"] });
		this.f_show.set_value("Needs Check").then(() => { this.ready = true; this.refresh(); });
	}

	// Date: 2026-10-27
	async refresh() {
		this.$(".ksc-list").html(`<div class="text-muted ev-loading">${__("Loading...")}</div>`);
		const node = this.f_node.get_value() || null;
		const d = await frappe.xcall(KSC_METHOD + "get_rows", { node, show: this.f_show.get_value() });
		if (!node) {
			this.f_node.df.options = [""].concat(d.nodes);
			this.f_node.set_options();
		}
		const c = d.counts;
		const tile = (v, l, cls = "") => `<div class="ksc-kpi ${cls}"><div class="v">${v || 0}</div><div class="l">${l}</div></div>`;
		this.$(".ksc-kpis").html(tile(c.Exact, __("Name matches KMZ")) + tile(c.Partial, __("Close match"), "t-orange") +
			tile(c["No Match"], __("No KMZ name"), "t-red") + tile(c["Not Linked"], __("Not linked to KMZ"), "t-gray"));
		this.draw(d.rows);
	}

	draw(rows) {
		if (!rows.length) {
			this.$(".ksc-list").html(`<div class="text-muted">${__("Nothing to check for these filters.")}</div>`);
			return;
		}
		this.rows = rows;
		this.$(".ksc-list").html(`<table class="table table-bordered table-sm ksc-table">
			<thead><tr><th>${__("Node")}</th><th>${__("Site (building)")}</th><th>${__("Status")}</th>
				<th class="text-right">${__("KMZ linked")}</th><th>${__("Closest KMZ names (same node)")}</th></tr></thead>
			<tbody>${rows.map((r, i) => `<tr>
				<td>${ksc_esc(r.node)}</td>
				<td><a href="/app/site/${encodeURIComponent(r.site)}">${ksc_esc(r.site_name)}</a>
					<div class="text-muted small">${ksc_esc(r.etipl_code || r.site)}</div></td>
				<td><span class="ksc-badge ${r.status.split(" ")[0]}">${__(r.status)}</span></td>
				<td class="text-right">${r.linked}</td>
				<td>${r.candidates.length ? r.candidates.map((c, j) => `<div class="ksc-cand">
					<span class="nm">${ksc_esc(c.kmz_name)}</span>
					<span class="sc">${__("{0}% alike · {1} pins", [c.score, c.pins])}
						${c.taken_by.length ? `<br>${__("linked to")} ${c.taken_by.map((t) =>
							`<a href="/app/site/${encodeURIComponent(t.site)}">${ksc_esc(t.site_name)}</a>`).join(", ")}` : ""}</span>
					${c.free ? `<button class="btn btn-xs btn-default ksc-link" data-i="${i}" data-j="${j}">${__("Link")}</button>
					<button class="btn btn-xs btn-primary ksc-rename" data-i="${i}" data-j="${j}">${__("Rename & Link")}</button>`
						: `<span class="text-muted small">${__("already used")}</span>`}
				</div>`).join("") : `<span class="text-muted">${__("No KMZ pins on this node")}</span>`}</td>
			</tr>`).join("")}</tbody></table>`);
		this.$(".ksc-link").on("click", (e) => this.act(e, false));
		this.$(".ksc-rename").on("click", (e) => this.act(e, true));
	}

	// Date: 2026-10-27
	act(e, rename) {
		const $b = $(e.currentTarget);
		const r = this.rows[cint($b.attr("data-i"))], c = r.candidates[cint($b.attr("data-j"))];
		const run = (new_site_name) => frappe.xcall(KSC_METHOD + "apply", { site: r.site, kmz_name: c.kmz_name, new_site_name })
			.then((res) => {
				frappe.show_alert({ indicator: "green", message: __("{0}: {1} pins and {2} routes linked{3}",
					[r.site_name, res.points, res.routes, res.renamed ? __(", Site renamed") : ""]) });
				this.refresh();
			});
		if (!rename) {
			frappe.confirm(__("Link KMZ \"{0}\" to Site \"{1}\"?", [ksc_esc(c.kmz_name), ksc_esc(r.site_name)]), () => run(null));
			return;
		}
		frappe.prompt({ fieldname: "new_name", label: __("Correct Site name"), fieldtype: "Data", reqd: 1, default: c.suggest,
			description: __("Now: {0} · KMZ: {1}", [ksc_esc(r.site_name), ksc_esc(c.kmz_name)]) },
			(v) => run(v.new_name), __("Rename & Link"), __("Save"));
	}
}
