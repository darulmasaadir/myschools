app_name = "myschools"
app_title = "MY School ERP"
app_publisher = "MY School Pakistan"
app_description = "Multi-tier franchise school management system for myschools.pk: Head Office → Cluster → Branch → Campus → Students/Parents"
app_email = "info@myschools.pk"
app_license = "agpl-3.0"

required_apps = ["erpnext", "education"]

# Brand
# -----
app_logo_url = "/assets/myschools/images/mys-logo.svg"
brand_html = '<img src="/assets/myschools/images/mys-logo.svg" alt="MY Schools" style="height:24px;vertical-align:middle">'
website_context = {
	"favicon": "/assets/myschools/images/mys-favicon.svg",
	"splash_image": "/assets/myschools/images/mys-splash.svg",
}
app_include_css = ["/assets/myschools/css/myschools.css"]
web_include_css = ["/assets/myschools/css/myschools.css"]

# Installation lifecycle
# ----------------------
after_install = "myschools.setup.install.after_install"
# `after_sync` fires on fresh `bench install-app` AFTER fixtures are imported,
# which is the only moment we can wire `default_print_format` Property Setters
# referencing our shipped Print Formats. `after_install` is too early — fixtures
# haven't loaded yet — so the Property-Setter step lives in `after_sync` for
# fresh installs and `after_migrate` for upgrades.
after_sync = "myschools.setup.install.after_sync"
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
	"User": {
		"validate": "myschools.api.user_profile.attach_module_profile_to_user",
	},
}

# Role-based landing pages
# ------------------------
role_home_page = {
	"Chief Executive": "mys-head-office",
	"HO Dept Head": "mys-head-office",
	"Cluster Director": "mys-cluster",
	"Academic Monitor": "mys-inspection",
	"Audit Officer": "mys-inspection",
	"Branch Director": "mys-branch",
	"Branch Principal": "mys-branch",
	"Branch Admin": "mys-branch",
	"Branch Accountant": "mys-branch",
	"Campus Incharge": "mys-campus",
}

# Permission query conditions for branch-scoped data isolation
# ------------------------------------------------------------
permission_query_conditions = {
	"Student": "myschools.api.permissions.student_query",
	"MYS Branch": "myschools.api.permissions.branch_query",
	"MYS Campus": "myschools.api.permissions.campus_query",
	"MYS Inspection Visit": "myschools.api.permissions.inspection_query",
	"MYS Inspection Finding": "myschools.api.inspection.finding_query",
	"MYS Corrective Action": "myschools.api.inspection.corrective_action_query",
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
	{"dt": "Workspace", "filters": [["name", "like", "mys-%"]]},
	{"dt": "Module Profile", "filters": [["name", "like", "MYS %"]]},
	{"dt": "Letter Head", "filters": [["name", "like", "MYS%"]]},
	{"dt": "Print Format", "filters": [["name", "like", "MYS %"]]},
	{
		"dt": "Property Setter",
		"filters": [
			[
				"doc_type",
				"in",
				[
					"MYS Royalty Invoice",
					"MYS Inspection Visit",
					"MYS Franchise Agreement",
					"Fees",
				],
			],
			["property", "=", "default_print_format"],
		],
	},
	{"dt": "Dashboard", "filters": [["name", "like", "MYS %"]]},
	{"dt": "Dashboard Chart", "filters": [["name", "like", "MYS - %"]]},
	{"dt": "Number Card", "filters": [["name", "like", "MYS - %"]]},
]
