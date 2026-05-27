// Status badges on the Royalty Invoice list. Maps the workflow states to
// indicator colours that match the finance team's mental model: red =
// overdue/action-needed, green = closed-good, grey = inert.
frappe.listview_settings["MYS Royalty Invoice"] = {
	add_fields: ["status", "outstanding_amount", "due_date"],
	get_indicator(doc) {
		const status_map = {
			Draft: [__("Draft"), "grey", "status,=,Draft"],
			Unpaid: [__("Unpaid"), "orange", "status,=,Unpaid"],
			Partial: [__("Partial"), "blue", "status,=,Partial"],
			Paid: [__("Paid"), "green", "status,=,Paid"],
			Overdue: [__("Overdue"), "red", "status,=,Overdue"],
			Cancelled: [__("Cancelled"), "grey", "status,=,Cancelled"],
		};
		return status_map[doc.status];
	},
};
