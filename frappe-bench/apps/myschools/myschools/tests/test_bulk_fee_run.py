"""8a-4 — bulk Fees generator (MYS Bulk Fee Run)."""

from __future__ import annotations

from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from myschools.api.fees import generate_bulk_fees_for_run

CLUSTER = "_TEST_BFR_CL"
BRANCH = "_TEST_BFR_BR"
CAMPUS = f"{BRANCH}-Kids"
GROUP = "_TEST_BFR_SG"
ACADEMIC_YEAR = "_TEST_BFR_AY"
ACADEMIC_TERM_NAME = "_TEST_BFR_TERM"
ACADEMIC_TERM = f"{ACADEMIC_YEAR} ({ACADEMIC_TERM_NAME})"
PROGRAM = "_TEST_BFR_PROG"
FEE_CATEGORY = "_TEST_BFR_TUITION"
YEAR_START = date(2025, 8, 1)
YEAR_END = date(2026, 7, 31)
TERM_START = date(2025, 9, 1)
TERM_END = date(2025, 12, 31)


class TestBulkFeeRun(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.db.get_value("Company", {}, "name")
		cls.receivable = frappe.db.get_value(
			"Account",
			{"company": cls.company, "account_type": "Receivable", "is_group": 0},
			"name",
		)
		cls._build_tree()
		cls._build_education()
		cls.default_fs = cls._ensure_fee_structure(100_000)
		cls.override_fs = cls._ensure_fee_structure(120_000)
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
		cls._ensure_student_group()
		cls.student, cls.enrollment = cls._ensure_student_and_enrollment()
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		for run in frappe.get_all("MYS Bulk Fee Run", {"branch": BRANCH}, pluck="name"):
			frappe.delete_doc("MYS Bulk Fee Run", run, force=True, ignore_permissions=True)
		for fee in frappe.get_all("Fees", {"student": cls.student}, pluck="name"):
			doc = frappe.get_doc("Fees", fee)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Fees", fee, force=True, ignore_permissions=True)
		if cls.enrollment and frappe.db.exists("Program Enrollment", cls.enrollment):
			pe = frappe.get_doc("Program Enrollment", cls.enrollment)
			if pe.docstatus == 1:
				pe.cancel()
			frappe.delete_doc("Program Enrollment", cls.enrollment, force=True, ignore_permissions=True)
		if cls.student and frappe.db.exists("Student", cls.student):
			frappe.delete_doc("Student", cls.student, force=True, ignore_permissions=True)
		if frappe.db.exists("Student Group", GROUP):
			frappe.delete_doc("Student Group", GROUP, force=True, ignore_permissions=True)
		frappe.db.delete("MYS Fee Structure Override", {"branch": BRANCH})
		for fs in [cls.default_fs, cls.override_fs]:
			if fs and frappe.db.exists("Fee Structure", fs):
				frappe.delete_doc("Fee Structure", fs, force=True, ignore_permissions=True)
		if frappe.db.exists("Program", PROGRAM):
			frappe.delete_doc("Program", PROGRAM, force=True, ignore_permissions=True)
		if frappe.db.exists("Academic Term", ACADEMIC_TERM):
			frappe.delete_doc("Academic Term", ACADEMIC_TERM, force=True, ignore_permissions=True)
		if frappe.db.exists("Academic Year", ACADEMIC_YEAR):
			frappe.delete_doc("Academic Year", ACADEMIC_YEAR, force=True, ignore_permissions=True)
		if frappe.db.exists("Fee Category", FEE_CATEGORY):
			frappe.delete_doc("Fee Category", FEE_CATEGORY, force=True, ignore_permissions=True)
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
					"cluster_name": CLUSTER,
					"region": "Test",
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("MYS Branch", BRANCH):
			frappe.get_doc(
				{
					"doctype": "MYS Branch",
					"branch_code": BRANCH,
					"branch_name": BRANCH,
					"cluster": CLUSTER,
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

	@classmethod
	def _build_education(cls):
		if not frappe.db.exists("Fee Category", FEE_CATEGORY):
			frappe.get_doc({"doctype": "Fee Category", "category_name": FEE_CATEGORY}).insert(
				ignore_permissions=True
			)
		if not frappe.db.exists("Academic Year", ACADEMIC_YEAR):
			frappe.get_doc(
				{
					"doctype": "Academic Year",
					"academic_year_name": ACADEMIC_YEAR,
					"year_start_date": YEAR_START,
					"year_end_date": YEAR_END,
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Academic Term", ACADEMIC_TERM):
			frappe.get_doc(
				{
					"doctype": "Academic Term",
					"academic_year": ACADEMIC_YEAR,
					"term_name": ACADEMIC_TERM_NAME,
					"term_start_date": TERM_START,
					"term_end_date": TERM_END,
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Program", PROGRAM):
			frappe.get_doc(
				{"doctype": "Program", "program_name": PROGRAM, "program_code": PROGRAM}
			).insert(ignore_permissions=True)

	@classmethod
	def _ensure_fee_structure(cls, amount: int) -> str:
		return (
			frappe.get_doc(
				{
					"doctype": "Fee Structure",
					"program": PROGRAM,
					"academic_year": ACADEMIC_YEAR,
					"company": cls.company,
					"receivable_account": cls.receivable,
					"components": [{"fees_category": FEE_CATEGORY, "amount": amount}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	@classmethod
	def _ensure_student_group(cls):
		if frappe.db.exists("Student Group", GROUP):
			return
		sg = frappe.get_doc(
			{
				"doctype": "Student Group",
				"student_group_name": GROUP,
				"group_based_on": "Batch",
				"program": PROGRAM,
				"academic_year": ACADEMIC_YEAR,
				"academic_term": ACADEMIC_TERM,
				"max_strength": 50,
			}
		)
		sg.insert(ignore_permissions=True)

	@classmethod
	def _ensure_student_and_enrollment(cls) -> tuple[str, str]:
		email = "_TEST_BFR_stu@example.test"
		student = frappe.db.get_value("Student", {"student_email_id": email}, "name")
		if not student:
			student = (
				frappe.get_doc(
					{
						"doctype": "Student",
						"first_name": "Bulk",
						"last_name": "FeeRun",
						"student_email_id": email,
						"mys_cluster": CLUSTER,
						"mys_branch": BRANCH,
						"mys_campus": CAMPUS,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		sg = frappe.get_doc("Student Group", GROUP)
		if not frappe.db.exists(
			"Student Group Student", {"parent": GROUP, "student": student}
		):
			sg.append("students", {"student": student, "active": 1})
			sg.save(ignore_permissions=True)

		enrollment = frappe.db.get_value(
			"Program Enrollment",
			{"student": student, "program": PROGRAM, "academic_year": ACADEMIC_YEAR, "docstatus": 1},
			"name",
		)
		if not enrollment:
			pe = frappe.get_doc(
				{
					"doctype": "Program Enrollment",
					"student": student,
					"program": PROGRAM,
					"academic_year": ACADEMIC_YEAR,
					"academic_term": ACADEMIC_TERM,
					"enrollment_date": today(),
				}
			)
			pe.insert(ignore_permissions=True)
			pe.submit()
			enrollment = pe.name
		return student, enrollment

	def test_bulk_run_creates_fees_with_override_structure(self):
		posting = today()
		run = frappe.get_doc(
			{
				"doctype": "MYS Bulk Fee Run",
				"branch": BRANCH,
				"company": self.company,
				"student_group": GROUP,
				"program": PROGRAM,
				"academic_year": ACADEMIC_YEAR,
				"academic_term": ACADEMIC_TERM,
				"posting_date": posting,
				"due_date": posting,
				"submit_fees": 1,
			}
		)
		run.insert(ignore_permissions=True)

		result = generate_bulk_fees_for_run(run.name)
		self.assertEqual(result["created"], 1)
		self.assertEqual(result["status"], "Completed")

		run.reload()
		self.assertEqual(run.lines[0].status, "Created")
		self.assertEqual(run.lines[0].fee_structure, self.override_fs)
		fee = frappe.get_doc("Fees", run.lines[0].fees)
		self.assertEqual(fee.docstatus, 1)
		self.assertEqual(fee.fee_structure, self.override_fs)
		self.assertEqual(fee.grand_total, 120_000)

	def test_bulk_run_skips_duplicate_enrollment(self):
		posting = today()
		run1 = frappe.get_doc(
			{
				"doctype": "MYS Bulk Fee Run",
				"branch": BRANCH,
				"company": self.company,
				"student_group": GROUP,
				"academic_year": ACADEMIC_YEAR,
				"academic_term": ACADEMIC_TERM,
				"posting_date": posting,
				"due_date": posting,
				"submit_fees": 1,
			}
		).insert(ignore_permissions=True)
		generate_bulk_fees_for_run(run1.name)

		run2 = frappe.get_doc(
			{
				"doctype": "MYS Bulk Fee Run",
				"branch": BRANCH,
				"company": self.company,
				"student_group": GROUP,
				"academic_year": ACADEMIC_YEAR,
				"academic_term": ACADEMIC_TERM,
				"posting_date": posting,
				"due_date": posting,
				"submit_fees": 1,
			}
		).insert(ignore_permissions=True)
		result = generate_bulk_fees_for_run(run2.name)
		self.assertEqual(result["created"], 0)
		self.assertEqual(result["skipped"], 1)
