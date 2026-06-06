"""Phase 8e — payment gateway adapters."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from myschools.api.fees import apply_resolved_fee_structure_on_fees
from myschools.api.payment_providers import dispatch_payment
from myschools.api.payments import initiate_fee_payment

CLUSTER = "_TEST_8E_PAY_CL"
BRANCH = "_TEST_8E_PAY_BR"
CAMPUS = f"{BRANCH}-Kids"
ACADEMIC_YEAR = "_TEST_8E_PAY_AY"
ACADEMIC_TERM = f"{ACADEMIC_YEAR} (Term1)"
PROGRAM = "_TEST_8E_PAY_PROG"
FEE_CATEGORY = "_TEST_8E_PAY_CAT"


class TestPaymentProviders(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("MYS Communication Log", {"channel": "Payment", "subject": ["like", "Payment for%"]})
		frappe.db.commit()
		self._orig_provider = None
		if frappe.db.exists("DocType", "MYS Payment Settings"):
			self._orig_provider = frappe.db.get_single_value("MYS Payment Settings", "payment_provider")

	def tearDown(self):
		if frappe.db.exists("DocType", "MYS Payment Settings") and self._orig_provider is not None:
			frappe.db.set_value(
				"MYS Payment Settings",
				"MYS Payment Settings",
				"payment_provider",
				self._orig_provider or "Stub",
			)
		frappe.db.commit()

	def _set_provider(self, provider: str, **fields):
		if not frappe.db.exists("DocType", "MYS Payment Settings"):
			self.skipTest("MYS Payment Settings not migrated")
		doc = frappe.get_single("MYS Payment Settings")
		doc.payment_provider = provider
		for key, val in fields.items():
			setattr(doc, key, val)
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	def test_stub_provider_returns_reference(self):
		self._set_provider("Stub")
		result = dispatch_payment(
			amount=1500.0,
			currency="PKR",
			reference="FEE-TEST-001",
			description="test stub payment",
		)
		self.assertTrue(result.ok)
		self.assertEqual(result.gateway, "stub")
		self.assertTrue(result.provider_reference)
		self.assertIn("stub_payment_complete", result.payment_url or "")

	def test_jazzcash_missing_credentials_returns_error(self):
		self._set_provider("JazzCash", jazzcash_merchant_id="", jazzcash_return_url="")
		result = dispatch_payment(
			amount=100.0,
			currency="PKR",
			reference="FEE-TEST-002",
			description="jazz fail",
		)
		self.assertFalse(result.ok)
		self.assertEqual(result.gateway, "jazzcash")
		self.assertIn("missing", (result.error or "").lower())

	@patch("requests.post")
	def test_easypaisa_provider_success(self, mock_post: MagicMock):
		mock_post.return_value = MagicMock(
			status_code=200,
			text='{"transaction_id":"EP123","payment_url":"https://pay.example.test/ep"}',
		)
		mock_post.return_value.json.return_value = {
			"transaction_id": "EP123",
			"payment_url": "https://pay.example.test/ep",
		}
		doc = frappe.get_single("MYS Payment Settings")
		doc.payment_provider = "Easypaisa"
		doc.easypaisa_store_id = "STORE1"
		doc.easypaisa_hash_key = "hashsecret"
		doc.easypaisa_return_url = "https://myschools.pk/return"
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		result = dispatch_payment(
			amount=2500.0,
			currency="PKR",
			reference="FEE-TEST-003",
			description="easypaisa ok",
		)
		self.assertTrue(result.ok)
		self.assertEqual(result.gateway, "easypaisa")
		self.assertEqual(result.provider_reference, "EP123")
		mock_post.assert_called_once()


class TestInitiateFeePayment(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("DocType", "MYS Payment Settings"):
			raise unittest.SkipTest("MYS Payment Settings not migrated")
		cls._build_tree()
		cls.company = frappe.db.get_value("MYS Branch", BRANCH, "company")
		cls.receivable = frappe.db.get_value(
			"Account",
			{"company": cls.company, "account_type": "Receivable", "is_group": 0},
			"name",
		)
		if not cls.receivable:
			raise unittest.SkipTest("no receivable account")
		cls._ensure_education_prereqs()
		frappe.db.set_value("MYS Payment Settings", "MYS Payment Settings", "payment_provider", "Stub")
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.db.delete("MYS Communication Log", {"channel": "Payment"})
		for stu in frappe.get_all("Student", {"student_email_id": ["like", "_TEST_8E_%"]}, pluck="name"):
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
		if frappe.db.exists("MYS Campus", CAMPUS):
			frappe.delete_doc("MYS Campus", CAMPUS, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Branch", BRANCH):
			frappe.delete_doc("MYS Branch", BRANCH, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.delete_doc("MYS Cluster", CLUSTER, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	@classmethod
	def _build_tree(cls):
		if not frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.get_doc(
				{
					"doctype": "MYS Cluster",
					"cluster_code": CLUSTER,
					"cluster_name": "Pay Test Cluster",
					"region": "Test",
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("MYS Branch", BRANCH):
			company = frappe.db.get_value("Company", {}, "name")
			frappe.get_doc(
				{
					"doctype": "MYS Branch",
					"branch_code": BRANCH,
					"branch_name": "Pay Test Branch",
					"cluster": CLUSTER,
					"city": "Test",
					"province": "Test",
					"is_active": 1,
					"company": company,
				}
			).insert(ignore_permissions=True)

		if not frappe.db.exists("MYS Campus", CAMPUS):
			frappe.get_doc(
				{"doctype": "MYS Campus", "branch": BRANCH, "campus_type": "Kids", "is_active": 1}
			).insert(ignore_permissions=True)

	@classmethod
	def _ensure_education_prereqs(cls):
		if not frappe.db.exists("Fee Category", FEE_CATEGORY):
			frappe.get_doc({"doctype": "Fee Category", "category_name": FEE_CATEGORY}).insert(
				ignore_permissions=True
			)
		if not frappe.db.exists("Academic Year", ACADEMIC_YEAR):
			frappe.get_doc(
				{
					"doctype": "Academic Year",
					"academic_year_name": ACADEMIC_YEAR,
					"year_start_date": "2025-08-01",
					"year_end_date": "2026-07-31",
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Academic Term", ACADEMIC_TERM):
			frappe.get_doc(
				{
					"doctype": "Academic Term",
					"academic_year": ACADEMIC_YEAR,
					"term_name": "Term1",
					"term_start_date": "2025-09-01",
					"term_end_date": "2025-12-31",
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Program", PROGRAM):
			frappe.get_doc({"doctype": "Program", "program_name": PROGRAM, "program_code": PROGRAM}).insert(
				ignore_permissions=True
			)
		cls.fee_structure = cls._ensure_fee_structure()

	@classmethod
	def _ensure_fee_structure(cls) -> str:
		existing = frappe.db.get_value(
			"Fee Structure",
			{"program": PROGRAM, "academic_year": ACADEMIC_YEAR, "company": cls.company},
			"name",
		)
		if existing:
			return existing
		return (
			frappe.get_doc(
				{
					"doctype": "Fee Structure",
					"program": PROGRAM,
					"academic_year": ACADEMIC_YEAR,
					"company": cls.company,
					"receivable_account": cls.receivable,
					"components": [{"fees_category": FEE_CATEGORY, "amount": 3_000}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _make_submitted_fee(self) -> str:
		student = frappe.get_doc(
			{
				"doctype": "Student",
				"first_name": "Pay",
				"last_name": "Test",
				"student_email_id": "_TEST_8E_pay@example.test",
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
		).insert(ignore_permissions=True)
		pe.submit()
		fee = frappe.get_doc(
			{
				"doctype": "Fees",
				"student": student.name,
				"program_enrollment": pe.name,
				"program": PROGRAM,
				"academic_year": ACADEMIC_YEAR,
				"academic_term": ACADEMIC_TERM,
				"company": self.company,
				"receivable_account": self.receivable,
				"posting_date": today(),
				"due_date": today(),
				"components": [{"fees_category": FEE_CATEGORY, "amount": 3_000}],
			}
		)
		apply_resolved_fee_structure_on_fees(fee)
		fee.insert(ignore_permissions=True)
		fee.submit()
		return fee.name

	def test_initiate_fee_payment_stub_writes_log(self):
		fee_name = self._make_submitted_fee()
		out = initiate_fee_payment(fee_name)
		self.assertTrue(out["ok"])
		self.assertEqual(out["gateway"], "stub")
		row = frappe.db.get_value(
			"MYS Communication Log",
			out["log"],
			["channel", "status", "gateway", "branch"],
			as_dict=True,
		)
		self.assertEqual(row.channel, "Payment")
		self.assertEqual(row.status, "Sent")
		self.assertEqual(row.gateway, "stub")
		self.assertEqual(row.branch, BRANCH)
