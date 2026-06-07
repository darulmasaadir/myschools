"""Phase 11 — Academic scheduling (branch/guardian timetable + desk scoping).

Run via:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_scheduling
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate, today

from myschools.api.permissions import course_schedule_query, student_group_query
from myschools.api.scheduling import (
	get_schedules_for_branch,
	get_schedules_for_guardian,
	get_schedules_for_instructor,
	get_student_group_ids_for_branch,
	group_schedule_by_date,
)
from myschools.setup.install import create_franchise_roles, grant_franchise_role_permissions


class TestScheduling(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_franchise_roles()
		grant_franchise_role_permissions()
		cls.branch_a = cls._ensure_branch("Sched A", "SCHA")
		cls.branch_b = cls._ensure_branch("Sched B", "SCHB")
		cls.group_a, cls.instructor_a = cls._ensure_group_and_instructor(cls.branch_a, "Sched Teacher A")
		cls.group_b, cls.instructor_b = cls._ensure_group_and_instructor(cls.branch_b, "Sched Teacher B")
		cls.student_a = cls._ensure_student(cls.branch_a, "Sched Child A")
		cls._link_student_group(cls.group_a, cls.student_a)
		cls.schedule_a = cls._ensure_schedule(cls.group_a, cls.instructor_a, slot=0)
		cls.schedule_b = cls._ensure_schedule(cls.group_b, cls.instructor_b, slot=1)
		cls.guardian = cls._ensure_guardian(cls.student_a)

	@classmethod
	def _ensure_branch(cls, name: str, code: str) -> str:
		existing = frappe.db.get_value("MYS Branch", {"branch_code": code}, "name")
		if existing:
			return existing
		cluster = frappe.get_doc(
			{"doctype": "MYS Cluster", "cluster_name": f"{name} Cluster", "cluster_code": code}
		).insert(ignore_permissions=True)
		return (
			frappe.get_doc(
				{
					"doctype": "MYS Branch",
					"branch_name": name,
					"branch_code": code,
					"cluster": cluster.name,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	@classmethod
	def _ensure_student(cls, branch: str, label: str) -> str:
		email = f"{label.lower().replace(' ', '-')}@sched.test"
		existing = frappe.db.get_value("Student", {"student_email_id": email}, "name")
		if existing:
			return existing
		return (
			frappe.get_doc(
				{
					"doctype": "Student",
					"first_name": label,
					"student_email_id": email,
					"mys_branch": branch,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	@classmethod
	def _ensure_group_and_instructor(cls, branch: str, teacher_name: str) -> tuple[str, str]:
		if not frappe.db.exists("DocType", "Student Group"):
			cls.skipTest("Education not installed")
		group_name = f"Sched Group {branch}"
		program = frappe.db.get_value("Program", {}, "name")
		if not program:
			program = (
				frappe.get_doc(
					{"doctype": "Program", "program_name": "Sched Test Program", "program_code": "STP"}
				)
				.insert(ignore_permissions=True)
				.name
			)
		year = frappe.db.get_value("Academic Year", {}, "name")
		if not year:
			year = (
				frappe.get_doc(
					{
						"doctype": "Academic Year",
						"academic_year_name": "Sched Test Year",
						"year_start_date": "2026-01-01",
						"year_end_date": "2026-12-31",
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		if not frappe.db.exists("Student Group", group_name):
			frappe.get_doc(
				{
					"doctype": "Student Group",
					"student_group_name": group_name,
					"group_based_on": "Batch",
					"program": program,
					"academic_year": year,
					"max_strength": 30,
				}
			).insert(ignore_permissions=True)
		company = frappe.db.get_value("Company", {}, "name")
		employee = frappe.db.get_value("Employee", {"first_name": teacher_name}, "name")
		if not employee:
			employee = (
				frappe.get_doc(
					{
						"doctype": "Employee",
						"first_name": teacher_name,
						"gender": "Male",
						"date_of_birth": "1990-01-01",
						"date_of_joining": today(),
						"company": company,
						"mys_branch": branch,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		instructor = frappe.db.get_value("Instructor", {"employee": employee}, "name")
		if not instructor:
			instructor = (
				frappe.get_doc(
					{
						"doctype": "Instructor",
						"instructor_name": teacher_name,
						"employee": employee,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		return group_name, instructor

	@classmethod
	def _link_student_group(cls, group: str, student: str) -> None:
		sg = frappe.get_doc("Student Group", group)
		existing = {row.student for row in sg.get("students") or []}
		if student not in existing:
			sg.append("students", {"student": student, "active": 1})
			sg.save(ignore_permissions=True)

	@classmethod
	def _ensure_schedule(cls, group: str, instructor: str, *, slot: int = 0) -> str | None:
		if not frappe.db.exists("DocType", "Course Schedule"):
			return None
		schedule_date = add_days(nowdate(), 2)
		existing = frappe.db.get_value(
			"Course Schedule",
			{"student_group": group, "instructor": instructor, "schedule_date": schedule_date},
			"name",
		)
		if existing:
			return existing
		course = frappe.db.get_value("Course", {}, "name")
		if not course:
			course = (
				frappe.get_doc({"doctype": "Course", "course_name": "Sched Test Course"})
				.insert(ignore_permissions=True)
				.name
			)
		room_name = f"Sched Test Room {slot}"
		room = frappe.db.get_value("Room", {"room_name": room_name}, "name")
		if not room and frappe.db.exists("DocType", "Room"):
			room = (
				frappe.get_doc({"doctype": "Room", "room_name": room_name})
				.insert(ignore_permissions=True)
				.name
			)
		start_hour = 10 + slot
		fields = {
			"doctype": "Course Schedule",
			"student_group": group,
			"instructor": instructor,
			"course": course,
			"schedule_date": schedule_date,
			"from_time": f"{start_hour:02d}:00:00",
			"to_time": f"{start_hour:02d}:45:00",
		}
		if room:
			fields["room"] = room
		return frappe.get_doc(fields).insert(ignore_permissions=True).name

	@classmethod
	def _ensure_guardian(cls, student: str):
		email = "sched-guardian@test.local"
		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Sched",
					"last_name": "Guardian",
					"send_welcome_email": 0,
				}
			)
			user.append("roles", {"role": "Guardian"})
			user.insert(ignore_permissions=True)
		guardian_name = frappe.db.get_value("Guardian", {"email_address": email}, "name")
		if not guardian_name:
			guardian_name = (
				frappe.get_doc(
					{
						"doctype": "Guardian",
						"guardian_name": "Sched Guardian",
						"email_address": email,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		frappe.db.set_value("Guardian", guardian_name, "user", email)
		student_doc = frappe.get_doc("Student", student)
		linked = {row.guardian for row in student_doc.get("guardians") or []}
		if guardian_name not in linked:
			student_doc.append("guardians", {"guardian": guardian_name, "relation": "Father"})
			student_doc.save(ignore_permissions=True)
		return frappe.get_doc("Guardian", guardian_name)

	def test_branch_group_resolution(self):
		group_ids = get_student_group_ids_for_branch(self.branch_a)
		self.assertIn(self.group_a, group_ids)
		self.assertNotIn(self.group_b, group_ids)

	def test_branch_timetable_rows(self):
		rows = get_schedules_for_branch(self.branch_a, days=14)
		names = {row["name"] for row in rows}
		self.assertIn(self.schedule_a, names)

	def test_guardian_timetable_rows(self):
		rows = get_schedules_for_guardian(self.guardian, days=14)
		names = {row["name"] for row in rows}
		self.assertIn(self.schedule_a, names)

	def test_instructor_timetable_rows(self):
		rows = get_schedules_for_instructor(self.instructor_a, days=14)
		names = {row["name"] for row in rows}
		self.assertIn(self.schedule_a, names)

	def test_group_schedule_by_date(self):
		rows = get_schedules_for_branch(self.branch_a, days=14)
		grouped = group_schedule_by_date(rows)
		self.assertTrue(grouped)
		self.assertEqual(len(grouped[0]["rows"]), 1)

	def test_course_schedule_query_scopes_branch_user(self):
		director_email = "sched-director@test.local"
		if not frappe.db.exists("User", director_email):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": director_email,
					"first_name": "Sched",
					"last_name": "Director",
					"send_welcome_email": 0,
					"user_type": "System User",
				}
			)
			user.append("roles", {"role": "Branch Director"})
			user.insert(ignore_permissions=True)
		company = frappe.db.get_value("Company", {}, "name")
		if not frappe.db.get_value("Employee", {"user_id": director_email}, "name"):
			frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": "Sched",
					"last_name": "Director",
					"gender": "Male",
					"date_of_birth": "1985-01-01",
					"date_of_joining": today(),
					"company": company,
					"mys_branch": self.branch_a,
					"user_id": director_email,
				}
			).insert(ignore_permissions=True)
		self.assertTrue(course_schedule_query(director_email))
		self.assertTrue(student_group_query(director_email))
		prev = frappe.session.user
		try:
			frappe.set_user(director_email)
			visible = set(frappe.get_list("Course Schedule", pluck="name", limit_page_length=500))
			self.assertIn(self.schedule_a, visible)
			self.assertNotIn(self.schedule_b, visible)
		finally:
			frappe.set_user(prev)
