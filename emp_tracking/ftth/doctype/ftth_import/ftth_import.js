// Copyright (c) 2026, Softworld and contributors
// For license information, please see license.txt

frappe.ui.form.on("FTTH Import", {
	setup(frm) {
		frappe.realtime.on("ftth_import_progress", (data) => {
			if (!frm.doc || frm.doc.name !== frm.docname) return;
			if (data.done) {
				frm.dashboard.hide_progress();
				frm.reload_doc();
				return;
			}
			frm.dashboard.show_progress(
				__("Importing"),
				(data.progress / data.total) * 100,
				__("{0}: {1} of {2}", [data.label, data.progress, data.total])
			);
		});
	},

	refresh(frm) {
		const status_color = { Pending: "gray", Queued: "orange", Running: "blue", Completed: "green", Failed: "red" };
		frm.page.set_indicator(__(frm.doc.status), status_color[frm.doc.status] || "gray");

		if (!frm.is_new() && ["Pending", "Failed", "Completed"].includes(frm.doc.status)) {
			const label = frm.doc.status === "Pending" ? __("Start Import") : __("Run Again");
			frm.add_custom_button(label, () => {
				frappe
					.call("emp_tracking.ftth.importer.run.start_import", { import_name: frm.doc.name })
					.then(() => {
						frappe.show_alert({ message: __("Import queued"), indicator: "blue" });
						frm.reload_doc();
					});
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Completed") {
			frm.add_custom_button(__("Work Orders"), () => frappe.set_route("List", "FTTH Work Order"), __("View"));
			frm.add_custom_button(
				__("With Warnings"),
				() => frappe.set_route("List", "FTTH Work Order", { has_warnings: 1 }),
				__("View")
			);
			frm.add_custom_button(__("Map"), () => frappe.set_route("List", "FTTH Work Order", "Map"), __("View"));
			frm.set_intro(
				__("Done: {0} work orders created, {1} skipped (already existed), {2} issues to review below.", [
					frm.doc.work_orders_created || 0,
					frm.doc.work_orders_skipped || 0,
					frm.doc.issues_found || 0,
				]),
				"green"
			);
		}
		if (frm.is_new()) {
			frm.set_intro(
				__("Attach the email export (.zip, zips inside zips are fine), then Save and click Start Import. Existing work orders are never overwritten."),
				"blue"
			);
		}
	},
});
