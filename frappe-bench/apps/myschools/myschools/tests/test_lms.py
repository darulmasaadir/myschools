"""Phase 15 — LMS integration: branch-scoped LMS Course rows.

Run:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_lms
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from myschools.api.lms import (
	ensure_lms_course_permissions,
	lms_course_has_permission,
	lms_course_query,
	validate_mys_lms_course,
)
from myschools.setup.install import (
	create_custom_franchise_fields,
	create_franchise_roles,
	grant_franchise_role_permissions,
)

CLUSTER = "_TEST_15_LMS_CL"
BRANCH_A = "_TEST_15_LMS_BRA"
BRANCH_B = "_TEST_15_LMS_BRB"
INSTRUCTOR = "lms-instructor@test.local"


class TestLmsIntegration(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.has_lms = frappe.db.exists("DocType", "LMS Course")
		if not cls.has_lms:
			return
		create_franchise_roles()
		create_custom_franchise_fields()
		grant_franchise_role_permissions()
		ensure_lms_course_permissions()
		cls.branch_a = cls._ensure_branch(BRANCH_A)
		cls.branch_b = cls._ensure_branch(BRANCH_B)
		cls._ensure_instructor_user()
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		if not cls.has_lms:
			super().tearDownClass()
			return
		frappe.db.rollback()
		for name in frappe.get_all(
			"LMS Course", filters={"mys_branch": ["in", [BRANCH_A, BRANCH_B]]}, pluck="name"
		):
			frappe.delete_doc("LMS Course", name, force=True, ignore_permissions=True)
		for br in (BRANCH_A, BRANCH_B):
			if frappe.db.exists("MYS Branch", br):
				frappe.delete_doc("MYS Branch", br, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.delete_doc("MYS Cluster", CLUSTER, force=True, ignore_permissions=True)
		if frappe.db.exists("User", INSTRUCTOR):
			frappe.delete_doc("User", INSTRUCTOR, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	@classmethod
	def _ensure_branch(cls, code: str) -> str:
		existing = frappe.db.get_value("MYS Branch", {"branch_code": code}, "name")
		if existing:
			return existing
		if not frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.get_doc(
				{"doctype": "MYS Cluster", "cluster_name": "LMS Cluster", "cluster_code": CLUSTER}
			).insert(ignore_permissions=True)
		return (
			frappe.get_doc(
				{
					"doctype": "MYS Branch",
					"branch_name": f"LMS Branch {code}",
					"branch_code": code,
					"cluster": CLUSTER,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	@classmethod
	def _ensure_instructor_user(cls):
		if frappe.db.exists("User", INSTRUCTOR):
			return
		frappe.get_doc(
			{
				"doctype": "User",
				"email": INSTRUCTOR,
				"first_name": "LMS Instructor",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)

	def _new_course(self, branch: str, title: str):
		return frappe.get_doc(
			{
				"doctype": "LMS Course",
				"title": title,
				"short_introduction": "Test intro",
				"description": "Test description",
				"mys_branch": branch,
				"instructors": [{"instructor": INSTRUCTOR}],
			}
		)

	def test_validate_requires_branch(self):
		if not self.has_lms:
			self.skipTest("lms not installed")
		doc = frappe.get_doc(
			{
				"doctype": "LMS Course",
				"title": "No Branch Course",
				"short_introduction": "x",
				"description": "y",
				"instructors": [{"instructor": INSTRUCTOR}],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			validate_mys_lms_course(doc)

	def test_lms_course_query_scopes_branch_user(self):
		if not self.has_lms:
			self.skipTest("lms not installed")
		director = "lms-director@test.local"
		if not frappe.db.exists("User", director):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": director,
					"first_name": "LMS Director",
					"send_welcome_email": 0,
				}
			)
			user.insert(ignore_permissions=True)
			user.add_roles("Branch Director")
		company = frappe.db.get_value("Company", {}, "name")
		if not frappe.db.get_value("Employee", {"user_id": director}, "name"):
			frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": "LMS Director",
					"gender": "Male",
					"date_of_birth": "1985-01-01",
					"date_of_joining": "2026-01-01",
					"company": company,
					"mys_branch": self.branch_a,
					"user_id": director,
				}
			).insert(ignore_permissions=True)

		a = self._new_course(self.branch_a, "Scope A Course")
		a.insert(ignore_permissions=True)
		b = self._new_course(self.branch_b, "Scope B Course")
		b.insert(ignore_permissions=True)

		cond = lms_course_query(director)
		self.assertIn(self.branch_a, cond)
		self.assertNotIn("__none__", cond)

		prev = frappe.session.user
		try:
			frappe.set_user(director)
			visible = set(frappe.get_list("LMS Course", pluck="name", limit_page_length=500))
			self.assertIn(a.name, visible)
			self.assertNotIn(b.name, visible)
		finally:
			frappe.set_user(prev)

	def test_has_permission_denies_other_branch(self):
		if not self.has_lms:
			self.skipTest("lms not installed")
		director = "lms-director@test.local"
		if not frappe.db.exists("User", director):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": director,
					"first_name": "LMS Director",
					"send_welcome_email": 0,
				}
			)
			user.insert(ignore_permissions=True)
			user.add_roles("Branch Director")
		company = frappe.db.get_value("Company", {}, "name")
		if not frappe.db.get_value("Employee", {"user_id": director}, "name"):
			frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": "LMS Director",
					"gender": "Male",
					"date_of_birth": "1985-01-01",
					"date_of_joining": "2026-01-01",
					"company": company,
					"mys_branch": self.branch_a,
					"user_id": director,
				}
			).insert(ignore_permissions=True)
		doc = self._new_course(self.branch_b, "Perm B Course")
		doc.insert(ignore_permissions=True)
		self.assertFalse(lms_course_has_permission(doc, "read", user=director))

	def test_custom_fields_exist_on_lms_course(self):
		if not self.has_lms:
			self.skipTest("lms not installed")
		meta = frappe.get_meta("LMS Course")
		self.assertTrue(meta.has_field("mys_branch"))
		self.assertTrue(meta.has_field("mys_program"))
