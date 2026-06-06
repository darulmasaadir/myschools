"""Teacher portal data access — scoped to the logged-in instructor's classes.

Teachers are linked via Education ``Instructor`` → ``Employee.user_id``. Every
query resolves that instructor (and their ``mys_branch`` / ``mys_campus``) and
returns only student groups and schedules assigned to them, with roster rows
filtered to students at the teacher's branch.
"""

from __future__ import annotations

import json

import frappe
from frappe.utils import add_days, getdate, nowdate

TEACHER_ROLES = frozenset({"Teacher"})


def require_teacher_role() -> None:
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/teacher"
		raise frappe.Redirect
	if not TEACHER_ROLES & set(frappe.get_roles()):
		frappe.throw("You do not have access to the Teacher portal.", frappe.PermissionError)


def get_employee_for_user(user: str | None = None) -> frappe.Document:
	"""Return the active Employee row for this login."""
	user = user or frappe.session.user
	if user == "Guest":
		frappe.throw("Sign in required.", frappe.PermissionError)
	name = frappe.db.get_value(
		"Employee",
		{"user_id": user, "status": "Active"},
		"name",
	) or frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not name:
		frappe.throw(
			"No active Employee record is linked to your login. "
			"Please ask your branch office to link your account.",
			frappe.PermissionError,
		)
	return frappe.get_doc("Employee", name)


def get_instructor_for_employee(employee: frappe.Document) -> frappe.Document | None:
	if not frappe.db.exists("DocType", "Instructor"):
		return None
	name = frappe.db.get_value(
		"Instructor",
		{"employee": employee.name, "status": "Active"},
		"name",
	) or frappe.db.get_value("Instructor", {"employee": employee.name}, "name")
	return frappe.get_doc("Instructor", name) if name else None


def get_instructor_for_user(user: str | None = None) -> tuple[frappe.Document, frappe.Document]:
	"""Return (employee, instructor) for the portal session."""
	employee = get_employee_for_user(user)
	instructor = get_instructor_for_employee(employee)
	if not instructor:
		frappe.throw(
			"No Instructor profile is linked to your employee record. "
			"Please ask your branch office to create one.",
			frappe.PermissionError,
		)
	return employee, instructor


def get_teacher_scope(employee: frappe.Document) -> dict:
	return {
		"branch": employee.get("mys_branch"),
		"campus": employee.get("mys_campus"),
		"employee": employee.name,
		"employee_name": employee.employee_name,
	}


def _student_group_ids_for_instructor(instructor_name: str) -> list[str]:
	if not frappe.db.exists("DocType", "Student Group Instructor"):
		return []
	parents = frappe.get_all(
		"Student Group Instructor",
		filters={"instructor": instructor_name, "parenttype": "Student Group"},
		pluck="parent",
	)
	return list(dict.fromkeys(parents))


def get_student_groups_for_teacher(instructor: frappe.Document, employee: frappe.Document) -> list[dict]:
	group_ids = _student_group_ids_for_instructor(instructor.name)
	if not group_ids:
		return []
	branch = employee.get("mys_branch")
	rows = frappe.get_all(
		"Student Group",
		filters={"name": ["in", group_ids]},
		fields=["name", "student_group_name", "program", "academic_year", "academic_term"],
		order_by="student_group_name asc",
		ignore_permissions=True,
	)
	for row in rows:
		student_filters: dict = {"parent": row.name, "parenttype": "Student Group", "active": 1}
		student_ids = frappe.get_all(
			"Student Group Student",
			filters=student_filters,
			pluck="student",
			ignore_permissions=True,
		)
		if branch and student_ids:
			student_ids = frappe.get_all(
				"Student",
				filters={"name": ["in", student_ids], "mys_branch": branch},
				pluck="name",
				ignore_permissions=True,
			)
		row["student_count"] = len(student_ids)
	return rows


def assert_teacher_owns_group(group_name: str, instructor: frappe.Document) -> None:
	if group_name not in _student_group_ids_for_instructor(instructor.name):
		frappe.throw("You do not have access to this class.", frappe.PermissionError)


