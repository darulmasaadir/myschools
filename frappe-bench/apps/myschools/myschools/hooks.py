app_name = "myschools"
app_title = "MY School ERP"
app_publisher = "MY School Pakistan"
app_description = "Multi-tier franchise school management system for myschools.pk: Head Office → Cluster → Branch → Campus → Students/Parents"
app_email = "info@myschools.pk"
app_license = "agpl-3.0"

required_apps = ["erpnext", "education", "hrms", "payments", "lms"]

# Desk launcher tile — ensures /apps picker has an explicit ERP entry when
# frappe/lms (route /lms) is also installed.
add_to_apps_screen = [
	{
		"name": "myschools",
		"logo": "/assets/myschools/images/mys-logo.svg",
		"title": "MY School ERP",
		"route": "/app",
	}
]

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

# Phase 16 — portal PWA (manifest + service worker at /mys-pwa-sw.js)
page_renderer = ["myschools.api.pwa.ServiceWorkerPageRenderer"]

# Setup wizard
# ------------
# `setup_wizard_requires` loads our JS slide *after* ERPNext's slides
# (operators land on Cluster / Branch / Campus after Company + Region).
# `setup_wizard_stages` runs our Python stage after ERPNext finishes,
# so the Company exists by the time we link the first Branch to it.
setup_wizard_requires = "/assets/myschools/js/setup_wizard.js"
setup_wizard_stages = "myschools.scripts.setup_wizard.get_setup_stages"

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
		"validate": [
			"myschools.api.identity.sync_guardian_branch",
			"myschools.api.identity.link_guardian_user",
		],
	},
	"User": {
		"validate": "myschools.api.user_profile.attach_module_profile_to_user",
	},
	# Mirror outbound system-generated emails (anything tied to an MYS doctype
	# or to Fees) into MYS Communication Log so the audit log is one place,
	# not two. See `api/notifications.log_outbound_email` for the filter rules.
	"Communication": {
		"after_insert": "myschools.api.notifications.log_outbound_email",
	},
	"Fees": {
		"validate": "myschools.api.fees.apply_resolved_fee_structure_on_fees",
	},
	"Program Enrollment": {
		"validate": "myschools.api.student_lifecycle.validate_program_enrollment",
	},
	# Payroll runs (frappe/hrms) post to a branch's Company books — keep the
	# run's Company aligned with its MYS Branch. See api/hr.py.
	"Payroll Entry": {
		"validate": "myschools.api.hr.set_payroll_entry_company_from_branch",
	},
	"LMS Course": {
		"validate": "myschools.api.lms.validate_mys_lms_course",
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
	"Teacher": "teacher",
	"Guardian": "guardian",
}

# Permission query conditions for branch-scoped data isolation
# ------------------------------------------------------------
permission_query_conditions = {
	"Student": "myschools.api.permissions.student_query",
	"Employee": "myschools.api.permissions.employee_query",
	"Payroll Entry": "myschools.api.hr.payroll_entry_query",
	"MYS Branch": "myschools.api.permissions.branch_query",
	"MYS Campus": "myschools.api.permissions.campus_query",
	"MYS Inspection Visit": "myschools.api.permissions.inspection_query",
	"MYS Inspection Finding": "myschools.api.inspection.finding_query",
	"MYS Corrective Action": "myschools.api.inspection.corrective_action_query",
	"MYS Franchise Agreement": "myschools.api.royalty.franchise_agreement_query",
	"MYS Royalty Rate Override": "myschools.api.royalty.rate_override_query",
	"MYS Royalty Invoice": "myschools.api.royalty.royalty_invoice_query",
	"MYS Royalty Payment": "myschools.api.royalty.royalty_payment_query",
	"MYS Fee Structure Override": "myschools.api.fees.fee_structure_override_query",
	"MYS Late Fee Policy": "myschools.api.fees.late_fee_policy_query",
	"MYS Bulk Fee Run": "myschools.api.fees.bulk_fee_run_query",
	"MYS Student Transfer": "myschools.api.student_lifecycle.student_transfer_query",
	"MYS Student Leaving": "myschools.api.student_lifecycle.student_leaving_query",
	"Student Group": "myschools.api.permissions.student_group_query",
	"Course Schedule": "myschools.api.permissions.course_schedule_query",
	"MYS Vehicle": "myschools.api.transport.vehicle_query",
	"MYS Transport Route": "myschools.api.transport.transport_route_query",
	"MYS Student Transport": "myschools.api.transport.student_transport_query",
	"MYS Library Item": "myschools.api.library.library_item_query",
	"MYS Library Loan": "myschools.api.library.library_loan_query",
	"MYS Document": "myschools.api.documents.document_query",
	"LMS Course": "myschools.api.lms.lms_course_query",
}

has_permission = {
	"Student": "myschools.api.permissions.student_has_permission",
	"Employee": "myschools.api.permissions.employee_has_permission",
	"Payroll Entry": "myschools.api.hr.payroll_entry_has_permission",
	"LMS Course": "myschools.api.lms.lms_course_has_permission",
}

# Scheduled jobs
# --------------
scheduler_events = {
	"cron": {
		# 03:00 on the 1st of every month — generate prior-month royalty invoices
		"0 3 1 * *": [
			"myschools.api.royalty.scheduled_monthly_royalty_run",
		],
		# 06:00 daily — late fees on overdue student invoices
		"0 6 * * *": [
			"myschools.api.fees.scheduled_apply_late_fees",
			"myschools.api.library.scheduled_mark_library_overdue",
			"myschools.api.documents.scheduled_mark_documents_expired",
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
					"Guardian",
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
	{"dt": "Module Onboarding", "filters": [["name", "like", "MYS %"]]},
	{"dt": "Onboarding Step", "filters": [["name", "like", "MYS %"]]},
	{"dt": "Report", "filters": [["name", "like", "MYS %"], ["is_standard", "=", "Yes"]]},
	{"dt": "Web Form", "filters": [["route", "like", "guardian-%"]]},
	{"dt": "Email Template", "filters": [["name", "like", "MYS - %"]]},
	{"dt": "Notification", "filters": [["name", "like", "MYS - %"]]},
	{
		"dt": "Workflow State",
		"filters": [
			[
				"name",
				"in",
				[
					"Open",
					"In Progress",
					"Resolved",
					"Verified",
					"Unpaid",
					"Partial",
					"Paid",
					"Overdue",
				],
			]
		],
	},
	{
		"dt": "Workflow Action Master",
		"filters": [
			[
				"name",
				"in",
				["Acknowledge", "Mark Resolved", "Verify", "Reject Resolution"],
			]
		],
	},
	{"dt": "Workflow", "filters": [["name", "like", "MYS %"]]},
]
