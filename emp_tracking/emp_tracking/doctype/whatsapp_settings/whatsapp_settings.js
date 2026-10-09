// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt

// ---------------------------------------------------------------------------------------------
// WhatsApp Settings: form script
//
// How this file works
//   Only the "Send Test Message" button needs the browser: it asks the server to send the
//   stage template to the Test Mobile Number and shows WhatsApp's answer.
//
// Change log
//   2026-10-08  Created with the Send Test Message button.
// ---------------------------------------------------------------------------------------------

frappe.ui.form.on("WhatsApp Settings", {
	// Date: 2026-10-08
	// "Send Test Message" button: unsaved changes would not be used, so ask to save first.
	send_test_message(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Please save the settings first."));
			return;
		}
		frappe.call({
			method: "emp_tracking.emp_tracking.doctype.whatsapp_settings.whatsapp_settings.send_test_message",
			freeze: true,
			freeze_message: __("Sending test message…"),
			callback: (r) => frappe.msgprint({ title: __("WhatsApp"), indicator: "green", message: r.message }),
		});
	},
});