def get_roster_for_group(
	group_name: str, instructor: frappe.Document, employee: frappe.Document
) -> list[dict]:
	assert_teacher_owns_group(group_name, instructor)
	branch = employee.get("mys_branch")
	student_ids = frappe.get_all(
		"Student Group Student",
		filters={"parent": group_name, "parenttype": "Student Group", "active": 1},
		pluck="student",
		ignore_permissions=True,
	)
	if not student_ids:
		return []
	filters: dict = {"name": ["in", student_ids]}
	if branch:
		filters["mys_branch"] = branch
	return frappe.get_all(
		"Student",
		filters=filters,
		fields=[
			"name",
			"student_name",
			"mys_student_id",
			"mys_campus",
			"student_email_id",
		],
		order_by="student_name asc",
		ignore_permissions=True,
	)


def get_schedule_for_teacher(instructor: frappe.Document, days: int = 14, limit: int = 100) -> list[dict]:
	if not frappe.db.exists("DocType", "Course Schedule"):
		return []
	from_date = nowdate()
	to_date = add_days(from_date, days)
	return frappe.get_all(
		"Course Schedule",
		filters={
			"instructor": instructor.name,
			"schedule_date": ["between", [from_date, to_date]],
		},
		fields=[
			"name",
			"schedule_date",
			"from_time",
			"to_time",
			"course",
			"program",
			"student_group",
			"room",
			"title",
		],
		order_by="schedule_date asc, from_time asc",
		limit=limit,
		ignore_permissions=True,
	)


def get_schedule_summary(schedule_rows: list[dict]) -> dict:
	today = getdate(nowdate())
	upcoming = [r for r in schedule_rows if getdate(r.schedule_date) >= today]
	next_row = upcoming[0] if upcoming else None
	return {
		"total": len(schedule_rows),
		"upcoming": len(upcoming),
		"next_date": next_row.schedule_date if next_row else None,
		"next_course": (next_row.course or next_row.title) if next_row else None,
	}


def populate_teacher_context(context) -> tuple[frappe.Document, frappe.Document]:
	"""Shared context for all /teacher/* pages."""
	require_teacher_role()
	employee, instructor = get_instructor_for_user()
	scope = get_teacher_scope(employee)
	context.no_cache = 1
	context.show_sidebar = 0
	context.employee = employee
	context.instructor = instructor
	context.instructor_name = instructor.instructor_name or instructor.name
	context.branch = scope["branch"]
	context.campus = scope["campus"]
	context.nav_items = [
		{"label": "Dashboard", "route": "/teacher"},
		{"label": "My Classes", "route": "/teacher/classes"},
		{"label": "Attendance", "route": "/teacher/attendance"},
		{"label": "Assessments", "route": "/teacher/assessments"},
		{"label": "Schedule", "route": "/teacher/schedule"},
	]
	return employee, instructor


def get_attendance_sheet(
	group_name: str,
	attendance_date: str,
	instructor: frappe.Document,
	employee: frappe.Document,
) -> dict:
	"""Roster rows merged with any existing Student Attendance for the date."""
	assert_teacher_owns_group(group_name, instructor)
	attendance_date = str(getdate(attendance_date))
	roster = get_roster_for_group(group_name, instructor, employee)
	if not roster:
		return {"group": group_name, "date": attendance_date, "rows": []}
	student_ids = [r["name"] for r in roster]
	existing = frappe.get_all(
		"Student Attendance",
		filters={
			"student": ["in", student_ids],
			"student_group": group_name,
			"date": attendance_date,
			"docstatus": ["!=", 2],
		},
		fields=["name", "student", "status", "docstatus"],
		ignore_permissions=True,
	)
	by_student = {row.student: row for row in existing}
	rows = []
	for student in roster:
		att = by_student.get(student["name"])
		rows.append(
			{
				"student": student["name"],
				"student_name": student.get("student_name") or student["name"],
				"mys_student_id": student.get("mys_student_id"),
				"status": att.status if att else "",
				"attendance_name": att.name if att else None,
				"submitted": bool(att and att.docstatus == 1),
			}
		)
	return {"group": group_name, "date": attendance_date, "rows": rows}


def _roster_student_ids(group_name: str, instructor: frappe.Document, employee: frappe.Document) -> set[str]:
	return {row["name"] for row in get_roster_for_group(group_name, instructor, employee)}


