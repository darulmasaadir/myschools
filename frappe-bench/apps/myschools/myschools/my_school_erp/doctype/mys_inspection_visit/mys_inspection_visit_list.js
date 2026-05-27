// Visit list uses docstatus as the status surrogate until a formal Visit
// workflow ships in the Phase-5 follow-up.
frappe.listview_settings["MYS Inspection Visit"] = {
	add_fields: ["docstatus", "visit_type"],
	get_indicator(doc) {
		if (doc.docstatus === 2) {
			return [__("Cancelled"), "grey", "docstatus,=,2"];
		}
		if (doc.docstatus === 1) {
			return [__("Submitted"), "green", "docstatus,=,1"];
		}
		return [__("Draft"), "orange", "docstatus,=,0"];
	},
};
