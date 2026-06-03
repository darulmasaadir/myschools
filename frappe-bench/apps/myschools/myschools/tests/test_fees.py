"""Phase 8a — fee structure overrides and late-fee automation.

Run:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_fees
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from myschools.api.fees import (
	apply_late_fees,
	compute_late_fee_amount,
	resolve_fee_structure,
	resolve_late_fee_policy,
)

CLUSTER = "_TEST_8A_FEE_CL"
BRANCH = "_TEST_8A_FEE_BR"
CAMPUS = f"{BRANCH}-Kids"
PROGRAM = "MYS Kids"
ACADEMIC_YEAR = "2025-2026"
ACADEMIC_TERM = "2025-2026 (May 2026)"
FEE_CATEGORY = "Tuition"
LATE_CATEGORY = "Late Fee"
COMPANY = "MY School Sindh"


class TestFeeOverridesAndLateFees(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._ensure_fee_category(LATE_CATEGORY)
		cls._build_tree()
		cls.company = cls._resolve_company()
		cls.receivable = cls._resolve_receivable()
		cls.default_fs, cls.override_fs = cls._ensure_fee_structures()
		cls._ensure_override()
		cls._ensure_late_policy()

	def tearDown(self):
		self._purge_test_student("_TEST_FEE_late@example.test")
		for late in frappe.get_all("Fees", {"mys_late_fee_for": ["!=", ""]}, pluck="name"):
			doc = frappe.get_doc("Fees", late)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Fees", late, force=True, ignore_permissions=True)
		# Campus-only override from test_resolve_fee_structure_campus_override_wins
		frappe.db.delete("MYS Fee Structure Override", {"branch": BRANCH, "campus": CAMPUS})
		super().tearDown()

	@classmethod
	def tearDownClass(cls):
		frappe.db.delete("MYS Fee Structure Override", {"branch": BRANCH})
		frappe.db.delete("MYS Late Fee Policy", {"branch": BRANCH})
		for name in [cls.default_fs, cls.override_fs]:
			if name and frappe.db.exists("Fee Structure", name):
				frappe.delete_doc("Fee Structure", name, force=True, ignore_permissions=True)
		for campus in [CAMPUS]:
			if frappe.db.exists("MYS Campus", campus):
				frappe.delete_doc("MYS Campus", campus, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Branch", BRANCH):
			frappe.delete_doc("MYS Branch", BRANCH, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.delete_doc("MYS Cluster", CLUSTER, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	@staticmethod
	def _purge_test_student(email: str):
		for stu in frappe.get_all("Student", {"student_email_id": email}, pluck="name"):
			for fee in frappe.get_all("Fees", {"student": stu}, pluck="name"):
				doc = frappe.get_doc("Fees", fee)
				if doc.docstatus == 1:
					doc.cancel()
				frappe.delete_doc("Fees", fee, force=True, ignore_permissions=True)
			for pe in frappe.get_all("Program Enrollment", {"student": stu}, pluck="name"):
				doc = frappe.get_doc("Program Enrollment", pe)
				if doc.docstatus == 1:
					doc.cancel()
				frappe.delete_doc("Program Enrollment", pe, force=True, ignore_permissions=True)
			frappe.delete_doc("Student", stu, force=True, ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def _ensure_fee_category(cls, name: str):
		if not frappe.db.exists("Fee Category", name):
			frappe.get_doc({"doctype": "Fee Category", "category_name": name}).insert(ignore_permissions=True)

	@classmethod
	def _build_tree(cls):
		if not frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.get_doc(
				{
					"doctype": "MYS Cluster",
					"cluster_code": CLUSTER,
					"cluster_name": "Fee Test Cluster",
					"region": "Test",
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("MYS Branch", BRANCH):
			frappe.get_doc(
				{
					"doctype": "MYS Branch",
					"branch_code": BRANCH,
					"branch_name": "Fee Test Branch",
					"cluster": CLUSTER,
					"city": "Test",
					"province": "Test",
					"is_active": 1,
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

	@classmethod
	def _resolve_company(cls) -> str:
		company = frappe.db.get_value("MYS Branch", BRANCH, "company") or frappe.db.get_value(
			"Company", {}, "name"
		)
		if not company:
			raise RuntimeError("No Company on site for fee tests")
		return company

	@classmethod
	def _resolve_receivable(cls) -> str:
		acc = frappe.db.get_value(
			"Account",
			{"company": cls.company, "account_type": "Receivable", "is_group": 0},
			"name",
		)
		if not acc:
			raise RuntimeError("No receivable account for fee tests")
		return acc

	@classmethod
	def _ensure_fee_structures(cls) -> tuple[str, str]:
		default = frappe.db.get_value(
			"Fee Structure",
			{"program": PROGRAM, "academic_year": ACADEMIC_YEAR, "company": cls.company},
			"name",
		)
		if not default:
			default = (
				frappe.get_doc(
					{
						"doctype": "Fee Structure",
						"program": PROGRAM,
						"academic_year": ACADEMIC_YEAR,
						"company": cls.company,
						"receivable_account": cls.receivable,
						"components": [{"fees_category": FEE_CATEGORY, "amount": 100_000}],
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		override = frappe.get_doc(
			{
				"doctype": "Fee Structure",
				"program": PROGRAM,
				"academic_year": ACADEMIC_YEAR,
				"company": cls.company,
				"receivable_account": cls.receivable,
				"components": [{"fees_category": FEE_CATEGORY, "amount": 120_000}],
			}
		).insert(ignore_permissions=True)
		return default, override.name

	@classmethod
	def _ensure_override(cls):
		frappe.get_doc(
			{
				"doctype": "MYS Fee Structure Override",
				"branch": BRANCH,
				"program": PROGRAM,
				"academic_year": ACADEMIC_YEAR,
				"fee_structure": cls.override_fs,
				"effective_from": "2025-01-01",
				"is_active": 1,
			}
		).insert(ignore_permissions=True)

	@classmethod
	def _ensure_late_policy(cls):
		frappe.get_doc(
			{
				"doctype": "MYS Late Fee Policy",
				"branch": BRANCH,
				"grace_days": 7,
				"late_fee_percent": 10,
				"late_fee_minimum": 500,
				"fees_category": LATE_CATEGORY,
				"effective_from": "2025-01-01",
				"is_active": 1,
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()

	def test_resolve_fee_structure_branch_override(self):
		fs, source = resolve_fee_structure(BRANCH, PROGRAM, ACADEMIC_YEAR, self.company, campus=None)
		self.assertEqual(fs, self.override_fs)
		self.assertEqual(source, "branch_override")

	def test_resolve_fee_structure_campus_override_wins(self):
		campus_fs = frappe.get_doc(
			{
				"doctype": "Fee Structure",
				"program": PROGRAM,
				"academic_year": ACADEMIC_YEAR,
				"company": self.company,
				"receivable_account": self.receivable,
				"components": [{"fees_category": FEE_CATEGORY, "amount": 130_000}],
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "MYS Fee Structure Override",
				"branch": BRANCH,
				"campus": CAMPUS,
				"program": PROGRAM,
				"academic_year": ACADEMIC_YEAR,
				"fee_structure": campus_fs.name,
				"effective_from": "2025-01-01",
				"is_active": 1,
			}
		).insert(ignore_permissions=True)
		fs, source = resolve_fee_structure(BRANCH, PROGRAM, ACADEMIC_YEAR, self.company, campus=CAMPUS)
		self.assertEqual(fs, campus_fs.name)
		self.assertEqual(source, "campus_override")

	def test_compute_late_fee_respects_minimum(self):
		policy = resolve_late_fee_policy(BRANCH)
		self.assertIsNotNone(policy)
		self.assertEqual(compute_late_fee_amount(1_000, policy), 500)
		self.assertEqual(compute_late_fee_amount(10_000, policy), 1_000)

	def test_apply_late_fees_creates_linked_invoice(self):
		email = "_TEST_FEE_late@example.test"
		self._purge_test_student(email)
		student = frappe.get_doc(
			{
				"doctype": "Student",
				"first_name": "Late",
				"last_name": "FeeTest",
				"student_email_id": email,
				"mys_cluster": CLUSTER,
				"mys_branch": BRANCH,
				"mys_campus": CAMPUS,
			}
		).insert(ignore_permissions=True)
		pe = frappe.get_doc(
			{
				"doctype": "Program Enrollment",
				"student": student.name,
				"program": PROGRAM,
				"academic_year": ACADEMIC_YEAR,
				"academic_term": ACADEMIC_TERM,
				"enrollment_date": today(),
			}
		)
		pe.insert(ignore_permissions=True)
		pe.submit()

		parent = frappe.get_doc(
			{
				"doctype": "Fees",
				"student": student.name,
				"program_enrollment": pe.name,
				"fee_structure": self.default_fs,
				"company": self.company,
				"receivable_account": self.receivable,
				"academic_year": ACADEMIC_YEAR,
				"academic_term": ACADEMIC_TERM,
				"posting_date": add_days(today(), -30),
				"due_date": add_days(today(), -20),
				"components": [{"fees_category": FEE_CATEGORY, "amount": 10_000}],
			}
		)
		parent.insert(ignore_permissions=True)
		parent.submit()

		results = apply_late_fees(dry_run=False)
		created = [r for r in results if r.get("parent_fee") == parent.name and r["status"] == "created"]
		self.assertEqual(len(created), 1)
		self.assertTrue(frappe.db.get_value("Fees", parent.name, "mys_late_fee_applied"))
		late_name = created[0]["late_fee"]
		self.assertEqual(frappe.db.get_value("Fees", late_name, "mys_late_fee_for"), parent.name)

		# Idempotent — second run must not create another late fee
		again = apply_late_fees(dry_run=False)
		self.assertFalse(
			[r for r in again if r.get("parent_fee") == parent.name and r["status"] == "created"]
		)
