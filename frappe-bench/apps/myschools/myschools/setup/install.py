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


def after_install():
	create_franchise_roles()
	create_custom_franchise_fields()
	create_default_head_office_departments()
	frappe.db.commit()


def after_migrate():
	create_franchise_roles()
	create_custom_franchise_fields()
	frappe.db.commit()


def create_franchise_roles():
	for role_name in FRANCHISE_ROLES:
		if not frappe.db.exists("Role", role_name):
			role = frappe.new_doc("Role")
			role.role_name = role_name
			role.desk_access = 1
			role.insert(ignore_permissions=True)


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
	]

	create_custom_fields(
		{
			"Student": student_fields,
			"Employee": employee_fields,
			"Guardian": guardian_fields,
		},
		ignore_validate=True,
		update=True,
	)
