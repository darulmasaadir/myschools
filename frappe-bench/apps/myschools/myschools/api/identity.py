"""MY School unique ID generation for Student and Employee records.

Student ID format : MYS-{cluster_code}-{branch_code}-STU{######}
Staff   ID format : MYS-{branch_code}-{role_code}{####}

The role code maps to the Employee's `mys_role_tier` + designation, but
for now we use a coarser mapping based on `designation`.
"""

import frappe
from frappe import _

ROLE_CODES = {
	"Teacher": "TCH",
	"Instructor": "TCH",
	"Principal": "PRN",
	"Branch Principal": "PRN",
	"Admin": "ADM",
	"Branch Admin": "ADM",
	"Accountant": "ACC",
	"Branch Accountant": "ACC",
	"Director": "DIR",
	"Branch Director": "DIR",
	"Campus Incharge": "INC",
	"Academic Monitor": "AMN",
	"Audit Officer": "AUD",
	"Cluster Director": "CDR",
}


def set_mys_student_id(doc, method=None):
	if getattr(doc, "mys_student_id", None):
		return
	branch_name = getattr(doc, "mys_branch", None)
	if not branch_name:
		return
	branch = frappe.get_cached_doc("MYS Branch", branch_name)
	cluster_code = branch.cluster
	branch_code = branch.branch_code or branch.name
	count = frappe.db.count("Student", {"mys_branch": branch_name}) + 1
	doc.mys_student_id = f"MYS-{cluster_code}-{branch_code}-STU{count:06d}"
	if not getattr(doc, "mys_cluster", None):
		doc.mys_cluster = cluster_code


def validate_student_franchise_links(doc, method=None):
	if doc.mys_campus and doc.mys_branch:
		campus = frappe.get_cached_doc("MYS Campus", doc.mys_campus)
		if campus.branch != doc.mys_branch:
			frappe.throw(_("Campus {0} does not belong to branch {1}").format(doc.mys_campus, doc.mys_branch))
	if doc.mys_branch and doc.mys_cluster:
		branch = frappe.get_cached_doc("MYS Branch", doc.mys_branch)
		if branch.cluster != doc.mys_cluster:
			frappe.throw(
				_("Branch {0} does not belong to cluster {1}").format(doc.mys_branch, doc.mys_cluster)
			)


def set_mys_staff_id(doc, method=None):
	if getattr(doc, "mys_staff_id", None):
		return
	branch_name = getattr(doc, "mys_branch", None)
	if not branch_name:
		return
	branch = frappe.get_cached_doc("MYS Branch", branch_name)
	branch_code = branch.branch_code or branch.name
	role_code = ROLE_CODES.get(doc.designation or "", "STF")
	count = frappe.db.count("Employee", {"mys_branch": branch_name, "designation": doc.designation}) + 1
	doc.mys_staff_id = f"MYS-{branch_code}-{role_code}{count:04d}"


def _guardian_email(doc) -> str:
	return (doc.get("email_address") or doc.get("email_id") or "").strip()


def sync_guardian_branch(doc, method=None):
	"""When a Guardian links to a Student, copy the student's branch onto
	the Guardian so the parent portal can filter visible data by branch."""
	if doc.mys_branch:
		return
	# Frappe Education's Guardian has a `students` child table referencing Student
	for row in doc.get("students") or []:
		student = frappe.db.get_value("Student", row.student, ["mys_branch"], as_dict=True)
		if student and student.mys_branch:
			doc.mys_branch = student.mys_branch
			break


def link_guardian_user(doc, method=None):
	"""Link Guardian.user to an existing User when emails match.

	Administrators create Website Users for guardians; this hook idempotently
	wires the back-link on save. Does not create users (signup stays admin-driven).
	"""
	if doc.get("user"):
		return
	email = _guardian_email(doc)
	if not email:
		return
	user = frappe.db.get_value("User", {"email": email}, "name")
	if user:
		doc.user = user


def backfill_guardian_user_links():
	"""One-shot linker for Guardians saved before the user field shipped."""
	if not frappe.db.has_column("Guardian", "user"):
		return
	for name in frappe.get_all(
		"Guardian",
		filters=[["user", "in", ("", None)]],
		pluck="name",
	):
		doc = frappe.get_doc("Guardian", name)
		link_guardian_user(doc)
		if doc.get("user"):
			frappe.db.set_value("Guardian", name, "user", doc.user, update_modified=False)
