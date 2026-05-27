// Shortcut: when a Finding is In Progress, surface a "Create Corrective
// Action" button. The workflow already provides Acknowledge / Mark Resolved
// / Verify / Reject Resolution / Cancel buttons via the standard workflow
// menu — we only add what the workflow can't.
frappe.ui.form.on("MYS Inspection Finding", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		if (!["Open", "In Progress"].includes(frm.doc.status)) return;

		frm.add_custom_button(
			__("Create Corrective Action"),
			() => {
				frappe.new_doc("MYS Corrective Action", {
					finding: frm.doc.name,
					branch: frm.doc.branch,
					campus: frm.doc.campus,
				});
			},
			__("Actions")
		);
	},
});
