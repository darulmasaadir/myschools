"""Branch- and guardian-scoped timetable helpers on Education ``Course Schedule``.

Shared by teacher, branch, and guardian portals. Desk list scoping is enforced
separately via ``permissions.course_schedule_query``.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import date

import frappe
from frappe.utils import add_days, getdate, nowdate

SCHEDULE_FIELDS = [
	"name",
	"schedule_date",
	"from_time",
	"to_time",
	"course",
	"program",
	"student_group",
	"instructor",
	"room",
	"title",
]


def schedule_date_window(days: int = 14, from_date: str | date | None = None) -> tuple[str, str]:
	start = getdate(from_date or nowdate())
	end = add_days(start, days)
	return str(start), str(end)


def get_student_group_ids_for_branch(branch: str) -> list[str]:
	if not branch or not frappe.db.exists("DocType", "Student Group Student"):
		return []
	return frappe.db.sql(
		"""
		SELECT DISTINCT sgs.parent
		FROM `tabStudent Group Student` sgs
		INNER JOIN `tabStudent` st ON st.name = sgs.student
		WHERE sgs.parenttype = 'Student Group' AND sgs.active = 1
			AND st.mys_branch = %s
		""",
		branch,
		pluck=True,
	)


def get_student_group_ids_for_students(student_ids: list[str]) -> list[str]:
	if not student_ids or not frappe.db.exists("DocType", "Student Group Student"):
		return []
	return frappe.db.sql(
		"""
		SELECT DISTINCT sgs.parent
		FROM `tabStudent Group Student` sgs
		WHERE sgs.parenttype = 'Student Group' AND sgs.active = 1
			AND sgs.student IN %(students)s
		""",
		{"students": tuple(student_ids)},
		pluck=True,
	)


def fetch_course_schedules(
	*,
	group_ids: list[str] | None = None,
	instructor: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	limit: int = 500,
) -> list[dict]:
	if not frappe.db.exists("DocType", "Course Schedule"):
		return []
	if from_date is None or to_date is None:
		from_date, to_date = schedule_date_window()
	filters: dict = {"schedule_date": ["between", [from_date, to_date]]}
	if instructor:
		filters["instructor"] = instructor
	if group_ids is not None:
		if not group_ids:
			return []
		filters["student_group"] = ["in", group_ids]
	rows = frappe.get_all(
		"Course Schedule",
		filters=filters,
		fields=SCHEDULE_FIELDS,
		order_by="schedule_date asc, from_time asc",
		limit=limit,
		ignore_permissions=True,
	)
	return enrich_schedule_rows(rows)


def enrich_schedule_rows(rows: list[dict]) -> list[dict]:
	if not rows:
		return rows
	instructor_ids = {r.get("instructor") for r in rows if r.get("instructor")}
	instructor_names: dict[str, str] = {}
	if instructor_ids and frappe.db.exists("DocType", "Instructor"):
		instructor_rows = frappe.get_all(
			"Instructor",
			filters={"name": ["in", list(instructor_ids)]},
			fields=["name", "instructor_name"],
			limit=len(instructor_ids),
		)
		instructor_names = {row["name"]: row.get("instructor_name") or row["name"] for row in instructor_rows}
	for row in rows:
		inst = row.get("instructor")
		if inst:
			row["instructor_name"] = instructor_names.get(inst, inst)
	return rows


def group_schedule_by_date(rows: list[dict]) -> list[dict]:
	grouped: OrderedDict[str, list[dict]] = OrderedDict()
	for row in sorted(rows, key=lambda r: (str(r.get("schedule_date") or ""), str(r.get("from_time") or ""))):
		day = str(row.get("schedule_date") or "")
		grouped.setdefault(day, []).append(row)
	return [{"date": day, "rows": grouped[day]} for day in grouped]


def get_schedules_for_instructor(
	instructor_name: str,
	days: int = 14,
	limit: int = 100,
) -> list[dict]:
	from_date, to_date = schedule_date_window(days=days)
	return fetch_course_schedules(
		instructor=instructor_name,
		from_date=from_date,
		to_date=to_date,
		limit=limit,
	)


def get_schedules_for_branch(branch: str, days: int = 14, limit: int = 500) -> list[dict]:
	group_ids = get_student_group_ids_for_branch(branch)
	from_date, to_date = schedule_date_window(days=days)
	return fetch_course_schedules(
		group_ids=group_ids,
		from_date=from_date,
		to_date=to_date,
		limit=limit,
	)


def get_schedules_for_guardian(
	guardian: frappe.Document,
	student_name: str | None = None,
	days: int = 14,
	limit: int = 500,
) -> list[dict]:
	from myschools.api.guardian_portal import get_linked_student_ids

	student_ids = get_linked_student_ids(guardian)
	if student_name:
		if student_name not in student_ids:
			frappe.throw("That student is not linked to your guardian profile.", frappe.PermissionError)
		student_ids = [student_name]
	group_ids = get_student_group_ids_for_students(student_ids)
	from_date, to_date = schedule_date_window(days=days)
	return fetch_course_schedules(
		group_ids=group_ids,
		from_date=from_date,
		to_date=to_date,
		limit=limit,
	)


def get_schedule_portal_summary(rows: list[dict]) -> dict:
	days = group_schedule_by_date(rows)
	return {
		"session_count": len(rows),
		"days_with_classes": len(days),
	}
