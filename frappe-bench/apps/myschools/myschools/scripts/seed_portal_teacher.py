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
GUARDIAN_EMAIL = "e2e_guardian@mys.local"
GUARDIAN_PASSWORD = "mys-e2e-guardian"
COURSE_NAME = "E2E Portal Math"
ROOM_NAME = "E2E Room 101"
TEACHER_TERM_LABEL = "E2E Teacher Jun"
TEACHER_ACADEMIC_TERM = f"{seed_education.ACADEMIC_YEAR} ({TEACHER_TERM_LABEL})"
TEACHER_TERM_START = "2026-06-01"
TEACHER_TERM_END = "2026-06-30"
PROGRAM_KIDS = seed_education.PROGRAMS["Kids"]
GRADING_SCALE = "E2E MY School Grading"
ASSESSMENT_GROUP = "E2E Term Assessment"
ASSESSMENT_CRITERIA = "E2E Written Test"
ASSESSMENT_PLAN_NAME = "E2E Portal Mid Term"


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
	_ensure_company_holiday_list(company)
	_ensure_designation("Teacher")
	employee = _ensure_employee(branch, campus, company)
	instructor = _ensure_instructor(employee)
	group = _ensure_student_group(branch, instructor)
	students = _ensure_group_students(group, branch, campus)
	schedules = _ensure_week_schedule(group, instructor)
	assessment_plan = _ensure_assessment_plan(group, instructor)
	guardian = _ensure_guardian_for_students(students)
	frappe.db.commit()
	return {
		"user": EMAIL,
		"employee": employee,
		"instructor": instructor,
		"student_group": group,
		"schedule": schedules[0] if schedules else None,
		"schedule_count": len(schedules),
		"assessment_plan": assessment_plan,
		"branch": branch,
		"guardian": guardian,
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


def _ensure_company_holiday_list(company: str | None) -> None:
	"""Education Student Attendance.validate_is_holiday requires a company holiday list."""
	if not frappe.db.exists("DocType", "Holiday List"):
		return
	companies: list[str] = []
	if company:
		companies.append(company)
	try:
		from erpnext import get_default_company

		default = get_default_company()
		if default and default not in companies:
			companies.append(default)
	except Exception:
		pass
	if not companies:
		companies = frappe.get_all("Company", pluck="name", limit=1)
	list_name = "MYS Default Holidays"
	if not frappe.db.exists("Holiday List", list_name):
		frappe.get_doc(
			{
				"doctype": "Holiday List",
				"holiday_list_name": list_name,
				"from_date": "2020-01-01",
				"to_date": "2030-12-31",
			}
		).insert(ignore_permissions=True)
	for comp in companies:
		if comp and not frappe.db.get_value("Company", comp, "default_holiday_list"):
			frappe.db.set_value("Company", comp, "default_holiday_list", list_name)


def _ensure_designation(name: str) -> None:
	if not frappe.db.exists("Designation", name):
		frappe.get_doc({"doctype": "Designation", "designation_name": name}).insert(ignore_permissions=True)


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


def _ensure_grading_scale() -> str:
	if not frappe.db.exists("DocType", "Grading Scale"):
		return ""
	if frappe.db.exists("Grading Scale", GRADING_SCALE):
		return GRADING_SCALE
	doc = frappe.get_doc(
		{
			"doctype": "Grading Scale",
			"grading_scale_name": GRADING_SCALE,
			"intervals": [
				{"grade_code": "A", "threshold": 90, "grade_description": "Excellent"},
				{"grade_code": "B", "threshold": 80, "grade_description": "Good"},
				{"grade_code": "C", "threshold": 70, "grade_description": "Average"},
				{"grade_code": "F", "threshold": 0, "grade_description": "Fail"},
			],
		}
	)
	doc.insert(ignore_permissions=True)
	return GRADING_SCALE


def _ensure_assessment_group() -> str:
	if not frappe.db.exists("DocType", "Assessment Group"):
		return ""
	if frappe.db.exists("Assessment Group", ASSESSMENT_GROUP):
		return ASSESSMENT_GROUP
	root = frappe.db.get_value("Assessment Group", {"is_group": 1}, "name", order_by="lft asc")
	if not root:
		root_doc = frappe.get_doc(
			{
				"doctype": "Assessment Group",
				"assessment_group_name": "All Assessment Groups",
				"is_group": 1,
				"parent_assessment_group": "All Assessment Groups",
			}
		)
		root_doc.insert(ignore_permissions=True)
		root = root_doc.name
	doc = frappe.get_doc(
		{
			"doctype": "Assessment Group",
			"assessment_group_name": ASSESSMENT_GROUP,
			"parent_assessment_group": root,
			"is_group": 0,
		}
	)
	doc.insert(ignore_permissions=True)
	return ASSESSMENT_GROUP


def _ensure_assessment_criteria() -> str:
	if not frappe.db.exists("DocType", "Assessment Criteria"):
		return ""
	if frappe.db.exists("Assessment Criteria", ASSESSMENT_CRITERIA):
		return ASSESSMENT_CRITERIA
	doc = frappe.get_doc(
		{
			"doctype": "Assessment Criteria",
			"assessment_criteria": ASSESSMENT_CRITERIA,
		}
	)
	doc.insert(ignore_permissions=True)
	return ASSESSMENT_CRITERIA


def _ensure_course() -> str:
	grading = _ensure_grading_scale()
	existing = frappe.db.get_value("Course", {"course_name": COURSE_NAME}, "name")
	if existing:
		if grading:
			frappe.db.set_value("Course", existing, "default_grading_scale", grading)
		return existing
	fields = {"doctype": "Course", "course_name": COURSE_NAME}
	if grading:
		fields["default_grading_scale"] = grading
	doc = frappe.get_doc(fields)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_assessment_plan(group: str, instructor: str) -> str | None:
	if not frappe.db.exists("DocType", "Assessment Plan"):
		return None
	existing = frappe.db.get_value(
		"Assessment Plan",
		{"assessment_name": ASSESSMENT_PLAN_NAME, "student_group": group},
		"name",
	)
	if existing:
		doc = frappe.get_doc("Assessment Plan", existing)
		if doc.docstatus == 0:
			doc.submit()
		return existing
	course = _ensure_course()
	assessment_group = _ensure_assessment_group()
	criteria = _ensure_assessment_criteria()
	grading = _ensure_grading_scale()
	if not all([course, assessment_group, criteria, grading]):
		return None
	term = _ensure_teacher_academic_term()
	doc = frappe.get_doc(
		{
			"doctype": "Assessment Plan",
			"assessment_name": ASSESSMENT_PLAN_NAME,
			"student_group": group,
			"assessment_group": assessment_group,
			"grading_scale": grading,
			"course": course,
			"program": PROGRAM_KIDS,
			"academic_year": seed_education.ACADEMIC_YEAR,
			"academic_term": term,
			"schedule_date": today(),
			"from_time": "10:00:00",
			"to_time": "11:00:00",
			"examiner": instructor,
			"maximum_assessment_score": 100,
			"assessment_criteria": [
				{
					"assessment_criteria": criteria,
					"maximum_score": 100,
				}
			],
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def _ensure_room() -> str:
	existing = frappe.db.get_value("Room", {"room_name": ROOM_NAME}, "name")
	if existing:
		return existing
	doc = frappe.get_doc({"doctype": "Room", "room_name": ROOM_NAME})
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_week_schedule(group: str, instructor: str) -> list[str]:
	"""Mon-Fri sessions for the next school week (portal timetable smoke)."""
	if not frappe.db.exists("DocType", "Course Schedule"):
		return []
	course = _ensure_course()
	room = _ensure_room()
	created: list[str] = []
	for offset in range(1, 6):
		schedule_date = add_days(nowdate(), offset)
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
			created.append(existing)
			continue
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
		created.append(doc.name)
	return created


def _ensure_guardian_for_students(student_ids: list[str]) -> dict | None:
	if not student_ids or not frappe.db.exists("DocType", "Guardian"):
		return None
	_ensure_user(
		GUARDIAN_EMAIL,
		{
			"first_name": "E2E",
			"roles": ["Guardian"],
			"password": GUARDIAN_PASSWORD,
		},
	)
	guardian_name = frappe.db.get_value("Guardian", {"email_address": GUARDIAN_EMAIL}, "name")
	if not guardian_name:
		guardian_name = (
			frappe.get_doc(
				{
					"doctype": "Guardian",
					"guardian_name": "E2E Guardian Parent",
					"email_address": GUARDIAN_EMAIL,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	frappe.db.set_value("Guardian", guardian_name, "user", GUARDIAN_EMAIL)
	# Link up to two children so the /guardian/timetable ?student= selector renders.
	linked_students = student_ids[:2]
	for student_name in linked_students:
		student = frappe.get_doc("Student", student_name)
		linked = {row.guardian for row in student.get("guardians") or []}
		if guardian_name not in linked:
			student.append("guardians", {"guardian": guardian_name, "relation": "Father"})
			student.save(ignore_permissions=True)
	return {
		"user": GUARDIAN_EMAIL,
		"guardian": guardian_name,
		"student": linked_students[0],
		"students": linked_students,
	}
