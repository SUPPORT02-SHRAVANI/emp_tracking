// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt

// KMZ Upload form: a "Match & Import" button that queues the import (kmz_upload.py), and a
// reload when the background job finishes.
// Change log
//   2026-10-26  Created.

frappe.ui.form.on("KMZ Upload", {
	// Date: 2026-10-26
	refresh(frm) {
		if (!frm.is_new() && frm.doc.kmz_file && !["Queued", "Running"].includes(frm.doc.status)) {
			frm.add_custom_button(frm.doc.status === "Completed" ? __("Match & Import Again") : __("Match & Import"), () =>
				frappe.xcall("emp_tracking.emp_tracking.doctype.kmz_upload.kmz_upload.start_import", { name: frm.doc.name })
					.then(() => frm.reload_doc()), null).addClass("btn-primary");
		}
		if (["Queued", "Running"].includes(frm.doc.status)) {
			frm.dashboard.set_headline(__("Matching the KMZ to GIS Nodes... this page reloads when it is done."));
		}
		if (frm.doc.status === "Completed" && frm.doc.nodes_found) {
			frm.add_custom_button(__("KMZ Points"), () => frappe.set_route("List", "KMZ Point", { custom_kmz_upload: frm.doc.name }), __("View"));
			frm.add_custom_button(__("KMZ Routes"), () => frappe.set_route("List", "KMZ Route", { custom_kmz_upload: frm.doc.name }), __("View"));
		}
		// the server publishes this when run_import() ends (Completed or Failed)
		frappe.realtime.off("kmz_upload_done");
		frappe.realtime.on("kmz_upload_done", (data) => {
			if (data.name === frm.doc.name) frm.reload_doc();
		});
	},
});
