"""Phase 8d — unit coverage for MY School unique ID generation + Employee scoping.

Backfills the gap flagged while scoping HR: `api/identity.py` (student + staff
IDs) and the franchise-link validators had no direct tests, and `Employee` was
not branch-scoped. Covers ID format, counter increment, role-code mapping,
franchise-link validation, and the new `employee_query` / `employee_has_permission`.

Run:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_identity
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from myschools.api.identity import (
	ROLE_CODES,
	set_mys_staff_id,
	set_mys_student_id,
	validate_student_franchise_links,
)
from myschools.api.permissions import employee_has_permission, employee_query

CLUSTER = "_TEST_8D_CL"
BRANCH = "_TEST_8D_BR"
BRANCH2 = "_TEST_8D_BR2"
CAMPUS = f"{BRANCH}-Kids"
OTHER_CLUSTER = "_TEST_8D_CL_OTHER"


class TestIdentityGeneration(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.db.get_value("Company", {}, "name")
		cls._build_tree()
		cls._ensure_designation("Teacher")
		cls._ensure_designation("Cleaner")

	@classmethod
	def tearDownClass(cls):
		frappe.db.delete("Employee", {"mys_branch": ["in", [BRANCH, BRANCH2]]})
		for stu in frappe.get_all("Student", {"mys_branch": BRANCH}, pluck="name"):
			frappe.delete_doc("Student", stu, force=True, ignore_permissions=True)
		for user in frappe.get_all(
			"User", {"email": ["like", "_test_8d_%@example.test"]}, pluck="name"
		):
			frappe.delete_doc("User", user, force=True, ignore_permissions=True)
		for campus in [CAMPUS]:
			if frappe.db.exists("MYS Campus", campus):
				frappe.delete_doc("MYS Campus", campus, force=True, ignore_permissions=True)
		for branch in [BRANCH, BRANCH2]:
			if frappe.db.exists("MYS Branch", branch):
				frappe.delete_doc("MYS Branch", branch, force=True, ignore_permissions=True)
		for cluster in [CLUSTER, OTHER_CLUSTER]:
			if frappe.db.exists("MYS Cluster", cluster):
				frappe.delete_doc("MYS Cluster", cluster, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	@classmethod
	def _build_tree(cls):
		for cluster in [CLUSTER, OTHER_CLUSTER]:
			if not frappe.db.exists("MYS Cluster", cluster):
				frappe.get_doc(
					{
						"doctype": "MYS Cluster",
						"cluster_code": cluster,
						"cluster_name": f"Identity Test {cluster}",
						"region": "Test",
					}
				).insert(ignore_permissions=True)
		for branch, cluster in [(BRANCH, CLUSTER), (BRANCH2, CLUSTER)]:
			if not frappe.db.exists("MYS Branch", branch):
				frappe.get_doc(
					{
						"doctype": "MYS Branch",
						"branch_code": branch,
						"branch_name": f"Identity Test {branch}",
						"cluster": cluster,
						"city": "Test",
						"province": "Test",
						"is_active": 1,
						"company": cls.company,
					}
				).insert(ignore_permissions=True)
		if not frappe.db.exists("MYS Campus", CAMPUS):
			frappe.get_doc(
				{
					"doctype": "MYS Campus",
					"branch": BRANCH,
					"campus_type": "Kids",
					"is_active": 1,
				}
			).insert(ignore_permissions=True)

	@staticmethod
	def _ensure_designation(name: str):
		if not frappe.db.exists("Designation", name):
			frappe.get_doc({"doctype": "Designation", "designation_name": name}).insert(
				ignore_permissions=True
			)

	# ---- Student ID --------------------------------------------------------

	def _make_student(self, first_name: str, branch: str = BRANCH):
		doc = frappe.get_doc(
			{
				"doctype": "Student",
				"first_name": first_name,
				"last_name": "Identity",
				"student_email_id": f"_test_8d_{first_name.lower()}@example.test",
				"mys_branch": branch,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	def test_student_id_format_and_cluster_autofill(self):
		stu = self._make_student("Aisha")
		self.assertRegex(stu.mys_student_id, rf"^MYS-{CLUSTER}-{BRANCH}-STU\d{{6}}$")
		self.assertEqual(stu.mys_cluster, CLUSTER)

	def test_student_id_counter_increments_per_branch(self):
		first = self._make_student("Bilal")
		second = self._make_student("Chand")
		n1 = int(first.mys_student_id.rsplit("STU", 1)[1])
		n2 = int(second.mys_student_id.rsplit("STU", 1)[1])
		self.assertEqual(n2, n1 + 1)

	def test_student_id_skipped_without_branch(self):
		doc = frappe.get_doc({"doctype": "Student", "mys_branch": None})
		set_mys_student_id(doc)
		self.assertFalse(doc.get("mys_student_id"))

	def test_franchise_link_validation_rejects_cross_cluster_branch(self):
		doc = frappe.get_doc(
			{"doctype": "Student", "mys_branch": BRANCH, "mys_cluster": OTHER_CLUSTER}
		)
		with self.assertRaises(frappe.ValidationError):
			validate_student_franchise_links(doc)

	def test_franchise_link_validation_accepts_consistent_tree(self):
		doc = frappe.get_doc(
			{
				"doctype": "Student",
				"mys_branch": BRANCH,
				"mys_cluster": CLUSTER,
				"mys_campus": CAMPUS,
			}
		)
		# Should not raise.
		validate_student_franchise_links(doc)

	# ---- Staff ID ----------------------------------------------------------

	def _make_employee(self, first_name: str, designation: str | None, branch: str = BRANCH):
		doc = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": first_name,
				"last_name": "Staff",
				"gender": "Male",
				"date_of_birth": "1990-01-01",
				"date_of_joining": today(),
				"status": "Active",
				"company": self.company,
				"designation": designation,
				"mys_branch": branch,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	def test_staff_id_format_with_role_code(self):
		emp = self._make_employee("Tariq", "Teacher")
		self.assertEqual(ROLE_CODES["Teacher"], "TCH")
		self.assertRegex(emp.mys_staff_id, rf"^MYS-{BRANCH}-TCH\d{{4}}$")

	def test_staff_id_defaults_to_stf_for_unknown_designation(self):
		emp = self._make_employee("Usman", "Cleaner")
		self.assertRegex(emp.mys_staff_id, rf"^MYS-{BRANCH}-STF\d{{4}}$")

	def test_staff_id_counter_is_per_branch_and_designation(self):
		e1 = self._make_employee("Vali", "Teacher")
		e2 = self._make_employee("Wajid", "Teacher")
		n1 = int(e1.mys_staff_id[-4:])
		n2 = int(e2.mys_staff_id[-4:])
		self.assertEqual(n2, n1 + 1)

	def test_staff_id_skipped_without_branch(self):
		doc = frappe.get_doc({"doctype": "Employee", "mys_branch": None, "designation": "Teacher"})
		set_mys_staff_id(doc)
		self.assertFalse(doc.get("mys_staff_id"))


class TestEmployeeScoping(FrappeTestCase):
	"""Branch-scope on Employee mirrors the Student permission pattern."""

	def test_global_role_query_is_unscoped(self):
		# Administrator carries System Manager → global window, empty filter.
		self.assertEqual(employee_query("Administrator"), "")

	def test_has_permission_global_role(self):
		doc = frappe.get_doc({"doctype": "Employee", "mys_branch": "anything"})
		self.assertTrue(employee_has_permission(doc, "read", user="Administrator"))
