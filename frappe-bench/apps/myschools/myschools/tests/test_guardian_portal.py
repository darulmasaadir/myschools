"""Phase 7b — Guardian portal content (children, fees, attendance, feedback).

Run via:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_guardian_portal
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from myschools.api.guardian_portal import (
	assert_guardian_owns_student,
	get_attendance_for_guardian,
	get_fees_for_guardian,
	get_guardian_for_user,
	get_linked_student_ids,
	get_students_for_guardian,
	submit_guardian_feedback,
)


class TestGuardianPortalAccess(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.guardian_email = "mys-portal-7b-guardian@test.local"
		cls.student_name = cls._ensure_student()
		cls.guardian_name = cls._ensure_guardian(cls.student_name)

	@classmethod
	def _ensure_student(cls):
		branch = frappe.db.get_value("MYS Branch", {}, "name")
		if not branch:
			cluster = frappe.get_doc(
				{"doctype": "MYS Cluster", "cluster_name": "Portal Test", "cluster_code": "PT"}
			).insert(ignore_permissions=True)
			branch = (
				frappe.get_doc(
					{
						"doctype": "MYS Branch",
						"branch_name": "Portal Branch",
						"branch_code": "PTB",
						"cluster": cluster.name,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		student = frappe.get_doc(
			{
				"doctype": "Student",
				"first_name": "Portal",
				"last_name": "Child",
				"student_email_id": "mys-portal-7b-student@test.local",
				"mys_branch": branch,
			}
		)
		student.insert(ignore_permissions=True)
		return student.name

	@classmethod
	def _ensure_guardian(cls, student_name):
		if frappe.db.exists("Guardian", {"email_address": cls.guardian_email}):
			gname = frappe.db.get_value("Guardian", {"email_address": cls.guardian_email}, "name")
			guardian = frappe.get_doc("Guardian", gname)
		else:
			guardian = frappe.get_doc(
				{
					"doctype": "Guardian",
					"guardian_name": "Portal Guardian",
					"email_address": cls.guardian_email,
				}
			)
			guardian.insert(ignore_permissions=True)
		student = frappe.get_doc("Student", student_name)
		linked_guardians = {row.guardian for row in student.get("guardians") or []}
		if guardian.name not in linked_guardians:
			student.append("guardians", {"guardian": guardian.name, "relation": "Father"})
			student.save(ignore_permissions=True)
		if frappe.db.exists("User", cls.guardian_email):
			user_name = cls.guardian_email
		else:
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": cls.guardian_email,
					"first_name": "Portal",
					"last_name": "Guardian",
					"send_welcome_email": 0,
					"user_type": "Website User",
				}
			)
			user.append("roles", {"role": "Guardian"})
			user.insert(ignore_permissions=True)
			user_name = user.name
		frappe.db.set_value("Guardian", guardian.name, "user", user_name)
		return guardian.name

	def test_linked_students_and_ownership(self):
		guardian = frappe.get_doc("Guardian", self.guardian_name)
		ids = get_linked_student_ids(guardian)
		self.assertIn(self.student_name, ids)
		students = get_students_for_guardian(guardian)
		self.assertTrue(any(s["name"] == self.student_name for s in students))
		assert_guardian_owns_student(self.student_name, guardian)
		with self.assertRaises(frappe.PermissionError):
			assert_guardian_owns_student("__not_linked__", guardian)

	def test_guardian_user_resolution(self):
		frappe.set_user(self.guardian_email)
		try:
			doc = get_guardian_for_user()
			self.assertIsNotNone(doc)
			self.assertEqual(doc.name, self.guardian_name)
		finally:
			frappe.set_user("Administrator")

	def test_submit_feedback_creates_communication_log(self):
		frappe.set_user(self.guardian_email)
		try:
			out = submit_guardian_feedback("Portal test", "Hello from guardian portal test.")
			self.assertTrue(out.get("ok"))
			log = frappe.get_doc("MYS Communication Log", out["name"])
			self.assertEqual(log.channel, "In-App")
			self.assertEqual(log.subject, "Portal test")
		finally:
			frappe.set_user("Administrator")

	def test_fees_and_attendance_queries_empty_without_data(self):
		guardian = frappe.get_doc("Guardian", self.guardian_name)
		# No submitted fees / attendance seeded for this student in this test module.
		fees = get_fees_for_guardian(guardian)
		self.assertIsInstance(fees, list)
		attendance = get_attendance_for_guardian(guardian, days=30)
		self.assertIsInstance(attendance, list)
