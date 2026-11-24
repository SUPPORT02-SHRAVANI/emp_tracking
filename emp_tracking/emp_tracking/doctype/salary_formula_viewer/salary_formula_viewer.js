// Salary Formula Viewer: reloads the formula table whenever the structure or an example value changes.
// Created: 2026-11-23.

frappe.ui.form.on("Salary Formula Viewer", {
	refresh(frm) {
		frm.disable_save();  // a view, nothing to save
		frm.set_intro(__("Choose a Salary Structure. Every component is shown with its formula in simple words and an example amount for the example gross salary."));
		if (frm.doc.salary_structure) {
			frm.add_custom_button(__("Open Salary Structure"), () =>
				frappe.set_route("Form", "Salary Structure", frm.doc.salary_structure));
		}
	},
	salary_structure: load,
	example_gross: load,
	example_variable: load,
	example_gender: load,
});

function load(frm) {
	// runs the server method on the current (unsaved) form values and shows the result
	frm.call({ method: "load_formulas", doc: frm.doc, freeze: true }).then(() => {
		frm.refresh_fields();
		frm.trigger("refresh");
	});
}
