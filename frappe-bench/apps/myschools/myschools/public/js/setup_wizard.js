// MY Schools — setup wizard slide.
//
// Registered via the `setup_wizard_requires` hook in myschools/hooks.py.
// Adds one extra slide *after* ERPNext's stock slides (organization /
// user-details / region). All fields are optional — operators who don't
// want to seed the franchise tree at install time can leave them blank
// and create Cluster / Branch / Campus through the normal forms later.
//
// The values collected here are POSTed alongside ERPNext's args to
// `frappe.desk.page.setup_wizard.setup_wizard.setup_complete` and are
// read in Python by `myschools.scripts.setup_wizard.create_first_franchise_tree`.

frappe.provide("mys.setup");

frappe.setup.on("before_load", function () {
	// Skip if this app's setup already completed on a prior wizard run.
	if (
		frappe.boot.setup_wizard_completed_apps?.length &&
		frappe.boot.setup_wizard_completed_apps.includes("myschools")
	) {
		return;
	}
	mys.setup.slides_settings.map(frappe.setup.add_slide);
});

mys.setup.slides_settings = [
	{
		name: "mys_franchise",
		title: __("Seed your first Cluster, Branch and Campus"),
		// Optional slide — operators can skip every field.
		icon: "fa fa-sitemap",
		fields: [
			{ fieldtype: "Section Break", label: __("First Cluster (optional)") },
			{
				fieldname: "mys_cluster_code",
				label: __("Cluster Code"),
				fieldtype: "Data",
				description: __("Short code, e.g. CLR-NORTH. Leave blank to skip."),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "mys_cluster_name",
				label: __("Cluster Name"),
				fieldtype: "Data",
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "mys_cluster_region",
				label: __("Region"),
				fieldtype: "Data",
				description: __("Optional descriptor, e.g. 'Northern Punjab'."),
			},

			{ fieldtype: "Section Break", label: __("First Branch (optional)") },
			{
				fieldname: "mys_branch_code",
				label: __("Branch Code"),
				fieldtype: "Data",
				description: __("Short code, e.g. BR-001. Required to create a Branch."),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "mys_branch_name",
				label: __("Branch Name"),
				fieldtype: "Data",
			},

			{ fieldtype: "Section Break", label: __("First Campus (optional)") },
			{
				fieldname: "mys_campus_type",
				label: __("Campus Type"),
				fieldtype: "Select",
				options: "\nKids\nJunior\nSenior",
				description: __("Pick a tier. Will be created under the Branch above."),
			},
		],

		validate: function () {
			// Anything goes — the Python stage skips rows whose required
			// fields are blank, so an entirely blank slide is valid (the
			// user simply doesn't seed any data at install time).
			//
			// Light validation: if any Branch field is filled, both must be,
			// otherwise the row would silently be dropped on the backend.
			const v = this.values;
			const branch_partial =
				(v.mys_branch_code && !v.mys_branch_name) ||
				(v.mys_branch_name && !v.mys_branch_code);
			if (branch_partial) {
				frappe.msgprint(__("Enter both Branch Code and Branch Name, or leave both blank."));
				return false;
			}
			const cluster_partial =
				(v.mys_cluster_code && !v.mys_cluster_name) ||
				(v.mys_cluster_name && !v.mys_cluster_code);
			if (cluster_partial) {
				frappe.msgprint(__("Enter both Cluster Code and Cluster Name, or leave both blank."));
				return false;
			}
			// Branch needs a Cluster — either from this slide or pre-existing.
			if (v.mys_branch_code && !v.mys_cluster_code) {
				frappe.msgprint(__("A Branch needs a Cluster. Fill in the Cluster fields above."));
				return false;
			}
			// Campus needs a Branch.
			if (v.mys_campus_type && !v.mys_branch_code) {
				frappe.msgprint(__("A Campus needs a Branch. Fill in the Branch fields above."));
				return false;
			}
			return true;
		},
	},
];
