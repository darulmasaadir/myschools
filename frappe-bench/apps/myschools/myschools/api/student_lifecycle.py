"""Phase 8b — student lifecycle: transfer, leaving, enrollment guards.

Canonical Education objects (`Student`, `Program Enrollment`) stay upstream;
MYS adds auditable workflow docs and franchise-aware side effects.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, nowdate


def validate_program_enrollment(doc, method=None):
	"""Block enrollment for inactive / un-scoped students (8b)."""
	if not doc.student:
		return
	if not frappe.db.get_value("Student", doc.student, "enabled"):
		frappe.throw(
			_("Student {0} is not active. Use MYS Student Leaving before re-enrolling.").format(
				frappe.bold(doc.student)
			)
		)
	if not frappe.db.get_value("Student", doc.student, "mys_branch"):
		frappe.throw(
			_("Student {0} has no MYS Branch. Set franchise links on the Student record first.").format(
				frappe.bold(doc.student)
			)
		)


def apply_student_transfer(transfer: frappe.Document) -> None:
	"""Move a student to a new branch/campus and sync guardians + groups."""
	to_branch = frappe.get_cached_doc("MYS Branch", transfer.to_branch)
	if transfer.to_campus:
		campus = frappe.get_cached_doc("MYS Campus", transfer.to_campus)
		if campus.branch != transfer.to_branch:
			frappe.throw(_("Campus {0} does not belong to branch {1}").format(transfer.to_campus, transfer.to_branch))

	frappe.db.set_value(
		"Student",
		transfer.student,
		{
			"mys_branch": transfer.to_branch,
			"mys_cluster": to_branch.cluster,
			"mys_campus": transfer.to_campus or "",
		},
		update_modified=True,
	)

	_deactivate_student_groups(transfer.student)
	_sync_guardian_branches(transfer.student, transfer.to_branch)


def apply_student_leaving(leaving: frappe.Document) -> None:
	"""Mark student inactive, stamp exit fields, cancel open enrollments."""
	frappe.db.set_value(
		"Student",
		leaving.student,
		{
			"enabled": 0,
			"date_of_leaving": leaving.leaving_date,
			"leaving_certificate_number": leaving.certificate_number,
			"reason_for_leaving": leaving.reason_for_leaving,
		},
		update_modified=True,
	)

	_cancel_submitted_enrollments(leaving.student)
	_deactivate_student_groups(leaving.student)


def generate_leaving_certificate_number(branch: str) -> str:
	"""Human-readable certificate id: {branch_code}-LC-{YYYY}-{seq}."""
	branch_code = frappe.db.get_value("MYS Branch", branch, "branch_code") or branch
	year = getdate(nowdate()).year
	prefix = f"{branch_code}-LC-{year}-"
	last = frappe.db.sql(
		"""
		SELECT certificate_number FROM `tabMYS Student Leaving`
		WHERE certificate_number LIKE %s
		ORDER BY certificate_number DESC LIMIT 1
		""",
		prefix + "%",
	)
	seq = 1
	if last and last[0][0]:
		try:
			seq = int(str(last[0][0]).rsplit("-", 1)[-1]) + 1
		except ValueError:
			seq = frappe.db.count("MYS Student Leaving", {"branch": branch}) + 1
	return f"{prefix}{seq:04d}"


def _deactivate_student_groups(student: str) -> None:
	for row in frappe.get_all("Student Group Student", filters={"student": student}, pluck="name"):
		frappe.db.set_value("Student Group Student", row, "active", 0)


def _cancel_submitted_enrollments(student: str) -> None:
	names = frappe.get_all(
		"Program Enrollment",
		filters={"student": student, "docstatus": 1},
		pluck="name",
	)
	if not names:
		return
	previous_user = frappe.session.user
	try:
		frappe.set_user("Administrator")
		for name in names:
			frappe.get_doc("Program Enrollment", name).cancel()
	finally:
		frappe.set_user(previous_user)


def _sync_guardian_branches(student: str, branch: str) -> None:
	for row in frappe.get_all("Student Guardian", filters={"parent": student}, pluck="guardian"):
		if frappe.db.exists("Guardian", row):
			frappe.db.set_value("Guardian", row, "mys_branch", branch)


def student_transfer_query(user):
	from myschools.api.permissions import _user_scope

	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Student Transfer`.from_branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"(`tabMYS Student Transfer`.from_branch IN ({in_list}) OR `tabMYS Student Transfer`.to_branch IN ({in_list}))"


def student_leaving_query(user):
	from myschools.api.permissions import _user_scope

	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Student Leaving`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Student Leaving`.branch IN ({in_list})"
