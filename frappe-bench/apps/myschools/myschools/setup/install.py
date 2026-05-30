"""Install / migrate hooks for the MY School ERP app.

Creates the franchise role hierarchy and the custom fields that link
the upstream `education` and `erpnext` DocTypes (Student, Employee,
Guardian) to our MYS Cluster / Branch / Campus structure.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FRANCHISE_ROLES = [
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
]

# Website-only role for parent/guardian portal (no Desk access).
PORTAL_ROLES = {
	"Guardian": {"desk_access": 0},
}


def after_install():
	create_franchise_roles()
	create_portal_roles()
	create_custom_franchise_fields()
	create_default_head_office_departments()
	grant_franchise_role_permissions()
	backfill_module_profiles()
	# NOTE: `set_default_print_formats` is intentionally NOT called here.
	# Frappe runs `after_install` BEFORE `sync_fixtures`, so the Print Format
	# records don't exist yet — the function would silently no-op. Instead it's
	# wired to `after_sync` (fresh-install path, after fixtures import) and
	# `after_migrate` (upgrade path).
	frappe.db.commit()


def after_sync():
	"""Runs once on fresh install after `sync_fixtures` / `sync_customizations` /
	`sync_dashboards` complete — the only safe point on a clean install at which
	the shipped Print Format records exist in DB."""
	set_default_print_formats()
	frappe.db.commit()


def after_migrate():
	create_franchise_roles()
	create_portal_roles()
	create_custom_franchise_fields()
	grant_franchise_role_permissions()
	backfill_module_profiles()
	backfill_guardian_user_links()
	set_default_print_formats()
	frappe.db.commit()


DEFAULT_PRINT_FORMATS = {
	"MYS Royalty Invoice": "MYS Royalty Invoice",
	"MYS Inspection Visit": "MYS Inspection Report",
	"MYS Franchise Agreement": "MYS Franchise Agreement",
	"Fees": "MYS Fee Receipt",
}


def set_default_print_formats():
	"""Point each customised doctype's default_print_format at the MYS Print
	Format that ships with this app — runs after fixtures are imported on
	migrate so the target Print Format records already exist. Uses a Property
	Setter so we don't have to edit upstream/owned doctype JSONs."""
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	for doctype, print_format in DEFAULT_PRINT_FORMATS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.db.exists("Print Format", print_format):
			continue
		make_property_setter(
			doctype,
			"",
			"default_print_format",
			print_format,
			"Data",
			for_doctype=True,
			validate_fields_for_doctype=False,
		)


