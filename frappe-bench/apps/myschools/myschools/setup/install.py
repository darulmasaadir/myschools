"""Install / migrate hooks for the MY School ERP app.

Creates the franchise role hierarchy and the custom fields that link
the upstream `education` and `erpnext` DocTypes (Student, Employee,
Guardian) to our MYS Cluster / Branch / Campus structure.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from myschools.api.library import ensure_library_fine_category
from myschools.api.lms import (
	ensure_default_desk_app,
	ensure_lms_course_permissions,
	ensure_lms_franchise_role_links,
)
from myschools.api.transport import ensure_transport_fee_category

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
	"Teacher",
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
	restrict_split_brain_billing_paths()
	backfill_module_profiles()
	# Transport Fee Category is created in `after_migrate` (not here): Education's
	# Fee Category hook creates an ERPNext Item which needs stock UOM — absent on
	# a bare `after_install` during fresh CI install-app.
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
	restrict_split_brain_billing_paths()
	backfill_custom_number_card_document_types()
	sync_workspace_number_card_content_labels()
	sync_mys_branch_fee_admin_workspace()
	backfill_module_profiles()
	backfill_guardian_user_links()
	ensure_transport_fee_category()
	ensure_library_fine_category()
	ensure_lms_course_permissions()
	ensure_lms_franchise_role_links()
	ensure_default_desk_app()
	set_default_print_formats()
	frappe.db.commit()


# Frappe's Number Card `has_permission` requires Custom cards to declare which
# DocType gates visibility (`document_type`). Without it, franchise roles with
# read on the underlying data still can't see the card on desk workspaces.
CUSTOM_NUMBER_CARD_DOCUMENT_TYPES = {
	"MYS - This Month Royalty Invoiced": "MYS Royalty Invoice",
	"MYS - This Month Fees Collected": "Fees",
	"MYS - Overdue Findings": "MYS Inspection Finding",
}


def backfill_custom_number_card_document_types():
	"""Set `document_type` on Custom Number Cards shipped without it (idempotent)."""
	for name, doctype in CUSTOM_NUMBER_CARD_DOCUMENT_TYPES.items():
		if not frappe.db.exists("Number Card", name):
			continue
		if not frappe.db.exists("DocType", doctype):
			continue
		current = frappe.db.get_value("Number Card", name, "document_type")
		if current != doctype:
			frappe.db.set_value("Number Card", name, "document_type", doctype, update_modified=False)


def sync_workspace_number_card_content_labels():
	"""Desk workspace blocks match Number Cards by workspace row `label`, not doc name.

	Frappe's workspace `content` JSON stores the value in `number_card_name`, but
	`block.js` compares it to `Workspace Number Card.label`. Early MYS fixtures
	used the Number Card document name (e.g. `MYS - Active Students`) — widgets
	never mounted. Rewrite content blocks to use the child-table label.
	"""
	import json

	for ws_name in frappe.get_all("Workspace", filters={"name": ["like", "mys-%"]}, pluck="name"):
		ws = frappe.get_doc("Workspace", ws_name)
		if not ws.content or not ws.number_cards:
			continue
		name_to_label = {row.number_card_name: (row.label or row.number_card_name) for row in ws.number_cards}
		content = json.loads(ws.content)
		changed = False
		for block in content:
			if block.get("type") != "number_card":
				continue
			current = block.get("data", {}).get("number_card_name")
			label = name_to_label.get(current)
			if label and current != label:
				block["data"]["number_card_name"] = label
				changed = True
		if changed:
			frappe.db.set_value("Workspace", ws_name, "content", json.dumps(content))


MYS_BRANCH_WORKSPACE = "mys-branch"
_BRANCH_FEE_ADMIN_SHORTCUT = {
	"color": "Cyan",
	"doc_view": "List",
	"label": "Bulk Fee Run",
	"link_to": "MYS Bulk Fee Run",
	"type": "DocType",
}
_BRANCH_FEE_ADMIN_LINKS = [
	("Bulk Fee Run", "MYS Bulk Fee Run"),
	("Fee Structure Override", "MYS Fee Structure Override"),
	("Late Fee Policy", "MYS Late Fee Policy"),
]
_BRANCH_STUDENT_LIFECYCLE_LINKS = [
	("Student Transfer", "MYS Student Transfer"),
	("Student Leaving", "MYS Student Leaving"),
]


def sync_mys_branch_fee_admin_workspace():
	"""Ensure Phase 8a fee-admin shortcuts/links exist on the MYS Branch workspace.

	Module JSON under my_school_erp/workspace/ only applies on first insert; existing
	sites keep the old workspace until we patch it here (same pattern as number-card
	content labels). Idempotent — safe on every migrate.
	"""
	import json

	if not frappe.db.exists("Workspace", MYS_BRANCH_WORKSPACE):
		return

	ws = frappe.get_doc("Workspace", MYS_BRANCH_WORKSPACE)
	changed = False

	labels = {row.label for row in ws.shortcuts}
	if _BRANCH_FEE_ADMIN_SHORTCUT["label"] not in labels:
		ws.append("shortcuts", dict(_BRANCH_FEE_ADMIN_SHORTCUT))
		changed = True

	existing_links = {(row.label, row.link_to) for row in ws.links if row.type == "Link"}
	for label, link_to in _BRANCH_FEE_ADMIN_LINKS + _BRANCH_STUDENT_LIFECYCLE_LINKS:
		if not frappe.db.exists("DocType", link_to):
			continue
		if (label, link_to) not in existing_links:
			ws.append(
				"links",
				{
					"hidden": 0,
					"is_query_report": 0,
					"label": label,
					"link_count": 0,
					"link_to": link_to,
					"link_type": "DocType",
					"onboard": 0,
					"type": "Link",
				},
			)
			changed = True

	content = json.loads(ws.content or "[]")
	block_vals = {
		block.get("data", {}).get("shortcut_name") for block in content if block.get("type") == "shortcut"
	}
	if _BRANCH_FEE_ADMIN_SHORTCUT["label"] not in block_vals:
		insert_at = next(
			(
				i + 1
				for i, block in enumerate(content)
				if block.get("type") == "shortcut" and block.get("data", {}).get("shortcut_name") == "Fees"
			),
			len(content),
		)
		content.insert(
			insert_at,
			{
				"id": "sc-bulk-fees",
				"type": "shortcut",
				"data": {"shortcut_name": _BRANCH_FEE_ADMIN_SHORTCUT["label"], "col": 3},
			},
		)
		ws.content = json.dumps(content)
		changed = True

	if changed:
		ws.flags.ignore_validate = True
		ws.save(ignore_permissions=True)


DEFAULT_PRINT_FORMATS = {
	"MYS Royalty Invoice": "MYS Royalty Invoice",
	"MYS Inspection Visit": "MYS Inspection Report",
	"MYS Franchise Agreement": "MYS Franchise Agreement",
	"Fees": "MYS Fee Receipt",
	"Assessment Result": "MYS Report Card",
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
		"MYS Bulk Fee Run",
		"MYS Fee Structure Override",
		"MYS Late Fee Policy",
		"MYS Student Transfer",
		"MYS Student Leaving",
		"Student",
		"Fees",
		"Employee",
		"Guardian",
	],
	"Branch Principal": [
		"MYS Branch",
		"MYS Campus",
		"MYS Communication Log",
		"MYS Royalty Invoice",
		"MYS Royalty Payment",
		"MYS Inspection Visit",
		"MYS Inspection Finding",
		"MYS Corrective Action",
		"MYS Student Transfer",
		"MYS Student Leaving",
		"Student",
		"Fees",
		"Employee",
		"Guardian",
	],
	"Branch Admin": [
		"MYS Branch",
		"MYS Campus",
		"MYS Communication Log",
		"MYS Royalty Invoice",
		"MYS Royalty Payment",
		"MYS Inspection Visit",
		"MYS Inspection Finding",
		"MYS Bulk Fee Run",
		"MYS Fee Structure Override",
		"MYS Late Fee Policy",
		"MYS Student Transfer",
		"MYS Student Leaving",
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
		"MYS Inspection Visit",
		"MYS Inspection Finding",
		"MYS Bulk Fee Run",
		"MYS Fee Structure Override",
		"MYS Late Fee Policy",
		"MYS Student Transfer",
		"MYS Student Leaving",
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
		"Student Attendance",
		"MYS Communication Log",
	],
	"Teacher": [
		"Student",
		"Student Group",
		"Course Schedule",
		"Instructor",
		"Program",
		"Student Attendance",
		"Assessment Plan",
		"Assessment Result",
	],
}

# Fee-admin roles need read on the link-target doctypes their Phase 8a forms
# (MYS Bulk Fee Run / Fee Structure Override / Late Fee Policy) reference —
# otherwise desk link-field validation rejects the values and the forms can't
# be filled or saved in the browser. Read-only; row scoping is unaffected.
_FEE_ADMIN_LINK_READS = [
	"Program",
	"Academic Year",
	"Academic Term",
	"Fee Structure",
	"Student Group",
	"Fee Category",
]
for _role in ("Branch Director", "Branch Accountant", "Branch Admin"):
	for _dt in _FEE_ADMIN_LINK_READS:
		if _dt not in FRANCHISE_ROLE_READS[_role]:
			FRANCHISE_ROLE_READS[_role].append(_dt)

# Enrollment desk: branch staff create Program Enrollment (Education upstream doctype).
for _role in ("Branch Director", "Branch Principal", "Branch Admin"):
	if "Program Enrollment" not in FRANCHISE_ROLE_READS[_role]:
		FRANCHISE_ROLE_READS[_role].append("Program Enrollment")

# Timetable desk reads (Phase 11): branch roles see schedules for their groups;
# row scope is enforced by course_schedule_query / student_group_query.
_SCHEDULING_READS = ("Course Schedule", "Student Group", "Instructor", "Program", "Room")
for _role in ("Branch Director", "Branch Principal", "Branch Admin", "Branch Accountant"):
	for _dt in _SCHEDULING_READS:
		if _dt not in FRANCHISE_ROLE_READS[_role]:
			FRANCHISE_ROLE_READS[_role].append(_dt)

# Transport desk (Phase 12): branch roles manage vehicles/routes/assignments;
# create/write come from the doctype JSON perms, row scope from transport queries.
_TRANSPORT_READS = ("MYS Vehicle", "MYS Transport Route", "MYS Student Transport")
for _role in ("Branch Director", "Branch Principal", "Branch Admin", "Branch Accountant"):
	for _dt in _TRANSPORT_READS:
		if _dt not in FRANCHISE_ROLE_READS[_role]:
			FRANCHISE_ROLE_READS[_role].append(_dt)

# Library desk (Phase 13): branch roles manage catalog + loans; row scope from library queries.
_LIBRARY_READS = ("MYS Library Item", "MYS Library Loan")
for _role in ("Branch Director", "Branch Principal", "Branch Admin", "Branch Accountant"):
	for _dt in _LIBRARY_READS:
		if _dt not in FRANCHISE_ROLE_READS[_role]:
			FRANCHISE_ROLE_READS[_role].append(_dt)

# Document registry (Phase 14): branch roles manage compliance docs; row scope from document_query.
_DOCUMENT_READS = ("MYS Document",)
for _role in (
	"Branch Director",
	"Branch Principal",
	"Branch Admin",
	"Branch Accountant",
	"Audit Officer",
	"Cluster Director",
	"HO Dept Head",
):
	for _dt in _DOCUMENT_READS:
		if _dt not in FRANCHISE_ROLE_READS[_role]:
			FRANCHISE_ROLE_READS[_role].append(_dt)

# LMS desk (Phase 15): branch roles see/create franchise-scoped LMS courses.
_LMS_COURSE_READS = ("LMS Course",)
for _role in (
	"Branch Director",
	"Branch Principal",
	"Branch Admin",
	"Branch Accountant",
	"Audit Officer",
	"Cluster Director",
	"HO Dept Head",
	"Chief Executive",
):
	for _dt in _LMS_COURSE_READS:
		if _dt not in FRANCHISE_ROLE_READS[_role]:
			FRANCHISE_ROLE_READS[_role].append(_dt)

# Payroll oversight (Phase 8d): branch finance roles + HO/cluster read Payroll
# Entry (frappe/hrms); row scope is enforced by api.hr.payroll_entry_query so
# each role only sees their own branch/cluster runs. Creating payroll still uses
# the stock hrms HR roles. Granted only when hrms is installed (guarded in
# grant_franchise_role_permissions via the DocType existence check).
for _role in (
	"Chief Executive",
	"HO Dept Head",
	"Cluster Director",
	"Branch Director",
	"Branch Accountant",
):
	if "Payroll Entry" not in FRANCHISE_ROLE_READS[_role]:
		FRANCHISE_ROLE_READS[_role].append("Payroll Entry")


# Education bulk billing paths that create Sales Invoice — not read by MY School.
SPLIT_BRAIN_BILLING_DOCTYPES = ("Fee Schedule", "Sales Invoice")
SPLIT_BRAIN_DENIED_PERMS = ("create", "write", "submit", "cancel", "amend", "delete", "import")


def restrict_split_brain_billing_paths():
	"""Deny franchise roles create/write on Fee Schedule and Sales Invoice (8a-2).

	Canonical billing is Education `Fees` (see docs/processes/billing-model.md).
	Module profiles also hide the Accounts module from branch/cluster sidebars;
	this hook ensures roles cannot create bulk SI / fee schedules even if they
	inherit stock ERPNext roles like Accounts User.
	"""
	from frappe.permissions import add_permission, update_permission_property

	for doctype in SPLIT_BRAIN_BILLING_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		for role in FRANCHISE_ROLES:
			if not frappe.db.exists("Role", role):
				continue
			add_permission(doctype, role, 0)
			for perm in SPLIT_BRAIN_DENIED_PERMS:
				update_permission_property(doctype, role, 0, perm, 0)


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

	# Branch fee admins create individual Fees on desk (8a-3 validate + orange alert).
	if frappe.db.exists("DocType", "Fees"):
		for role in ("Branch Director", "Branch Principal", "Branch Admin", "Branch Accountant"):
			if not frappe.db.exists("Role", role):
				continue
			add_permission("Fees", role, 0)
			for perm in ("read", "create", "write"):
				update_permission_property("Fees", role, 0, perm, 1)
			for link_dt in ("Account", "Company", "Program Enrollment"):
				if frappe.db.exists("DocType", link_dt):
					add_permission(link_dt, role, 0)
					update_permission_property(link_dt, role, 0, "read", 1)
			if role in ("Branch Director", "Branch Principal", "Branch Admin") and frappe.db.exists(
				"DocType", "Program Enrollment"
			):
				add_permission("Program Enrollment", role, 0)
				for perm in ("read", "create", "write", "submit"):
					update_permission_property("Program Enrollment", role, 0, perm, 1)

	# Teacher portal: marking attendance + assessment results via whitelist API.
	if frappe.db.exists("Role", "Teacher"):
		for doctype in ("Student Attendance", "Assessment Result"):
			if not frappe.db.exists("DocType", doctype):
				continue
			add_permission(doctype, "Teacher", 0)
			for perm in ("read", "create", "write", "submit", "cancel"):
				update_permission_property(doctype, "Teacher", 0, perm, 1)
		if frappe.db.exists("DocType", "Assessment Plan"):
			add_permission("Assessment Plan", "Teacher", 0)
			update_permission_property("Assessment Plan", "Teacher", 0, "read", 1)

	# Guardian portal: read attendance + submit feedback via Web Form.
	if frappe.db.exists("Role", "Guardian"):
		if frappe.db.exists("DocType", "MYS Communication Log"):
			add_permission("MYS Communication Log", "Guardian", 0)
			update_permission_property("MYS Communication Log", "Guardian", 0, "read", 1)
			update_permission_property("MYS Communication Log", "Guardian", 0, "create", 1)


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

	fees_fields = [
		{
			"fieldname": "mys_late_fee_for",
			"label": "Late Fee For",
			"fieldtype": "Link",
			"options": "Fees",
			"insert_after": "due_date",
			"read_only": 1,
			"description": "Set on late-fee invoices — points to the overdue parent Fees.",
		},
		{
			"fieldname": "mys_late_fee_applied",
			"label": "Late Fee Applied",
			"fieldtype": "Check",
			"insert_after": "mys_late_fee_for",
			"read_only": 1,
			"default": "0",
			"description": "Set when a late-fee invoice has been generated for this Fees.",
		},
		{
			"fieldname": "mys_transport_for",
			"label": "Transport For",
			"fieldtype": "Link",
			"options": "MYS Student Transport",
			"insert_after": "mys_late_fee_applied",
			"read_only": 1,
			"description": "Set on transport invoices — points to the MYS Student Transport assignment.",
		},
		{
			"fieldname": "mys_library_loan_for",
			"label": "Library Loan For",
			"fieldtype": "Link",
			"options": "MYS Library Loan",
			"insert_after": "mys_transport_for",
			"read_only": 1,
			"description": "Set on library fine invoices — points to the MYS Library Loan.",
		},
	]

	field_map = {
		"Student": student_fields,
		"Employee": employee_fields,
		"Guardian": guardian_fields,
		"Fee Structure": fee_structure_fields,
		"Fees": fees_fields,
	}

	# Payroll Entry ships with frappe/hrms (Phase 8d). Guard so a site without
	# hrms (shouldn't happen — it's in required_apps) doesn't error on install.
	if frappe.db.exists("DocType", "Payroll Entry"):
		field_map["Payroll Entry"] = [
			{
				"fieldname": "mys_branch",
				"label": "MYS Branch",
				"fieldtype": "Link",
				"options": "MYS Branch",
				"insert_after": "company",
				"in_standard_filter": 1,
				"description": "Scope this payroll run to a MY School branch; the run's Company is aligned to the branch's books.",
			},
			{
				"fieldname": "mys_campus",
				"label": "MYS Campus",
				"fieldtype": "Link",
				"options": "MYS Campus",
				"insert_after": "mys_branch",
			},
		]

	# LMS Course ships with frappe/lms (Phase 15). Guard for sites mid-migrate.
	if frappe.db.exists("DocType", "LMS Course"):
		field_map["LMS Course"] = [
			{
				"fieldname": "mys_branch",
				"label": "MYS Branch",
				"fieldtype": "Link",
				"options": "MYS Branch",
				"insert_after": "category",
				"reqd": 1,
				"in_standard_filter": 1,
				"in_list_view": 1,
				"description": "Franchise branch that owns this LMS course.",
			},
			{
				"fieldname": "mys_program",
				"label": "Education Program",
				"fieldtype": "Link",
				"options": "Program",
				"insert_after": "mys_branch",
				"description": "Optional link to the Education Program this course supports.",
			},
		]

	create_custom_fields(
		field_map,
		ignore_validate=True,
		update=True,
	)
