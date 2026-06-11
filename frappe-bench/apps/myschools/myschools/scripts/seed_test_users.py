"""Run via:
  bench --site myschools.localhost execute myschools.scripts.seed_test_users.run

Creates one System User per franchise role with a known dev password so you can
manually verify the role-aware shell (workspace landing, sidebar scoping).

Branch-scoped users (Director / Principal / Admin / Accountant / Campus Incharge /
Campus Admin) also get an idempotent Employee row linked to the first MYS Branch
on the site, so the same credentials work on the mobile `/branch` portal — which
scopes data via `Employee.user_id` + `Employee.mys_branch` (see api/branch_portal.py).

Idempotent — re-running keeps existing users/Employees and resets the password.

DO NOT USE IN PRODUCTION. The shared password is for local development only.
"""

import frappe
from frappe.utils import today

from myschools.setup.install import migrate_legacy_ho_dept_head
from myschools.setup.role_model import CAMPUS_ADMIN_ROLE, LEGACY_HO_DEPT_HEAD

DEV_PASSWORD = "admin"

TEST_USERS = [
	("ceo@mys.local", "Cynthia", "Executive", "Chief Executive"),
	("finance.head@mys.local", "Farah", "Finance", "Finance Dept Head"),
	("academic.head@mys.local", "Amjad", "Academic", "Academic Dept Head"),
	("monitoring.head@mys.local", "Mona", "Monitoring", "Monitoring Dept Head"),
	("admin.head@mys.local", "Adnan", "Administration", "Administration Dept Head"),
	("training.head@mys.local", "Tariq", "Training", "Training Dept Head"),
	("cluster.dir@mys.local", "Cyrus", "Director", "Cluster Director"),
	("monitor@mys.local", "Maham", "Monitor", "Academic Monitor"),
	("audit@mys.local", "Asad", "Auditor", "Audit Officer"),
	("branch.dir@mys.local", "Bilal", "Director", "Branch Director"),
	("principal@mys.local", "Parveen", "Principal", "Branch Principal"),
	("branch.admin@mys.local", "Adeel", "Admin", "Branch Admin"),
	("accountant@mys.local", "Aliya", "Accountant", "Branch Accountant"),
	("campus@mys.local", "Komal", "Incharge", "Campus Incharge"),
	("campus.admin@mys.local", "Sana", "Admin", CAMPUS_ADMIN_ROLE),
]

BRANCH_SCOPED_ROLES = {
	"Branch Director",
	"Branch Principal",
	"Branch Admin",
	"Branch Accountant",
	"Campus Incharge",
	CAMPUS_ADMIN_ROLE,
}

INSPECTION_SCOPED_ROLES = {
	"Academic Monitor",
	"Audit Officer",
	"Cluster Director",
}


def run():
	migrate_legacy_ho_dept_head()
	for email, first_name, last_name, role in TEST_USERS:
		if frappe.db.exists("User", email):
			user = frappe.get_doc("User", email)
			if LEGACY_HO_DEPT_HEAD in {r.role for r in user.roles}:
				user.remove_roles(LEGACY_HO_DEPT_HEAD)
			if not any(r.role == role for r in user.roles):
				user.append("roles", {"role": role})
				user.save(ignore_permissions=True)
		else:
			user = frappe.new_doc("User")
			user.email = email
			user.first_name = first_name
			user.last_name = last_name
			user.send_welcome_email = 0
			user.user_type = "System User"
			user.enabled = 1
			user.append("roles", {"role": role})
			user.insert(ignore_permissions=True)

		from frappe.utils.password import update_password

		update_password(email, DEV_PASSWORD)

		if role in BRANCH_SCOPED_ROLES or role in INSPECTION_SCOPED_ROLES:
			_ensure_employee(email, first_name, last_name)

	from myschools.api.lms import ensure_default_desk_app

	ensure_default_desk_app()
	frappe.db.commit()
	_print_summary()


def _ensure_employee(email: str, first_name: str, last_name: str) -> str | None:
	"""Ensure an Employee row linked to `email` exists, joined to a MYS Branch."""
	branch = frappe.db.get_value("MYS Branch", {}, "name")
	if not branch:
		return None
	company = frappe.db.get_value("MYS Branch", branch, "company") or frappe.db.get_value(
		"Company", {}, "name"
	)

	existing = frappe.db.get_value("Employee", {"user_id": email}, "name")
	if existing:
		updates = {"status": "Active"}
		current_branch = frappe.db.get_value("Employee", existing, "mys_branch")
		if not current_branch:
			updates["mys_branch"] = branch
		frappe.db.set_value("Employee", existing, updates)
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": first_name,
			"last_name": last_name,
			"gender": "Male",
			"date_of_birth": "1985-01-01",
			"date_of_joining": today(),
			"status": "Active",
			"company": company,
			"user_id": email,
			"mys_branch": branch,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _print_summary():
	print("\nTest users (password: admin)\n")
	print(f"  {'Email':<32}  {'Role':<24}  {'Lands on':<22}  Module Profile")
	print("  " + "-" * 96)

	role_home = frappe.get_hooks("role_home_page") or {}
	for email, _, _, role in TEST_USERS:
		home = role_home.get(role)
		if isinstance(home, list):
			home = home[0] if home else ""
		profile = frappe.db.get_value("User", email, "module_profile") or "-"
		print(f"  {email:<32}  {role:<24}  /app/{home:<17}  {profile}")
	print()
