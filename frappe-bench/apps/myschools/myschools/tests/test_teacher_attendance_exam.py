"""Phase 10 — Teacher portal attendance + assessment marking.

Run via:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_teacher_attendance_exam
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from myschools.api.teacher_portal import (
	get_assessment_entry_sheet,
	get_assessment_plans_for_teacher,
	get_attendance_sheet,
	save_assessment_scores,
	save_class_attendance,
)
from myschools.scripts.seed_portal_teacher import main as seed_teacher_portal
from myschools.setup.install import create_franchise_roles, grant_franchise_role_permissions


class TestTeacherAttendanceExam(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_franchise_roles()
		grant_franchise_role_permissions()
		cls.seed = seed_teacher_portal()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		super().tearDownClass()

	def test_save_class_attendance_creates_submitted_rows(self):
		frappe.set_user(self.seed["user"])
		group = self.seed["student_group"]
		employee = frappe.get_doc("Employee", self.seed["employee"])
		instructor = frappe.get_doc("Instructor", self.seed["instructor"])
		sheet = get_attendance_sheet(group, nowdate(), instructor, employee)
		self.assertTrue(sheet["rows"])
		student = sheet["rows"][0]["student"]
		result = save_class_attendance(
			group,
			nowdate(),
			json.dumps([{"student": student, "status": "Present"}]),
		)
		self.assertTrue(result["ok"])
		self.assertEqual(result["count"], 1)
		updated = get_attendance_sheet(group, nowdate(), instructor, employee)
		row = next(r for r in updated["rows"] if r["student"] == student)
		self.assertEqual(row["status"], "Present")
		self.assertTrue(row["submitted"])

	def test_teacher_sees_assessment_plan(self):
		frappe.set_user(self.seed["user"])
		if not self.seed.get("assessment_plan"):
			self.skipTest("Assessment Plan doctype not available")
		employee = frappe.get_doc("Employee", self.seed["employee"])
		instructor = frappe.get_doc("Instructor", self.seed["instructor"])
		plans = get_assessment_plans_for_teacher(instructor, employee)
		names = {p["name"] for p in plans}
		self.assertIn(self.seed["assessment_plan"], names)

	def test_save_assessment_scores_submits_result(self):
		frappe.set_user(self.seed["user"])
		plan = self.seed.get("assessment_plan")
		if not plan:
			self.skipTest("Assessment Plan doctype not available")
		employee = frappe.get_doc("Employee", self.seed["employee"])
		instructor = frappe.get_doc("Instructor", self.seed["instructor"])
		entry = get_assessment_entry_sheet(plan, instructor, employee)
		self.assertTrue(entry["rows"])
		student = entry["rows"][0]["student"]
		criteria = entry["criteria"][0]["assessment_criteria"]
		result = save_assessment_scores(
			plan,
			json.dumps([{"student": student, "scores": {criteria: 85}}]),
		)
		self.assertTrue(result["ok"])
		updated = get_assessment_entry_sheet(plan, instructor, employee)
		row = next(r for r in updated["rows"] if r["student"] == student)
		self.assertTrue(row["submitted"])
		self.assertEqual(row["grade"], "B")
