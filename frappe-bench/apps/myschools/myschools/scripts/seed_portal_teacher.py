"""Idempotent Teacher portal smoke user + instructor / class / schedule data.

Run via:
    bench --site SITE execute myschools.scripts.seed_portal_teacher.main

Self-contained for fresh-install / CI: chains ``seed_demo`` when needed, creates
minimal students + education prereqs without calling ``seed_education.run()`` (that
script needs company receivable accounts that may not exist before demo seed).
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, nowdate, today

from myschools.scripts import seed_education
from myschools.scripts.seed_e2e import _ensure_franchise_tree, _ensure_user
from myschools.setup.install import create_franchise_roles, grant_franchise_role_permissions

EMAIL = "e2e_teacher@mys.local"
PASSWORD = "mys-e2e-teacher"
COURSE_NAME = "E2E Portal Math"
ROOM_NAME = "E2E Room 101"
TEACHER_TERM_LABEL = "E2E Teacher Jun"
TEACHER_ACADEMIC_TERM = f"{seed_education.ACADEMIC_YEAR} ({TEACHER_TERM_LABEL})"
TEACHER_TERM_START = "2026-06-01"
TEACHER_TERM_END = "2026-06-30"
PROGRAM_KIDS = seed_education.PROGRAMS["Kids"]


def _group_name_for_branch(branch: str) -> str:
	return f"E2E Teacher Class {branch}"


def main():
	create_franchise_roles()
	grant_franchise_role_permissions()
	_ensure_user(
		EMAIL,
		{
			"first_name": "E2E",
			"roles": ["Teacher"],
			"password": PASSWORD,
		},
	)
	branch, campus = _resolve_branch_and_campus()
	_ensure_education_prereqs()
	_ensure_min_students(branch, campus)
	company = frappe.db.get_value("MYS Branch", branch, "company")
	_ensure_designation("Teacher")
	employee = _ensure_employee(branch, campus, company)
	instructor = _ensure_instructor(employee)
	group = _ensure_student_group(branch, instructor)
	_ensure_group_students(group, branch, campus)
	schedule = _ensure_schedule(group, instructor)
	frappe.db.commit()
	return {
		"user": EMAIL,
		"employee": employee,
		"instructor": instructor,
		"student_group": group,
		"schedule": schedule,
		"branch": branch,
	}


def _resolve_branch_and_campus() -> tuple[str, str | None]:
	"""Franchise tree + campus (CI-safe — does not assume ``{branch}-Kids`` exists)."""
	branch = _ensure_franchise_tree()
	if not branch:
		frappe.throw("No MYS Branch — seed_demo could not run.")
	campus = frappe.db.get_value("MYS Campus", {"branch": branch}, "name", order_by="creation asc")
	return branch, campus


def _ensure_education_prereqs() -> None:
	if not frappe.db.exists("Academic Year", seed_education.ACADEMIC_YEAR):
		frappe.get_doc(
			{
				"doctype": "Academic Year",
				"academic_year_name": seed_education.ACADEMIC_YEAR,
				"year_start_date": seed_education.YEAR_START,
				"year_end_date": seed_education.YEAR_END,
			}
		).insert(ignore_permissions=True)
	_ensure_teacher_academic_term()
	if not frappe.db.exists("Program", PROGRAM_KIDS):
		frappe.get_doc(
			{
				"doctype": "Program",
				"program_name": PROGRAM_KIDS,
				"program_code": PROGRAM_KIDS.replace(" ", "-").upper(),
			}
		).insert(ignore_permissions=True)


def _ensure_designation(name: str) -> None:
	if not frappe.db.exists("Designation", name):
		frappe.get_doc({"doctype": "Designation", "designation_name": name}).insert(
			ignore_permissions=True
		)


def _ensure_min_students(branch: str, campus: str | None) -> None:
	if frappe.db.count("Student", {"mys_branch": branch}):
		return
	cluster = frappe.db.get_value("MYS Branch", branch, "cluster")
	for i in range(1, 4):
		frappe.get_doc(
			{
				"doctype": "Student",
				"first_name": "E2E",
				"last_name": f"TeacherPupil{i}",
				"student_email_id": f"e2e-teacher-pupil-{branch.lower()}-{i}@example.test",
				"mys_branch": branch,
				"mys_cluster": cluster,
				"mys_campus": campus,
			}
		).insert(ignore_permissions=True)


def _ensure_employee(branch: str, campus: str | None, company: str) -> str:
	existing = frappe.db.get_value("Employee", {"user_id": EMAIL}, "name")
	if existing:
		patch = {"mys_branch": branch, "status": "Active", "company": company}
		if campus:
			patch["mys_campus"] = campus
		frappe.db.set_value("Employee", existing, patch)
		return existing
	fields = {
		"doctype": "Employee",
		"first_name": "E2E",
		"last_name": "Teacher",
		"gender": "Male",
		"date_of_birth": "1992-01-01",
		"date_of_joining": today(),
		"status": "Active",
		"company": company,
		"designation": "Teacher",
		"user_id": EMAIL,
		"mys_branch": branch,
	}
	if campus:
		fields["mys_campus"] = campus
	doc = frappe.get_doc(fields)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_instructor(employee: str) -> str:
	existing = frappe.db.get_value("Instructor", {"employee": employee}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Instructor",
			"instructor_name": "E2E Portal Teacher",
			"employee": employee,
			"status": "Active",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_teacher_academic_term() -> str:
	if not frappe.db.exists("Academic Term", TEACHER_ACADEMIC_TERM):
		frappe.get_doc(
			{
				"doctype": "Academic Term",
				"academic_year": seed_education.ACADEMIC_YEAR,
				"term_name": TEACHER_TERM_LABEL,
				"term_start_date": TEACHER_TERM_START,
				"term_end_date": TEACHER_TERM_END,
			}
		).insert(ignore_permissions=True)
	return TEACHER_ACADEMIC_TERM


def _ensure_student_group(branch: str, instructor: str) -> str:
	group_name = _group_name_for_branch(branch)
	year = seed_education.ACADEMIC_YEAR
	term = _ensure_teacher_academic_term()
	if not frappe.db.exists("Student Group", group_name):
		frappe.get_doc(
			{
				"doctype": "Student Group",
				"student_group_name": group_name,
				"group_based_on": "Batch",
				"program": PROGRAM_KIDS,
				"academic_year": year,
				"academic_term": term,
				"max_strength": 50,
			}
		).insert(ignore_permissions=True)
	sg = frappe.get_doc("Student Group", group_name)
	if sg.academic_term != term:
		sg.academic_term = term
		sg.save(ignore_permissions=True)
	linked = {row.instructor for row in sg.get("instructors") or []}
	if instructor not in linked:
		sg.append("instructors", {"instructor": instructor})
		sg.save(ignore_permissions=True)
	return group_name


def _ensure_group_students(group: str, branch: str, campus: str | None) -> list[str]:
	filters: dict = {"mys_branch": branch}
	if campus:
		filters["mys_campus"] = campus
	students = frappe.get_all("Student", filters, pluck="name", limit=3)
	if not students:
		frappe.throw("No students on branch after minimal seed.")
	sg = frappe.get_doc("Student Group", group)
	existing = {row.student for row in sg.get("students") or []}
	added = False
	for student in students:
		if student not in existing:
			sg.append("students", {"student": student, "active": 1})
			added = True
	if added:
		sg.save(ignore_permissions=True)
	return students


def _ensure_course() -> str:
	existing = frappe.db.get_value("Course", {"course_name": COURSE_NAME}, "name")
	if existing:
		return existing
	doc = frappe.get_doc({"doctype": "Course", "course_name": COURSE_NAME})
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_room() -> str:
	existing = frappe.db.get_value("Room", {"room_name": ROOM_NAME}, "name")
	if existing:
		return existing
	doc = frappe.get_doc({"doctype": "Room", "room_name": ROOM_NAME})
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_schedule(group: str, instructor: str) -> str | None:
	if not frappe.db.exists("DocType", "Course Schedule"):
		return None
	course = _ensure_course()
	room = _ensure_room()
	schedule_date = add_days(nowdate(), 1)
	existing = frappe.db.get_value(
		"Course Schedule",
		{
			"student_group": group,
			"instructor": instructor,
			"schedule_date": schedule_date,
		},
		"name",
	)
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Course Schedule",
			"student_group": group,
			"instructor": instructor,
			"course": course,
			"program": PROGRAM_KIDS,
			"schedule_date": schedule_date,
			"from_time": "09:00:00",
			"to_time": "10:00:00",
			"room": room,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name