def _upsert_student_attendance(student: str, student_group: str, att_date: str, status: str) -> str:
	att_date = str(getdate(att_date))
	status = (status or "").strip()
	if status not in ("Present", "Absent", "Leave"):
		frappe.throw(f"Invalid attendance status for {student}: {status!r}")
	filters = {
		"student": student,
		"student_group": student_group,
		"date": att_date,
		"docstatus": ("!=", 2),
	}
	existing_name = frappe.db.exists("Student Attendance", filters)
	if existing_name:
		doc = frappe.get_doc("Student Attendance", existing_name)
		if doc.docstatus == 1:
			if doc.status == status:
				return doc.name
			doc.cancel()
		else:
			doc.status = status
			doc.save(ignore_permissions=True)
			doc.submit()
			return doc.name
	doc = frappe.get_doc(
		{
			"doctype": "Student Attendance",
			"naming_series": "EDU-ATT-.YYYY.-",
			"student": student,
			"student_group": student_group,
			"date": att_date,
			"status": status,
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


@frappe.whitelist()
def save_class_attendance(student_group: str, date: str, rows: str) -> dict:
	"""Mark attendance for a class the teacher owns. *rows* is JSON [{student, status}, …]."""
	require_teacher_role()
	employee, instructor = get_instructor_for_user()
	assert_teacher_owns_group(student_group, instructor)
	allowed = _roster_student_ids(student_group, instructor, employee)
	parsed = json.loads(rows) if isinstance(rows, str) else rows
	if not isinstance(parsed, list):
		frappe.throw("rows must be a JSON list")
	saved = []
	for row in parsed:
		student = row.get("student")
		if student not in allowed:
			frappe.throw(f"Student {student} is not in your class roster.", frappe.PermissionError)
		status = row.get("status")
		if not status:
			continue
		name = _upsert_student_attendance(student, student_group, date, status)
		saved.append({"student": student, "name": name, "status": status})
	frappe.db.commit()
	return {"ok": True, "saved": saved, "count": len(saved)}


def assert_teacher_owns_plan(plan_name: str, instructor: frappe.Document) -> frappe.Document:
	if not frappe.db.exists("Assessment Plan", plan_name):
		frappe.throw("Assessment plan not found.", frappe.DoesNotExistError)
	plan = frappe.get_doc("Assessment Plan", plan_name)
	if plan.docstatus != 1:
		frappe.throw("Assessment plan is not submitted.", frappe.PermissionError)
	assert_teacher_owns_group(plan.student_group, instructor)
	return plan


def get_assessment_plans_for_teacher(
	instructor: frappe.Document, employee: frappe.Document
) -> list[dict]:
	if not frappe.db.exists("DocType", "Assessment Plan"):
		return []
	group_ids = _student_group_ids_for_instructor(instructor.name)
	if not group_ids:
		return []
	rows = frappe.get_all(
		"Assessment Plan",
		filters={"student_group": ["in", group_ids], "docstatus": 1},
		fields=[
			"name",
			"assessment_name",
			"student_group",
			"course",
			"schedule_date",
			"maximum_assessment_score",
		],
		order_by="schedule_date desc, modified desc",
		limit=50,
		ignore_permissions=True,
	)
	for row in rows:
		row["result_count"] = frappe.db.count(
			"Assessment Result",
			{"assessment_plan": row.name, "docstatus": 1},
		)
	return rows


def get_assessment_entry_sheet(
	plan_name: str, instructor: frappe.Document, employee: frappe.Document
) -> dict:
	plan = assert_teacher_owns_plan(plan_name, instructor)
	roster = get_roster_for_group(plan.student_group, instructor, employee)
	criteria = [
		{
			"assessment_criteria": row.assessment_criteria,
			"maximum_score": row.maximum_score,
		}
		for row in plan.assessment_criteria or []
	]
	student_ids = [r["name"] for r in roster]
	existing = {}
	if student_ids:
		for res in frappe.get_all(
			"Assessment Result",
			filters={
				"assessment_plan": plan_name,
				"student": ["in", student_ids],
				"docstatus": ["!=", 2],
			},
			fields=["name", "student", "total_score", "grade", "docstatus"],
			ignore_permissions=True,
		):
			existing[res.student] = res
	rows = []
	for student in roster:
		res = existing.get(student["name"])
		scores: dict[str, float] = {}
		if res and res.name:
			for detail in frappe.get_all(
				"Assessment Result Detail",
				filters={"parent": res.name, "parenttype": "Assessment Result"},
				fields=["assessment_criteria", "score"],
				ignore_permissions=True,
			):
				scores[detail.assessment_criteria] = detail.score
		rows.append(
			{
				"student": student["name"],
				"student_name": student.get("student_name") or student["name"],
				"mys_student_id": student.get("mys_student_id"),
				"result_name": res.name if res else None,
				"total_score": res.total_score if res else None,
				"grade": res.grade if res else None,
				"submitted": bool(res and res.docstatus == 1),
				"scores": scores,
			}
		)
	return {
		"plan": {
			"name": plan.name,
			"assessment_name": plan.assessment_name or plan.name,
			"student_group": plan.student_group,
			"course": plan.course,
			"schedule_date": plan.schedule_date,
			"maximum_assessment_score": plan.maximum_assessment_score,
		},
		"criteria": criteria,
		"rows": rows,
	}


def _upsert_assessment_result(plan: frappe.Document, student: str, scores: dict[str, float]) -> str:
	filters = {
		"assessment_plan": plan.name,
		"student": student,
		"docstatus": ("!=", 2),
	}
	existing_name = frappe.db.exists("Assessment Result", filters)
	if existing_name:
		doc = frappe.get_doc("Assessment Result", existing_name)
		if doc.docstatus == 1:
			doc.cancel()
		else:
			doc.details = []
			for crit in plan.assessment_criteria:
				score = float(scores.get(crit.assessment_criteria) or 0)
				doc.append(
					"details",
					{
						"assessment_criteria": crit.assessment_criteria,
						"score": score,
					},
				)
			doc.save(ignore_permissions=True)
			doc.submit()
			return doc.name
	doc = frappe.get_doc(
		{
			"doctype": "Assessment Result",
			"assessment_plan": plan.name,
			"student": student,
			"student_group": plan.student_group,
			"details": [
				{
					"assessment_criteria": crit.assessment_criteria,
					"score": float(scores.get(crit.assessment_criteria) or 0),
				}
				for crit in plan.assessment_criteria or []
			],
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


@frappe.whitelist()
def save_assessment_scores(assessment_plan: str, rows: str) -> dict:
	"""Save submitted Assessment Result rows. *rows*: [{student, scores: {criteria: score}}]."""
	require_teacher_role()
	employee, instructor = get_instructor_for_user()
	plan = assert_teacher_owns_plan(assessment_plan, instructor)
	allowed = _roster_student_ids(plan.student_group, instructor, employee)
	parsed = json.loads(rows) if isinstance(rows, str) else rows
	if not isinstance(parsed, list):
		frappe.throw("rows must be a JSON list")
	saved = []
	for row in parsed:
		student = row.get("student")
		if student not in allowed:
			frappe.throw(f"Student {student} is not in your class roster.", frappe.PermissionError)
		scores = row.get("scores") or {}
		if not scores:
			continue
		name = _upsert_assessment_result(plan, student, scores)
		saved.append({"student": student, "name": name})
	frappe.db.commit()
	return {"ok": True, "saved": saved, "count": len(saved)}


@frappe.whitelist()
def download_report_card(assessment_plan: str, student: str):
	"""PDF report card for a student on a plan the teacher owns."""
	require_teacher_role()
	employee, instructor = get_instructor_for_user()
	plan = assert_teacher_owns_plan(assessment_plan, instructor)
	if student not in _roster_student_ids(plan.student_group, instructor, employee):
		frappe.throw("Student is not in your class roster.", frappe.PermissionError)
	result_name = frappe.db.get_value(
		"Assessment Result",
		{
			"assessment_plan": assessment_plan,
			"student": student,
			"docstatus": 1,
		},
		"name",
	)
	if not result_name:
		frappe.throw("No submitted assessment result for this student.", frappe.DoesNotExistError)
	from frappe.utils.print_format import download_pdf

	return download_pdf("Assessment Result", result_name, format="MYS Report Card")
