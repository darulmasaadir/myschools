"""Idempotent Branch portal smoke user + Employee record for local HTTP checks.

Run via:
    bench --site SITE execute myschools.scripts.seed_portal_branch.main
"""

from __future__ import annotations

import frappe
from frappe.utils import today

from myschools.scripts.seed_e2e import _ensure_user

EMAIL = "mys-portal-smoke-director@test.local"
PASSWORD = "mys-portal-smoke-director"


def main():
	_ensure_user(
		EMAIL,
		{
			"first_name": "Portal Director",
			"roles": ["Branch Director"],
			"password": PASSWORD,
		},
	)
	branch = frappe.db.get_value("MYS Branch", {}, "name")
	if not branch:
		frappe.throw("No MYS Branch on site — run seed_demo first.")
	emp = _ensure_employee(branch)
	frappe.db.commit()
	return {"branch": branch, "employee": emp, "user": EMAIL}


def _ensure_employee(branch: str) -> str:
	existing = frappe.db.get_value("Employee", {"user_id": EMAIL}, "name")
	if existing:
		frappe.db.set_value("Employee", existing, {"mys_branch": branch, "status": "Active"})
		return existing
	company = frappe.db.get_value("MYS Branch", branch, "company") or frappe.db.get_value(
		"Company", {}, "name"
	)
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": "Portal",
			"last_name": "Director",
			"gender": "Male",
			"date_of_birth": "1985-01-01",
			"date_of_joining": today(),
			"status": "Active",
			"company": company,
			"user_id": EMAIL,
			"mys_branch": branch,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name
