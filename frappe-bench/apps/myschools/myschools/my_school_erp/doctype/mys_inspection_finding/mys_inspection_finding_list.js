// Severity + status badges on the Inspection Finding list.
// Critical = red, Major = orange, Minor = grey; status follows the
// workflow's intent (Draft = grey, Open = orange, In Progress = blue,
// Resolved = light green, Verified = green, Cancelled = grey).
frappe.listview_settings["MYS Inspection Finding"] = {
	add_fields: ["severity", "status"],
	get_indicator(doc) {
		const status_map = {
			Draft: [__("Draft"), "grey", "status,=,Draft"],
			Open: [__("Open"), "orange", "status,=,Open"],
			"In Progress": [__("In Progress"), "blue", "status,=,In Progress"],
			Resolved: [__("Resolved"), "light-green", "status,=,Resolved"],
			Verified: [__("Verified"), "green", "status,=,Verified"],
			Cancelled: [__("Cancelled"), "grey", "status,=,Cancelled"],
		};
		return status_map[doc.status];
	},
	formatters: {
		severity(value) {
			const colour = { Critical: "red", Major: "orange", Minor: "grey" }[value] || "grey";
			return `<span class="indicator-pill ${colour} filterable" data-filter="severity,=,${value}">${value}</span>`;
		},
	},
};
