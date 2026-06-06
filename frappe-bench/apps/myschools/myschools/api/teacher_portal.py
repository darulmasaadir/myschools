"""Teacher portal data access — scoped to the logged-in instructor's classes.

Teachers are linked via Education ``Instructor`` → ``Employee.user_id``. Every
query resolves that instructor (and their ``mys_branch`` / ``mys_campus``) and
returns only student groups and schedules assigned to them, with roster rows
filtered to students at the teacher's branch.
"""

from __future__ import annotations

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
		{"label": "Schedule", "route": "/teacher/schedule"},
	]
	return employee, instructor
