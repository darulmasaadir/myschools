"""Run via:
  bench --site myschools.localhost execute myschools.scripts.seed_test_users.run

Creates one System User per franchise role with a known dev password so you can
manually verify the role-aware shell (workspace landing, sidebar scoping).

Idempotent — re-running keeps existing users and resets their password.

DO NOT USE IN PRODUCTION. The shared password is for local development only.
"""

import frappe

DEV_PASSWORD = "admin"

TEST_USERS = [
	("ceo@mys.local", "Cynthia", "Executive", "Chief Executive"),
	("ho.head@mys.local", "Hira", "Head", "HO Dept Head"),
	("cluster.dir@mys.local", "Cyrus", "Director", "Cluster Director"),
	("monitor@mys.local", "Maham", "Monitor", "Academic Monitor"),
	("audit@mys.local", "Asad", "Auditor", "Audit Officer"),
	("branch.dir@mys.local", "Bilal", "Director", "Branch Director"),
	("principal@mys.local", "Parveen", "Principal", "Branch Principal"),
	("branch.admin@mys.local", "Adeel", "Admin", "Branch Admin"),
	("accountant@mys.local", "Aliya", "Accountant", "Branch Accountant"),
	("campus@mys.local", "Komal", "Incharge", "Campus Incharge"),
]


def run():
	for email, first_name, last_name, role in TEST_USERS:
		if frappe.db.exists("User", email):
			user = frappe.get_doc("User", email)
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

	frappe.db.commit()
	_print_summary()


def _print_summary():
	print("\nTest users (password: admin)\n")
	print(f"  {'Email':<30}  {'Role':<22}  {'Lands on':<22}  Module Profile")
	print("  " + "-" * 92)

	role_home = frappe.get_hooks("role_home_page") or {}
	for email, _, _, role in TEST_USERS:
		home = role_home.get(role)
		if isinstance(home, list):
			home = home[0] if home else ""
		profile = frappe.db.get_value("User", email, "module_profile") or "-"
		print(f"  {email:<30}  {role:<22}  /app/{home:<17}  {profile}")
	print()