# Doctypes each franchise role needs read access to so the role's workspace
# (shortcuts + number cards) renders something useful. Branch-/cluster-/campus-
# level isolation is enforced separately by `permission_query_conditions` in
# hooks.py — so granting "read" here just gates VISIBILITY of the doctype, while
# row-level scoping decides which rows the user sees.
FRANCHISE_ROLE_READS = {
	"Chief Executive": [
		"MYS Cluster",
		"MYS Branch",
		"MYS Campus",
		"MYS Department",
		"MYS Franchise Owner",
		"MYS Franchise Agreement",
		"MYS Royalty Rate Override",
		"MYS Royalty Invoice",
		"MYS Royalty Payment",
		"MYS Communication Log",
		"MYS Inspection Checklist Template",
		"MYS Inspection Visit",
		"MYS Inspection Finding",
		"MYS Corrective Action",
		"Student",
		"Fees",
		"Fee Structure",
		"Employee",
		"Guardian",
	],
	"HO Dept Head": [
		"MYS Cluster",
		"MYS Branch",
		"MYS Campus",
		"MYS Department",
		"MYS Franchise Agreement",
		"MYS Royalty Invoice",
		"MYS Royalty Payment",
		"MYS Communication Log",
		"MYS Inspection Visit",
		"MYS Inspection Finding",
		"Student",
		"Fees",
		"Employee",
	],
	"Cluster Director": [
		"MYS Cluster",
		"MYS Branch",
		"MYS Campus",
		"MYS Franchise Agreement",
		"MYS Royalty Invoice",
		"MYS Royalty Payment",
		"MYS Communication Log",
		"MYS Inspection Visit",
		"MYS Inspection Finding",
		"MYS Corrective Action",
		"Student",
		"Fees",
		"Employee",
	],
	"Academic Monitor": [
		"MYS Branch",
		"MYS Campus",
		"MYS Cluster",
		"MYS Communication Log",
		"MYS Inspection Checklist Template",
		"MYS Inspection Visit",
		"MYS Inspection Finding",
		"MYS Corrective Action",
	],
	"Audit Officer": [
		"MYS Branch",
		"MYS Campus",
		"MYS Cluster",
		"MYS Communication Log",
		"MYS Inspection Checklist Template",
		"MYS Inspection Visit",
		"MYS Inspection Finding",
		"MYS Corrective Action",
	],
	"Branch Director": [
		"MYS Branch",
		"MYS Campus",
		"MYS Communication Log",
		"MYS Royalty Invoice",
		"MYS Royalty Payment",
		"MYS Inspection Visit",
		"MYS Inspection Finding",
		"MYS Corrective Action",
		"Student",
		"Fees",
		"Employee",
		"Guardian",
	],
	"Branch Principal": [
		"MYS Branch",
		"MYS Campus",
		"MYS Communication Log",
		"MYS Inspection Visit",
		"MYS Inspection Finding",
		"MYS Corrective Action",
		"Student",
		"Fees",
		"Employee",
		"Guardian",
	],
	"Branch Admin": [
		"MYS Branch",
		"MYS Campus",
		"MYS Communication Log",
		"Student",
		"Fees",
		"Employee",
		"Guardian",
	],
	"Branch Accountant": [
		"MYS Branch",
		"MYS Campus",
		"MYS Communication Log",
		"MYS Royalty Invoice",
		"MYS Royalty Payment",
		"Student",
		"Fees",
	],
	"Campus Incharge": [
		"MYS Campus",
		"MYS Branch",
		"MYS Communication Log",
		"Student",
		"Guardian",
	],
	"Guardian": [
		"Guardian",
		"Student",
		"Fees",
	],
}


def grant_franchise_role_permissions():
	"""Grant read perms on the doctypes each franchise role needs to see their
	workspace's shortcuts and number cards. Uses Custom DocPerm so we don't have
	to edit per-doctype JSON files. Idempotent — re-running is a no-op."""
	from frappe.permissions import add_permission, update_permission_property

	for role, doctypes in FRANCHISE_ROLE_READS.items():
		if not frappe.db.exists("Role", role):
			continue
		for doctype in doctypes:
			if not frappe.db.exists("DocType", doctype):
				continue
			# add_permission returns the DocPerm name (existing or new); we then
			# enforce the read=1 flag idempotently.
			add_permission(doctype, role, 0)
			update_permission_property(doctype, role, 0, "read", 1)


def backfill_module_profiles():
	"""Attach the right MYS Module Profile to every existing user — called
	on `after_migrate` so a fresh install of this app applies sidebar scoping
	to users who were created before the profiles were shipped."""
	from myschools.api.user_profile import backfill_existing_users

	backfill_existing_users()


def create_franchise_roles():
	for role_name in FRANCHISE_ROLES:
		if not frappe.db.exists("Role", role_name):
			role = frappe.new_doc("Role")
			role.role_name = role_name
			role.desk_access = 1
			role.insert(ignore_permissions=True)


def create_portal_roles():
	for role_name, opts in PORTAL_ROLES.items():
		if frappe.db.exists("Role", role_name):
			frappe.db.set_value("Role", role_name, "desk_access", opts.get("desk_access", 0))
			continue
		role = frappe.new_doc("Role")
		role.role_name = role_name
		role.desk_access = opts.get("desk_access", 0)
		role.insert(ignore_permissions=True)


def backfill_guardian_user_links():
	from myschools.api.identity import backfill_guardian_user_links as _run

	_run()


def create_default_head_office_departments():
	defaults = ["Monitoring", "Academic", "Finance", "Training", "Administration", "Marketing", "IT"]
	for name in defaults:
		if not frappe.db.exists("MYS Department", name):
			doc = frappe.new_doc("MYS Department")
			doc.dept_name = name
			doc.tier = "Head Office"
			doc.is_active = 1
			doc.insert(ignore_permissions=True)


