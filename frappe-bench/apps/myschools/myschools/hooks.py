app_name = "myschools"
app_title = "MY School ERP"
app_publisher = "MY School Pakistan"
app_description = "Multi-tier franchise school management system for myschools.pk: Head Office → Cluster → Branch → Campus → Students/Parents"
app_email = "info@myschools.pk"
app_license = "agpl-3.0"

required_apps = ["erpnext", "education"]

# Installation lifecycle
# ----------------------
after_install = "myschools.setup.install.after_install"
after_migrate = ["myschools.setup.install.after_migrate"]

# Document events
# ---------------
doc_events = {
	"Student": {
		"before_insert": "myschools.api.identity.set_mys_student_id",
		"validate": "myschools.api.identity.validate_student_franchise_links",
	},
	"Employee": {
		"before_insert": "myschools.api.identity.set_mys_staff_id",
	},
	"Guardian": {
		"validate": "myschools.api.identity.sync_guardian_branch",
	},
}

# Permission query conditions for branch-scoped data isolation
# ------------------------------------------------------------
permission_query_conditions = {
	"Student": "myschools.api.permissions.student_query",
	"MYS Branch": "myschools.api.permissions.branch_query",
	"MYS Campus": "myschools.api.permissions.campus_query",
	"MYS Inspection Visit": "myschools.api.permissions.inspection_query",
	"MYS Franchise Agreement": "myschools.api.royalty.franchise_agreement_query",
	"MYS Royalty Rate Override": "myschools.api.royalty.rate_override_query",
	"MYS Royalty Invoice": "myschools.api.royalty.royalty_invoice_query",
	"MYS Royalty Payment": "myschools.api.royalty.royalty_payment_query",
}

has_permission = {
	"Student": "myschools.api.permissions.student_has_permission",
}

# Scheduled jobs
# --------------
scheduler_events = {
	"cron": {
		# 03:00 on the 1st of every month — generate prior-month royalty invoices
		"0 3 1 * *": [
			"myschools.api.royalty.scheduled_monthly_royalty_run",
		],
	},
}

# Fixtures (exported with `bench export-fixtures`)
# -----------------------------------------------
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["name", "like", "%-mys_%"]],
	},
	{
		"dt": "Role",
		"filters": [
			[
				"name",
				"in",
				[
					"Chief Executive",
					"HO Dept Head",
					"Cluster Director",
					"Academic Monitor",
					"Audit Officer",
					"Branch Director",
					"Branch Principal",
					"Branch Admin",
					"Branch Accountant",
					"Campus Incharge",
				],
			]
		],
	},
]
