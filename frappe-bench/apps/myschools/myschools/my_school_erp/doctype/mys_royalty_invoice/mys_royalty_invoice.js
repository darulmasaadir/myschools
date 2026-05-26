// "Send Reminder" button on overdue (or unpaid past due) Royalty Invoices.
// Fires the MYS - Royalty Invoice Overdue notification immediately rather
// than waiting for the next scheduled run.
frappe.ui.form.on("MYS Royalty Invoice", {
	refresh(frm) {
		const past_due = frm.doc.due_date && frappe.datetime.now_date() > frm.doc.due_date;
		const can_remind =
			frm.doc.docstatus === 1 &&
			(frm.doc.status === "Overdue" || (frm.doc.status === "Unpaid" && past_due));
		if (!can_remind) return;

		frm.add_custom_button(
			__("Send Reminder"),
			() => {
				frappe.call({
					method: "myschools.api.royalty.send_overdue_reminder",
					args: { invoice: frm.doc.name },
					freeze: true,
					freeze_message: __("Sending reminder…"),
					callback(r) {
						if (r.message && r.message.ok) {
							frappe.show_alert({
								message: __("Reminder sent to {0}", [r.message.recipient]),
								indicator: "green",
							});
						}
					},
				});
			},
			__("Actions")
		);
	},
});