def create_custom_franchise_fields():
	"""Adds mys_cluster / mys_branch / mys_campus / mys_student_id etc to
	upstream DocTypes."""

	student_fields = [
		{
			"fieldname": "mys_franchise_section",
			"label": "MY School Franchise",
			"fieldtype": "Section Break",
			"insert_after": "image",
			"collapsible": 1,
		},
		{
			"fieldname": "mys_cluster",
			"label": "Cluster",
			"fieldtype": "Link",
			"options": "MYS Cluster",
			"insert_after": "mys_franchise_section",
			"in_list_view": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "mys_branch",
			"label": "Branch",
			"fieldtype": "Link",
			"options": "MYS Branch",
			"insert_after": "mys_cluster",
			"in_list_view": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "mys_column_break",
			"fieldtype": "Column Break",
			"insert_after": "mys_branch",
		},
		{
			"fieldname": "mys_campus",
			"label": "Campus",
			"fieldtype": "Link",
			"options": "MYS Campus",
			"insert_after": "mys_column_break",
			"in_standard_filter": 1,
		},
		{
			"fieldname": "mys_student_id",
			"label": "MYS Student ID",
			"fieldtype": "Data",
			"insert_after": "mys_campus",
			"read_only": 1,
			"in_list_view": 1,
			"unique": 1,
			"description": "Auto-generated as MYS-{cluster}-{branch}-STU{######}",
		},
	]

	employee_fields = [
		{
			"fieldname": "mys_franchise_section",
			"label": "MY School Franchise",
			"fieldtype": "Section Break",
			"insert_after": "company_email",
			"collapsible": 1,
		},
		{
			"fieldname": "mys_role_tier",
			"label": "MYS Role Tier",
			"fieldtype": "Select",
			"options": "\nHead Office\nCluster\nBranch\nCampus",
			"insert_after": "mys_franchise_section",
			"in_list_view": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "mys_branch",
			"label": "Branch",
			"fieldtype": "Link",
			"options": "MYS Branch",
			"insert_after": "mys_role_tier",
			"in_standard_filter": 1,
		},
		{
			"fieldname": "mys_column_break",
			"fieldtype": "Column Break",
			"insert_after": "mys_branch",
		},
		{
			"fieldname": "mys_campus",
			"label": "Campus",
			"fieldtype": "Link",
			"options": "MYS Campus",
			"insert_after": "mys_column_break",
		},
		{
			"fieldname": "mys_staff_id",
			"label": "MYS Staff ID",
			"fieldtype": "Data",
			"insert_after": "mys_campus",
			"read_only": 1,
			"unique": 1,
			"description": "Auto-generated as MYS-{branch}-{TCH|ADM|PRN...}{####}",
		},
	]

	guardian_fields = [
		{
			"fieldname": "mys_branch",
			"label": "MYS Branch",
			"fieldtype": "Link",
			"options": "MYS Branch",
			"insert_after": "education",
			"in_standard_filter": 1,
		},
		{
			"fieldname": "user",
			"label": "Portal User",
			"fieldtype": "Link",
			"options": "User",
			"insert_after": "mys_branch",
			"read_only": 1,
			"description": "Website User login linked to this guardian (auto-set when email matches).",
		},
	]

	# Workaround for upstream Frappe Education v15.5.3 bug:
	# `Fees.income_account` declares `fetch_from: "fee_structure.income_account"`,
	# but `tabFee Structure` has no `income_account` column. Frappe's link
	# validation issues `SELECT name, income_account FROM tabFeeStructure`,
	# which crashes with 1054 Unknown column. Adding the field as a Custom
	# Field gives the SELECT a real column to read.
	fee_structure_fields = [
		{
			"fieldname": "income_account",
			"label": "Income Account",
			"fieldtype": "Link",
			"options": "Account",
			"insert_after": "receivable_account",
			"description": "Optional; declared by upstream Fees.fetch_from. Leave blank to use the Company default.",
		},
	]

	create_custom_fields(
		{
			"Student": student_fields,
			"Employee": employee_fields,
			"Guardian": guardian_fields,
			"Fee Structure": fee_structure_fields,
		},
		ignore_validate=True,
		update=True,
	)
