"""Idempotent Teacher portal smoke user + instructor / class / schedule data.

Run via:
    bench --site SITE execute myschools.scripts.seed_portal_teacher.main
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, nowdate, today

from myschools.scripts import seed_education
from myschools.scripts.seed_e2e import _ensure_user
from myschools.setup.install import create_franchise_roles, grant_franchise_role_permissions

EMAIL = "e2e_teacher@mys.local"
PASSWORD = "mys-e2e-teacher"
GROUP_NAME = "E2E Teacher Class BR014"
COURSE_NAME = "E2E Portal Math"
ROOM_NAME = "E2E Room 101"
TEACHER_TERM_LABEL = "E2E Teacher Jun"
TEACHER_ACADEMIC_TERM = f"{seed_education.ACADEMIC_YEAR} ({TEACHER_TERM_LABEL})"
TEACHER_TERM_START = "2026-06-01"
TEACHER_TERM_END = "2026-06-30"


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
	branch = frappe.db.get_value("MYS Branch", {}, "name")
	if not branch:
		frappe.throw("No MYS Branch — run seed_demo first.")
	campus = f"{branch}-Kids"
	company = frappe.db.get_value("MYS Branch", branch, "company")
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


def _ensure_employee(branch: str, campus: str, company: str) -> str:
	existing = frappe.db.get_value("Employee", {"user_id": EMAIL}, "name")
	if existing:
		frappe.db.set_value(
			"Employee",
			existing,
			{"mys_branch": branch, "mys_campus": campus, "status": "Active", "company": company},
		)
		return existing
	doc = frappe.get_doc(
		{
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
			"mys_campus": campus,
		}
	)
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
	seed_education.run()
	program = seed_education.PROGRAMS["Kids"]
	year = seed_education.ACADEMIC_YEAR
	term = _ensure_teacher_academic_term()
	if not frappe.db.exists("Student Group", GROUP_NAME):
		frappe.get_doc(
			{
				"doctype": "Student Group",
				"student_group_name": GROUP_NAME,
				"group_based_on": "Batch",
				"program": program,
				"academic_year": year,
				"academic_term": term,
				"max_strength": 50,
			}
		).insert(ignore_permissions=True)
	sg = frappe.get_doc("Student Group", GROUP_NAME)
	if sg.academic_term != term:
		sg.academic_term = term
		sg.save(ignore_permissions=True)
	linked = {row.instructor for row in sg.get("instructors") or []}
	if instructor not in linked:
		sg.append("instructors", {"instructor": instructor})
		sg.save(ignore_permissions=True)
	return GROUP_NAME


def _ensure_group_students(group: str, branch: str, campus: str) -> list[str]:
	students = frappe.get_all(
		"Student",
		{"mys_branch": branch, "mys_campus": campus},
		pluck="name",
		limit=3,
	)
	if not students:
		frappe.throw("No students on branch — run seed_education first.")
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
			"program": seed_education.PROGRAMS["Kids"],
			"schedule_date": schedule_date,
			"from_time": "09:00:00",
			"to_time": "10:00:00",
			"room": room,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name
