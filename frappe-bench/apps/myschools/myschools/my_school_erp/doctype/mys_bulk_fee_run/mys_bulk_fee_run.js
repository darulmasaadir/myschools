// Copyright (c) 2026, MY School Pakistan and contributors
// For license information, please see license.txt

frappe.ui.form.on("MYS Bulk Fee Run", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status === "In Process") {
			return;
		}
		frm.add_custom_button(__("Generate Fees"), () => {
			frappe.call({
				method: "myschools.api.fees.generate_bulk_fees_for_run",
				args: { run: frm.doc.name },
				freeze: true,
				freeze_message: __("Generating Fees…"),
				callback() {
					frm.reload_doc();
				},
			});
		}).addClass("btn-primary");
	},
});
