"""Idempotent Guardian portal smoke user + linked student for local HTTP checks.

Run via:
    bench --site SITE execute myschools.scripts.seed_portal_guardian.main
"""

from __future__ import annotations

import frappe

from myschools.scripts.seed_e2e import _ensure_user

EMAIL = "mys-portal-smoke-guardian@test.local"
PASSWORD = "mys-portal-smoke"
STUDENT_EMAIL = "mys-portal-smoke-student@test.local"


def main():
	_ensure_user(
		EMAIL,
		{
			"first_name": "Portal",
			"roles": ["Guardian"],
			"password": PASSWORD,
		},
	)
	guardian_name = _ensure_guardian()
	student_name = _ensure_student()
	_link_student_guardian(student_name, guardian_name)
	frappe.db.set_value("Guardian", guardian_name, "user", EMAIL)
	frappe.db.commit()
	return {"guardian": guardian_name, "student": student_name, "user": EMAIL}


def _ensure_guardian() -> str:
	if frappe.db.exists("Guardian", {"email_address": EMAIL}):
		return frappe.db.get_value("Guardian", {"email_address": EMAIL}, "name")
	doc = frappe.get_doc(
		{
			"doctype": "Guardian",
			"guardian_name": "Portal Smoke Guardian",
			"email_address": EMAIL,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_student() -> str:
	existing = frappe.db.get_value("Student", {"student_email_id": STUDENT_EMAIL}, "name")
	if existing:
		return existing
	branch = frappe.db.get_value("MYS Branch", {}, "name")
	if not branch:
		frappe.throw("No MYS Branch on site — run seed_demo first.")
	student = frappe.get_doc(
		{
			"doctype": "Student",
			"first_name": "Portal",
			"last_name": "Smoke Child",
			"student_email_id": STUDENT_EMAIL,
			"mys_branch": branch,
		}
	)
	student.insert(ignore_permissions=True)
	return student.name


def _link_student_guardian(student_name: str, guardian_name: str) -> None:
	student = frappe.get_doc("Student", student_name)
	linked = {row.guardian for row in student.get("guardians") or []}
	if guardian_name not in linked:
		student.append("guardians", {"guardian": guardian_name, "relation": "Father"})
		student.save(ignore_permissions=True)
