"""Phase 13 — Library: catalog, loans, copy tracking, fine billing + scoping.

Run:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_library
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from myschools.api.library import (
	LIBRARY_FINE_CATEGORY,
	ensure_library_fine_category,
	generate_library_fine,
	get_loans_for_guardian,
	library_loan_query,
	recalc_library_fine,
	return_library_loan,
	scheduled_mark_library_overdue,
)
from myschools.setup.install import create_franchise_roles, grant_franchise_role_permissions

CLUSTER = "_TEST_13_LB_CL"
BRANCH_A = "_TEST_13_LB_BRA"
BRANCH_B = "_TEST_13_LB_BRB"


class TestLibrary(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_franchise_roles()
		grant_franchise_role_permissions()
		ensure_library_fine_category()
		cls.company = frappe.db.get_value("Company", {}, "name")
		cls.branch_a = cls._ensure_branch(BRANCH_A, with_company=True)
		cls.branch_b = cls._ensure_branch(BRANCH_B, with_company=True)
		cls.student_a = cls._ensure_student(cls.branch_a, "LB Child A", "lb-child-a@lb.test")
		cls.student_b = cls._ensure_student(cls.branch_b, "LB Child B", "lb-child-b@lb.test")
		cls.item_a = cls._ensure_item(cls.branch_a, "LB Book A", copies=2, fine_per_day=100)
		cls.item_b = cls._ensure_item(cls.branch_b, "LB Book B", copies=1, fine_per_day=50)
		cls._ensure_enrollment(cls.student_a)
		pe = frappe.db.get_value(
			"Program Enrollment",
			{"student": cls.student_a, "docstatus": 1},
			["program", "academic_year"],
			as_dict=True,
		)
		if pe:
			cls._ensure_fee_structure(cls.branch_a, pe.program, pe.academic_year)
		frappe.db.commit()

	def tearDown(self):
		frappe.db.rollback()
		# ``adjust_available_copies`` uses ``db.set_value`` — survives rollback.
		for item in (self.item_a, self.item_b):
			total = frappe.db.get_value("MYS Library Item", item, "total_copies")
			if total is not None:
				frappe.db.set_value(
					"MYS Library Item", item, "available_copies", total, update_modified=False
				)

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		for dt, filt in (
			("MYS Library Loan", {"branch": ["in", [BRANCH_A, BRANCH_B]]}),
			("MYS Library Item", {"branch": ["in", [BRANCH_A, BRANCH_B]]}),
		):
			for name in frappe.get_all(dt, filters=filt, pluck="name"):
				frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
		for fee in frappe.get_all("Fees", {"mys_library_loan_for": ["!=", ""]}, pluck="name"):
			doc = frappe.get_doc("Fees", fee)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Fees", fee, force=True, ignore_permissions=True)
		for stu in frappe.get_all("Student", {"student_email_id": ["like", "%@lb.test"]}, pluck="name"):
			frappe.delete_doc("Student", stu, force=True, ignore_permissions=True)
		for br in (BRANCH_A, BRANCH_B):
			if frappe.db.exists("MYS Branch", br):
				frappe.delete_doc("MYS Branch", br, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.delete_doc("MYS Cluster", CLUSTER, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	@classmethod
	def _ensure_branch(cls, code: str, with_company: bool = False) -> str:
		existing = frappe.db.get_value("MYS Branch", {"branch_code": code}, "name")
		if existing:
			return existing
		if not frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.get_doc(
				{"doctype": "MYS Cluster", "cluster_name": "LB Cluster", "cluster_code": CLUSTER}
			).insert(ignore_permissions=True)
		doc = {
			"doctype": "MYS Branch",
			"branch_name": f"LB Branch {code}",
			"branch_code": code,
			"cluster": CLUSTER,
		}
		if with_company:
			doc["company"] = cls.company
		return frappe.get_doc(doc).insert(ignore_permissions=True).name

	@classmethod
	def _ensure_student(cls, branch: str, label: str, email: str) -> str:
		existing = frappe.db.get_value("Student", {"student_email_id": email}, "name")
		if existing:
			frappe.db.set_value("Student", existing, "mys_branch", branch)
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
	def _ensure_item(cls, branch: str, title: str, copies: int = 1, fine_per_day: float = 50) -> str:
		existing = frappe.db.get_value("MYS Library Item", {"title": title, "branch": branch}, "name")
		if existing:
			frappe.db.set_value(
				"MYS Library Item",
				existing,
				{"total_copies": copies, "available_copies": copies, "fine_per_day": fine_per_day},
			)
			return existing
		return (
			frappe.get_doc(
				{
					"doctype": "MYS Library Item",
					"title": title,
					"branch": branch,
					"total_copies": copies,
					"available_copies": copies,
					"fine_per_day": fine_per_day,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	@classmethod
	def _ensure_enrollment(cls, student: str) -> str:
		existing = frappe.db.get_value("Program Enrollment", {"student": student, "docstatus": 1}, "name")
		if existing:
			return existing
		program = frappe.db.get_value("Program", {}, "name")
		if not program:
			program = (
				frappe.get_doc({"doctype": "Program", "program_name": "LB Program", "program_code": "LBP"})
				.insert(ignore_permissions=True)
				.name
			)
		year = frappe.db.get_value("Academic Year", {}, "name")
		if not year:
			year = (
				frappe.get_doc(
					{
						"doctype": "Academic Year",
						"academic_year_name": "LB Year",
						"year_start_date": "2025-01-01",
						"year_end_date": "2025-12-31",
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		doc = frappe.get_doc(
			{
				"doctype": "Program Enrollment",
				"student": student,
				"program": program,
				"academic_year": year,
				"enrollment_date": today(),
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	@classmethod
	def _ensure_fee_structure(cls, branch: str, program: str, academic_year: str) -> str:
		existing = frappe.db.get_value(
			"Fee Structure",
			{"program": program, "academic_year": academic_year},
			"name",
		)
		if existing:
			return existing
		category = LIBRARY_FINE_CATEGORY
		if not frappe.db.exists("Fee Category", category):
			ensure_library_fine_category()
		doc = frappe.get_doc(
			{
				"doctype": "Fee Structure",
				"program": program,
				"academic_year": academic_year,
				"company": cls.company,
				"components": [{"fees_category": category, "amount": 1000}],
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _new_loan(
		self,
		student: str,
		item: str,
		due_date: str | None = None,
		loan_date: str | None = None,
	):
		loan_date = loan_date or today()
		return frappe.get_doc(
			{
				"doctype": "MYS Library Loan",
				"student": student,
				"library_item": item,
				"loan_date": loan_date,
				"due_date": due_date or add_days(loan_date, 7),
				"status": "On Loan",
			}
		)

	def test_loan_decrements_available_copies(self):
		before = frappe.db.get_value("MYS Library Item", self.item_a, "available_copies")
		loan = self._new_loan(self.student_a, self.item_a)
		loan.insert(ignore_permissions=True)
		after = frappe.db.get_value("MYS Library Item", self.item_a, "available_copies")
		self.assertEqual(after, before - 1)

	def test_branch_consistency_enforced(self):
		loan = self._new_loan(self.student_a, self.item_b)
		with self.assertRaises(frappe.ValidationError):
			loan.insert(ignore_permissions=True)

	def test_no_copy_available_blocks_loan(self):
		# item_b has 1 copy — loan it, then second loan should fail
		frappe.db.set_value("Student", self.student_b, "mys_branch", self.branch_b)
		first = self._new_loan(self.student_b, self.item_b)
		first.insert(ignore_permissions=True)
		second = self._new_loan(self.student_b, self.item_b)
		with self.assertRaises(frappe.ValidationError):
			second.insert(ignore_permissions=True)

	def test_return_restores_copy_and_bills_overdue_fine(self):
		loan = self._new_loan(
			self.student_a,
			self.item_a,
			loan_date=add_days(today(), -10),
			due_date=add_days(today(), -3),
		)
		loan.insert(ignore_permissions=True)
		before = frappe.db.get_value("MYS Library Item", self.item_a, "available_copies")
		result = return_library_loan(loan.name)
		self.assertEqual(result["status"], "returned")
		after = frappe.db.get_value("MYS Library Item", self.item_a, "available_copies")
		self.assertEqual(after, before + 1)
		updated = frappe.get_doc("MYS Library Loan", loan.name)
		self.assertEqual(updated.status, "Returned")
		self.assertTrue(updated.fine_billed)
		self.assertTrue(frappe.db.exists("Fees", {"mys_library_loan_for": loan.name, "docstatus": 1}))

	def test_fine_generation_idempotent(self):
		loan = self._new_loan(
			self.student_a,
			self.item_a,
			loan_date=add_days(today(), -10),
			due_date=add_days(today(), -2),
		)
		loan.insert(ignore_permissions=True)
		loan.status = "Overdue"
		recalc_library_fine(loan)
		loan.db_update()
		first = generate_library_fine(loan.name)
		self.assertEqual(first["status"], "created")
		second = generate_library_fine(loan.name)
		self.assertEqual(second["status"], "skipped")

	def test_scheduled_mark_overdue(self):
		loan = self._new_loan(
			self.student_a,
			self.item_a,
			loan_date=add_days(today(), -7),
			due_date=add_days(today(), -1),
		)
		loan.insert(ignore_permissions=True)
		scheduled_mark_library_overdue()
		self.assertEqual(frappe.db.get_value("MYS Library Loan", loan.name, "status"), "Overdue")

	def test_library_loan_query_scopes_branch_user(self):
		director = "lb-director@test.local"
		if not frappe.db.exists("User", director):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": director,
					"first_name": "LB Director",
					"send_welcome_email": 0,
				}
			)
			user.insert(ignore_permissions=True)
			user.add_roles("Branch Director")
		if not frappe.db.get_value("Employee", {"user_id": director}, "name"):
			frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": "LB Director",
					"gender": "Male",
					"date_of_birth": "1985-01-01",
					"date_of_joining": today(),
					"company": self.company,
					"mys_branch": self.branch_a,
					"user_id": director,
				}
			).insert(ignore_permissions=True)

		cond = library_loan_query(director)
		self.assertIn(self.branch_a, cond)
		self.assertNotIn("__none__", cond)

		a = self._new_loan(self.student_a, self.item_a)
		a.insert(ignore_permissions=True)
		frappe.db.set_value("Student", self.student_b, "mys_branch", self.branch_b)
		b = self._new_loan(self.student_b, self.item_b)
		b.insert(ignore_permissions=True)

		prev = frappe.session.user
		try:
			frappe.set_user(director)
			visible = set(
				frappe.get_list("MYS Library Loan", pluck="name", limit_page_length=500)
			)
			self.assertIn(a.name, visible)
			self.assertNotIn(b.name, visible)
		finally:
			frappe.set_user(prev)

	def test_get_loans_for_guardian(self):
		loan = self._new_loan(self.student_a, self.item_a)
		loan.insert(ignore_permissions=True)
		guardian = frappe.get_doc(
			{
				"doctype": "Guardian",
				"guardian_name": "LB Test Guardian",
				"email_address": "lb-guardian@lb.test",
			}
		).insert(ignore_permissions=True)
		student = frappe.get_doc("Student", self.student_a)
		student.append("guardians", {"guardian": guardian.name, "relation": "Father"})
		student.save(ignore_permissions=True)
		rows = get_loans_for_guardian(guardian)
		self.assertTrue(any(r["name"] == loan.name for r in rows))
