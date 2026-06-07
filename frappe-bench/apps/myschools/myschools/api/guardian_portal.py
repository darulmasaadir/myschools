"""Guardian portal data access — explicit student linkage, not desk permission queries.

Guardians are Website Users without Employee records, so ``permission_query_conditions``
return ``none`` for them. Every query here resolves the logged-in user's ``Guardian``
document and only returns rows for students linked via Education's ``Student Guardian`` table.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, nowdate

from myschools.api.notifications import log_communication


def require_guardian_role() -> None:
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/guardian"
		raise frappe.Redirect
	if "Guardian" not in frappe.get_roles():
		frappe.throw("You do not have access to the Guardian portal.", frappe.PermissionError)


def get_guardian_for_user(user: str | None = None) -> frappe.Document | None:
	"""Return the Guardian doc linked to this Website User, if any."""
	user = user or frappe.session.user
	if user == "Guest":
		return None
	name = frappe.db.get_value("Guardian", {"user": user}, "name")
	if name:
		return frappe.get_doc("Guardian", name)
	email = frappe.db.get_value("User", user, "email")
	if not email:
		return None
	name = frappe.db.get_value("Guardian", {"email_address": email}, "name")
	return frappe.get_doc("Guardian", name) if name else None


def get_linked_student_ids(guardian: frappe.Document) -> list[str]:
	"""Students linked on the Student form (``guardians`` child table), not Guardian.students.

	Education's Guardian doc clears ``students`` on validate and repopulates it read-only on load.
	"""
	return frappe.get_all(
		"Student Guardian",
		filters={"guardian": guardian.name, "parenttype": "Student"},
		pluck="parent",
	)


def assert_guardian_owns_student(student_id: str, guardian: frappe.Document) -> None:
	if student_id not in get_linked_student_ids(guardian):
		frappe.throw("You do not have access to this student record.", frappe.PermissionError)


def get_students_for_guardian(guardian: frappe.Document) -> list[dict]:
	student_ids = get_linked_student_ids(guardian)
	if not student_ids:
		return []
	return frappe.get_all(
		"Student",
		filters={"name": ["in", student_ids]},
		fields=[
			"name",
			"student_name",
			"first_name",
			"last_name",
			"mys_student_id",
			"mys_branch",
			"mys_campus",
			"student_email_id",
			"student_mobile_number",
		],
		order_by="student_name asc",
		ignore_permissions=True,
	)


def get_student_detail(student_id: str, guardian: frappe.Document) -> dict:
	assert_guardian_owns_student(student_id, guardian)
	row = frappe.db.get_value(
		"Student",
		student_id,
		[
			"name",
			"student_name",
			"first_name",
			"last_name",
			"mys_student_id",
			"mys_branch",
			"mys_campus",
			"student_email_id",
			"student_mobile_number",
			"date_of_birth",
			"gender",
		],
		as_dict=True,
	)
	if not row:
		frappe.throw("Student not found.", frappe.DoesNotExistError)
	campus_label = None
	if row.mys_campus:
		campus_label = frappe.db.get_value("MYS Campus", row.mys_campus, "campus_name")
	row["campus_label"] = campus_label
	return row


def get_fees_for_guardian(guardian: frappe.Document) -> list[dict]:
	student_ids = get_linked_student_ids(guardian)
	if not student_ids:
		return []
	fees = frappe.get_all(
		"Fees",
		filters={"student": ["in", student_ids], "docstatus": 1},
		fields=[
			"name",
			"student",
			"posting_date",
			"due_date",
			"grand_total",
			"outstanding_amount",
		],
		order_by="posting_date desc",
		ignore_permissions=True,
	)
	student_names = {
		s["name"]: s.get("student_name") or s["name"] for s in get_students_for_guardian(guardian)
	}
	for fee in fees:
		fee["student_name"] = student_names.get(fee.student, fee.student)
		paid = (fee.grand_total or 0) - (fee.outstanding_amount or 0)
		fee["paid_amount"] = paid
		fee["receipt_url"] = (
			f"/api/method/myschools.api.guardian_portal.download_fee_receipt?fee_name={fee.name}"
		)
	return fees


def get_attendance_for_guardian(guardian: frappe.Document, days: int = 90) -> list[dict]:
	student_ids = get_linked_student_ids(guardian)
	if not student_ids:
		return []
	if not frappe.db.exists("DocType", "Student Attendance"):
		return []
	from_date = add_days(nowdate(), -days)
	rows = frappe.get_all(
		"Student Attendance",
		filters={
			"student": ["in", student_ids],
			"date": [">=", from_date],
		},
		fields=["student", "date", "status"],
		order_by="date desc, student asc",
		limit=500,
		ignore_permissions=True,
	)
	student_names = {
		s["name"]: s.get("student_name") or s["name"] for s in get_students_for_guardian(guardian)
	}
	for row in rows:
		row["student_name"] = student_names.get(row.student, row.student)
	return rows


def get_attendance_summary(attendance_rows: list[dict]) -> dict:
	summary = {"Present": 0, "Absent": 0, "Leave": 0, "Other": 0}
	for row in attendance_rows:
		status = (row.get("status") or "").strip()
		if status in summary:
			summary[status] += 1
		elif status:
			summary["Other"] += 1
	return summary


def populate_guardian_context(context) -> frappe.Document:
	"""Shared context for all /guardian/* pages."""
	require_guardian_role()
	guardian = get_guardian_for_user()
	if not guardian:
		frappe.throw(
			"No Guardian profile is linked to your login. Please contact your branch office.",
			frappe.PermissionError,
		)
	context.no_cache = 1
	context.show_sidebar = 0
	context.guardian = guardian
	context.guardian_name = guardian.guardian_name
	context.students = get_students_for_guardian(guardian)
	context.nav_items = [
		{"label": "My Children", "route": "/guardian"},
		{"label": "Fees", "route": "/guardian/fees"},
		{"label": "Attendance", "route": "/guardian/attendance"},
		{"label": "Timetable", "route": "/guardian/timetable"},
		{"label": "Feedback", "route": "/guardian-feedback"},
	]
	return guardian


@frappe.whitelist()
def download_fee_receipt(fee_name: str):
	"""PDF receipt for a fee row owned by the logged-in guardian's child."""
	require_guardian_role()
	guardian = get_guardian_for_user()
	if not guardian:
		frappe.throw("Guardian profile not found.", frappe.PermissionError)
	fee = frappe.db.get_value("Fees", fee_name, ["student", "docstatus"], as_dict=True)
	if not fee or fee.docstatus != 1:
		frappe.throw("Fee record not found.", frappe.DoesNotExistError)
	assert_guardian_owns_student(fee.student, guardian)
	from frappe.utils.print_format import download_pdf

	return download_pdf("Fees", fee_name, format="MYS Fee Receipt")


@frappe.whitelist()
def submit_guardian_feedback(subject: str, message: str) -> dict:
	"""Record guardian feedback into MYS Communication Log (used by portal form)."""
	require_guardian_role()
	guardian = get_guardian_for_user()
	if not guardian:
		frappe.throw("Guardian profile not found.", frappe.PermissionError)
	subject = (subject or "").strip()
	message = (message or "").strip()
	if not subject or not message:
		frappe.throw("Subject and message are required.")
	name = log_communication(
		channel="In-App",
		status="Sent",
		subject=subject,
		body=message,
		scope="Individual",
		branch=guardian.get("mys_branch"),
		recipient_user=frappe.session.user,
		sender=frappe.session.user,
	)
	return {"ok": True, "name": name}
