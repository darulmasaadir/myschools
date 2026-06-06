"""Phase 9 — Teacher portal (classes, roster, schedule).

Run via:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_teacher_portal
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from myschools.api.teacher_portal import (
	assert_teacher_owns_group,
	get_roster_for_group,
	get_schedule_for_teacher,
	get_student_groups_for_teacher,
)
from myschools.scripts.seed_portal_teacher import GROUP_NAME
from myschools.scripts.seed_portal_teacher import main as seed_teacher_portal
from myschools.setup.install import create_franchise_roles, grant_franchise_role_permissions


class TestTeacherPortalAccess(FrappeTestCase):
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

	def test_teacher_sees_assigned_student_group(self):
		frappe.set_user(self.seed["user"])
		employee = frappe.get_doc("Employee", self.seed["employee"])
		instructor = frappe.get_doc("Instructor", self.seed["instructor"])
		groups = get_student_groups_for_teacher(instructor, employee)
		names = {g["name"] for g in groups}
		self.assertIn(GROUP_NAME, names)
		group = next(g for g in groups if g["name"] == GROUP_NAME)
		self.assertGreater(group["student_count"], 0)

	def test_roster_is_branch_scoped(self):
		frappe.set_user(self.seed["user"])
		employee = frappe.get_doc("Employee", self.seed["employee"])
		instructor = frappe.get_doc("Instructor", self.seed["instructor"])
		roster = get_roster_for_group(GROUP_NAME, instructor, employee)
		self.assertTrue(roster)
		for row in roster:
			branch = frappe.db.get_value("Student", row["name"], "mys_branch")
			self.assertEqual(branch, self.seed["branch"])

	def test_schedule_lists_upcoming_session(self):
		frappe.set_user(self.seed["user"])
		instructor = frappe.get_doc("Instructor", self.seed["instructor"])
		rows = get_schedule_for_teacher(instructor, days=7)
		self.assertTrue(any(r.get("student_group") == GROUP_NAME for r in rows))

	def test_other_instructor_cannot_open_group(self):
		other = frappe.get_doc(
			{
				"doctype": "Instructor",
				"instructor_name": "Other Portal Teacher",
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		instructor = frappe.get_doc("Instructor", self.seed["instructor"])
		with self.assertRaises(frappe.PermissionError):
			assert_teacher_owns_group(GROUP_NAME, other)
		assert_teacher_owns_group(GROUP_NAME, instructor)
