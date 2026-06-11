"""Student portal data access — own-record scoping only.

Students are Website Users without Employee records. Every query resolves the
logged-in user's linked ``Student`` row via ``student_email_id`` (and ``user``
when Education exposes that field).
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, nowdate

from myschools.api.notifications import log_communication


def require_student_role() -> None:
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/student"
		raise frappe.Redirect
	if "Student" not in frappe.get_roles():
		frappe.throw("You do not have access to the Student portal.", frappe.PermissionError)


def get_student_for_user(user: str | None = None) -> frappe.Document | None:
	user = user or frappe.session.user
	if user == "Guest":
		return None
	if frappe.get_meta("Student").has_field("user"):
		name = frappe.db.get_value("Student", {"user": user}, "name")
		if name:
			return frappe.get_doc("Student", name)
	email = frappe.db.get_value("User", user, "email")
	if not email:
		return None
	name = frappe.db.get_value("Student", {"student_email_id": email}, "name")
	return frappe.get_doc("Student", name) if name else None


def get_student_detail(student: frappe.Document) -> dict:
	campus_label = student.get("mys_campus")
	if student.mys_campus:
		campus_label = (
			frappe.db.get_value("MYS Campus", student.mys_campus, "campus_type") or student.mys_campus
		)
	return {
		"name": student.name,
		"student_name": student.student_name,
		"first_name": student.first_name,
		"last_name": student.last_name,
		"mys_student_id": student.get("mys_student_id"),
		"mys_branch": student.get("mys_branch"),
		"mys_campus": student.get("mys_campus"),
		"campus_label": campus_label,
		"student_email_id": student.get("student_email_id"),
		"student_mobile_number": student.get("student_mobile_number"),
		"date_of_birth": student.get("date_of_birth"),
		"gender": student.get("gender"),
	}


def get_fees_for_student(student: frappe.Document) -> list[dict]:
	if not frappe.db.exists("DocType", "Fees"):
		return []
	fees = frappe.get_all(
		"Fees",
		filters={"student": student.name, "docstatus": 1},
		fields=[
			"name",
			"posting_date",
			"due_date",
			"grand_total",
			"outstanding_amount",
		],
		order_by="posting_date desc",
		ignore_permissions=True,
	)
	for fee in fees:
		paid = (fee.grand_total or 0) - (fee.outstanding_amount or 0)
		fee["paid_amount"] = paid
		fee["receipt_url"] = (
			f"/api/method/myschools.api.student_portal.download_fee_receipt?fee_name={fee.name}"
		)
	return fees


def get_attendance_for_student(student: frappe.Document, days: int = 90) -> list[dict]:
	if not frappe.db.exists("DocType", "Student Attendance"):
		return []
	from_date = add_days(nowdate(), -days)
	return frappe.get_all(
		"Student Attendance",
		filters={"student": student.name, "date": [">=", from_date]},
		fields=["date", "status"],
		order_by="date desc",
		limit=500,
		ignore_permissions=True,
	)


def get_attendance_summary(attendance_rows: list[dict]) -> dict:
	summary = {"Present": 0, "Absent": 0, "Leave": 0, "Other": 0}
	for row in attendance_rows:
		status = (row.get("status") or "").strip()
		if status in summary:
			summary[status] += 1
		elif status:
			summary["Other"] += 1
	return summary


def populate_student_context(context) -> frappe.Document:
	"""Shared context for all /student/* pages."""
	require_student_role()
	student = get_student_for_user()
	if not student:
		frappe.throw(
			"No Student profile is linked to your login. Please contact your branch office.",
			frappe.PermissionError,
		)
	context.no_cache = 1
	context.show_sidebar = 0
	context.student = student
	context.student_detail = get_student_detail(student)
	context.nav_items = [
		{"label": "My Profile", "route": "/student"},
		{"label": "Fees", "route": "/student/fees"},
		{"label": "Attendance", "route": "/student/attendance"},
		{"label": "Timetable", "route": "/student/timetable"},
	]
	return student


@frappe.whitelist()
def download_fee_receipt(fee_name: str):
	require_student_role()
	student = get_student_for_user()
	if not student:
		frappe.throw("Student profile not found.", frappe.PermissionError)
	fee = frappe.db.get_value("Fees", fee_name, ["student", "docstatus"], as_dict=True)
	if not fee or fee.docstatus != 1 or fee.student != student.name:
		frappe.throw("Fee record not found.", frappe.DoesNotExistError)
	from frappe.utils.print_format import download_pdf

	return download_pdf("Fees", fee_name, format="MYS Fee Receipt")


@frappe.whitelist()
def submit_student_feedback(subject: str, message: str) -> dict:
	require_student_role()
	student = get_student_for_user()
	if not student:
		frappe.throw("Student profile not found.", frappe.PermissionError)
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
		branch=student.get("mys_branch"),
		recipient_user=frappe.session.user,
		sender=frappe.session.user,
	)
	return {"ok": True, "name": name}
