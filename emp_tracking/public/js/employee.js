// employee.js — Employee form: company-wise Employee Code
// Created: 2026-11-20
// Shows the next Employee Code (IPT-0001, AUT-0001, INF-0001 ...) as soon as a company is picked on a
// new Employee. It is only a preview: the server (emp_tracking.overrides.employee.before_insert) gives
// the final number on save, so two people adding employees at once never get the same code.
// Change log:
//   2026-11-20  Created.

frappe.ui.form.on("Employee", {
	company(frm) {
		emp_tracking_set_code_preview(frm);
	},
	onload(frm) {
		emp_tracking_set_code_preview(frm);
	},
});

function emp_tracking_set_code_preview(frm) {
	if (!frm.is_new() || !frm.fields_dict.custom_employee_code) return;
	const current = frm.doc.custom_employee_code || "";
	// Replace only an empty or automatic-looking code (e.g. IPT-0003 when the company changes);
	// a code the user typed in another format is left as it is.
	if (current && !/^[A-Z]+-\d+$/.test(current)) return;
	if (!frm.doc.company) return;
	frappe.call({
		method: "emp_tracking.overrides.employee.get_next_employee_code",
		args: { company: frm.doc.company },
		callback(r) {
			if (r.message) frm.set_value("custom_employee_code", r.message);
		},
	});
}
