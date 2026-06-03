"""Smoke user for Phase 7d inspection portal.

Run:
    bench --site SITE execute myschools.scripts.seed_portal_inspection.main
"""

import frappe
from frappe.utils import today

EMAIL = "mys-portal-smoke-monitor@test.local"
PASSWORD = "mys-portal-smoke"


def main():
	branch = frappe.db.get_value("MYS Branch", {}, "name")
	if not branch:
		print("No MYS Branch on site — run seed_demo first.")
		return

	if not frappe.db.exists("User", EMAIL):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": EMAIL,
				"first_name": "Portal",
				"last_name": "Monitor",
				"send_welcome_email": 0,
				"user_type": "System User",
			}
		)
		user.append("roles", {"role": "Academic Monitor"})
		user.insert(ignore_permissions=True)
	else:
		user = frappe.get_doc("User", EMAIL)
		if not any(r.role == "Academic Monitor" for r in user.roles):
			user.append("roles", {"role": "Academic Monitor"})
			user.save(ignore_permissions=True)

	from frappe.utils.password import update_password

	update_password(EMAIL, PASSWORD)

	emp = frappe.db.get_value("Employee", {"user_id": EMAIL}, "name")
	company = frappe.db.get_value("MYS Branch", branch, "company") or frappe.db.get_value(
		"Company", {}, "name"
	)
	if not emp:
		frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": "Portal",
				"last_name": "Monitor",
				"gender": "Male",
				"date_of_birth": "1985-01-01",
				"date_of_joining": today(),
				"status": "Active",
				"company": company,
				"user_id": EMAIL,
				"mys_branch": branch,
			}
		).insert(ignore_permissions=True)
	else:
		frappe.db.set_value("Employee", emp, {"mys_branch": branch, "status": "Active"})

	frappe.db.commit()
	print(f"Inspection portal smoke user: {EMAIL} / {PASSWORD}")
	print(f"Linked to branch: {branch}")
	print("Open: /inspection (after login)")
