"""Integration tests for the MYS Print Format bundle.

Asserts that:
  1. All four Print Format records ship and import cleanly.
  2. Four Property Setters wire `default_print_format` on the target doctypes.
  3. Each format renders against a real sample doc without raising and
     emits an HTML body that references the doc's name (smoke marker).

Run via:
    bench --site myschools.localhost run-tests --app myschools \\
        --module myschools.tests.test_print_formats
"""

from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today
from frappe.www.printview import get_html_and_style

from myschools.api.royalty import generate_monthly_royalty_invoices

# Use _TEST_PF_ prefix so we never collide with test_inspection / test_royalty.
CLUSTER = "_TEST_PF_CL"
BRANCH = "_TEST_PF_BR"
CAMPUS = f"{BRANCH}-Kids"
OWNER = "_TEST_PF_OWNER"
EMPLOYEE_TAG = "_test_pf_inspector@example.com"

ACADEMIC_YEAR = "_TEST_PF_AY"
ACADEMIC_TERM_NAME = "_TEST_PF_TERM"
ACADEMIC_TERM = f"{ACADEMIC_YEAR} ({ACADEMIC_TERM_NAME})"
PROGRAM = "_TEST_PF_PROG"
FEE_CATEGORY = "_TEST_PF_CAT"

# Period chosen to fall inside FY 2025-07-01..2026-06-30 (Pakistan academic year)
# and away from the demo seed and other tests' months.
PERIOD_YEAR = 2025
PERIOD_MONTH = 10
POSTING_DATE = date(PERIOD_YEAR, PERIOD_MONTH, 15)
DUE_DATE = date(PERIOD_YEAR, PERIOD_MONTH, 28)
YEAR_START = date(2025, 8, 1)
YEAR_END = date(2026, 7, 31)
TERM_START = date(PERIOD_YEAR, PERIOD_MONTH, 1)
TERM_END = date(PERIOD_YEAR, PERIOD_MONTH, 30)
FEE_AMOUNT = 50_000

EXPECTED_FORMATS = {
	"MYS Royalty Invoice": "MYS Royalty Invoice",
	"MYS Inspection Report": "MYS Inspection Visit",
	"MYS Fee Receipt": "Fees",
	"MYS Franchise Agreement": "MYS Franchise Agreement",
	"MYS Report Card": "Assessment Result",
}


class TestPrintFormats(FrappeTestCase):
	"""Ensures branded Print Formats import, get wired as defaults, and render."""

	company: str = ""
	receivable: str = ""
	inspector: str = ""
	agreement: str = ""
	visit: str = ""
	fee: str = ""
	invoice: str = ""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			raise RuntimeError("No Company in test site; ERPNext setup expected.")
		cls.receivable = frappe.db.get_value(
			"Account",
			{"company": cls.company, "account_type": "Receivable", "is_group": 0},
			"name",
		)
		if not cls.receivable:
			raise RuntimeError(f"No Receivable Account for {cls.company}")

		cls._build_franchise_tree()
		cls._build_education_prereqs()
		cls.inspector = cls._build_inspector()
		cls.agreement = cls._build_agreement()
		cls.fee = cls._build_fee()
		cls.visit = cls._build_visit()
		cls.invoice = cls._build_invoice()
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		# Invoices first (period-scoped — generate_monthly_royalty_invoices also
		# visits demo agreements and may create empty invoices for them).
		for inv_name in frappe.get_all(
			"MYS Royalty Invoice",
			filters={"period_year": str(PERIOD_YEAR), "period_month": f"{PERIOD_MONTH:02d}"},
			pluck="name",
		):
			inv = frappe.get_doc("MYS Royalty Invoice", inv_name)
			if inv.docstatus == 1:
				inv.cancel()
			frappe.delete_doc("MYS Royalty Invoice", inv_name, force=True, ignore_permissions=True)

		if cls.agreement and frappe.db.exists("MYS Franchise Agreement", cls.agreement):
			ag = frappe.get_doc("MYS Franchise Agreement", cls.agreement)
			if ag.docstatus == 1:
				ag.cancel()
			frappe.delete_doc("MYS Franchise Agreement", cls.agreement, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Franchise Owner", OWNER):
			frappe.delete_doc("MYS Franchise Owner", OWNER, force=True, ignore_permissions=True)

		if cls.visit and frappe.db.exists("MYS Inspection Visit", cls.visit):
			v = frappe.get_doc("MYS Inspection Visit", cls.visit)
			if v.docstatus == 1:
				v.cancel()
			frappe.delete_doc("MYS Inspection Visit", cls.visit, force=True, ignore_permissions=True)

		for fee in frappe.get_all("Fees", filters={"academic_year": ACADEMIC_YEAR}, pluck="name"):
			fdoc = frappe.get_doc("Fees", fee)
			if fdoc.docstatus == 1:
				fdoc.cancel()
			frappe.delete_doc("Fees", fee, force=True, ignore_permissions=True)
		for pe in frappe.get_all(
			"Program Enrollment", filters={"academic_year": ACADEMIC_YEAR}, pluck="name"
		):
			pedoc = frappe.get_doc("Program Enrollment", pe)
			if pedoc.docstatus == 1:
				pedoc.cancel()
			frappe.delete_doc("Program Enrollment", pe, force=True, ignore_permissions=True)
		for stu in frappe.get_all("Student", filters={"mys_branch": BRANCH}, pluck="name"):
			frappe.delete_doc("Student", stu, force=True, ignore_permissions=True)

		for fs in frappe.get_all("Fee Structure", filters={"academic_year": ACADEMIC_YEAR}, pluck="name"):
			frappe.delete_doc("Fee Structure", fs, force=True, ignore_permissions=True)
		if frappe.db.exists("Program", PROGRAM):
			frappe.delete_doc("Program", PROGRAM, force=True, ignore_permissions=True)
		if frappe.db.exists("Fee Category", FEE_CATEGORY):
			frappe.delete_doc("Fee Category", FEE_CATEGORY, force=True, ignore_permissions=True)
		if frappe.db.exists("Academic Term", ACADEMIC_TERM):
			frappe.delete_doc("Academic Term", ACADEMIC_TERM, force=True, ignore_permissions=True)
		if frappe.db.exists("Academic Year", ACADEMIC_YEAR):
			frappe.delete_doc("Academic Year", ACADEMIC_YEAR, force=True, ignore_permissions=True)

		if cls.inspector and frappe.db.exists("Employee", cls.inspector):
			frappe.delete_doc("Employee", cls.inspector, force=True, ignore_permissions=True)

		if frappe.db.exists("MYS Campus", CAMPUS):
			frappe.delete_doc("MYS Campus", CAMPUS, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Branch", BRANCH):
			frappe.delete_doc("MYS Branch", BRANCH, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.delete_doc("MYS Cluster", CLUSTER, force=True, ignore_permissions=True)

		frappe.db.commit()
		super().tearDownClass()

	# --- fixtures -----------------------------------------------------------

	@classmethod
	def _build_franchise_tree(cls):
		if not frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.get_doc(
				{
					"doctype": "MYS Cluster",
					"cluster_code": CLUSTER,
					"cluster_name": "Test PF Cluster",
					"region": "Test",
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("MYS Branch", BRANCH):
			frappe.get_doc(
				{
					"doctype": "MYS Branch",
					"branch_code": BRANCH,
					"branch_name": "Test PF Branch",
					"cluster": CLUSTER,
					"city": "Testville",
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
		if not frappe.db.exists("MYS Franchise Owner", OWNER):
			frappe.get_doc(
				{
					"doctype": "MYS Franchise Owner",
					"owner_name": OWNER,
					"status": "Active",
					"phone": "+92-300-0000000",
					"email": "test_pf_owner@example.com",
				}
			).insert(ignore_permissions=True)

	@classmethod
	def _build_education_prereqs(cls):
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
		if not frappe.db.exists("Fee Category", FEE_CATEGORY):
			frappe.get_doc({"doctype": "Fee Category", "category_name": FEE_CATEGORY}).insert(
				ignore_permissions=True
			)
		if not frappe.db.exists("Program", PROGRAM):
			frappe.get_doc(
				{
					"doctype": "Program",
					"program_name": PROGRAM,
					"program_code": PROGRAM,
				}
			).insert(ignore_permissions=True)

	@classmethod
	def _build_inspector(cls):
		existing = frappe.db.get_value("Employee", {"personal_email": EMPLOYEE_TAG}, "name")
		if existing:
			return existing
		emp = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": "PF",
				"last_name": "Inspector",
				"personal_email": EMPLOYEE_TAG,
				"gender": "Male",
				"date_of_birth": "1990-01-01",
				"date_of_joining": "2020-01-01",
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		return emp.name

	@classmethod
	def _build_agreement(cls):
		ag = frappe.get_doc(
			{
				"doctype": "MYS Franchise Agreement",
				"franchisee": frappe.db.get_value("MYS Franchise Owner", {"owner_name": OWNER}, "name"),
				"branch": BRANCH,
				"company": cls.company,
				"start_date": YEAR_START,
				"end_date": YEAR_END,
				"default_royalty_rate": 7.0,
				"royalty_base": "Gross Fee Collection",
				"billing_day": 5,
				"grace_days": 10,
				"currency": "PKR",
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		ag.submit()
		return ag.name

	@classmethod
	def _build_fee(cls):
		fs = frappe.get_doc(
			{
				"doctype": "Fee Structure",
				"program": PROGRAM,
				"academic_year": ACADEMIC_YEAR,
				"company": cls.company,
				"receivable_account": cls.receivable,
				"components": [{"fees_category": FEE_CATEGORY, "amount": FEE_AMOUNT}],
			}
		).insert(ignore_permissions=True)

		stu = frappe.get_doc(
			{
				"doctype": "Student",
				"first_name": "PFStudent",
				"last_name": "Test",
				"student_email_id": "test-pf-student@example.test",
				"mys_cluster": CLUSTER,
				"mys_branch": BRANCH,
				"mys_campus": CAMPUS,
			}
		).insert(ignore_permissions=True)

		pe = frappe.get_doc(
			{
				"doctype": "Program Enrollment",
				"student": stu.name,
				"program": PROGRAM,
				"academic_year": ACADEMIC_YEAR,
				"academic_term": ACADEMIC_TERM,
				"enrollment_date": POSTING_DATE,
			}
		)
		pe.insert(ignore_permissions=True)
		pe.submit()

		fee = frappe.get_doc(
			{
				"doctype": "Fees",
				"student": stu.name,
				"program_enrollment": pe.name,
				"fee_structure": fs.name,
				"company": cls.company,
				"receivable_account": cls.receivable,
				"academic_year": ACADEMIC_YEAR,
				"academic_term": ACADEMIC_TERM,
				"posting_date": POSTING_DATE,
				"due_date": DUE_DATE,
				"components": [{"fees_category": FEE_CATEGORY, "amount": FEE_AMOUNT}],
			}
		)
		fee.insert(ignore_permissions=True)
		fee.submit()
		return fee.name

	@classmethod
	def _build_visit(cls):
		v = frappe.get_doc(
			{
				"doctype": "MYS Inspection Visit",
				"branch": BRANCH,
				"campus": CAMPUS,
				"visit_type": "Routine",
				"visit_date": today(),
				"inspector": cls.inspector,
				"checklist_results": [
					{
						"item_text": "Fire exits clear",
						"category": "Safety",
						"severity": "Critical",
						"weight": 3,
						"max_score": 5,
						"result": "Pass",
						"score": 5,
					},
					{
						"item_text": "Classrooms clean",
						"category": "Cleanliness",
						"severity": "Major",
						"weight": 2,
						"max_score": 5,
						"result": "Pass",
						"score": 4,
					},
				],
			}
		).insert(ignore_permissions=True)
		return v.name

	@classmethod
	def _build_invoice(cls):
		"""Run the monthly generator for our period; return the invoice we own."""
		results = generate_monthly_royalty_invoices(year=PERIOD_YEAR, month=PERIOD_MONTH)
		ours = [r for r in results if r.get("branch") == BRANCH]
		if not ours:
			raise RuntimeError(f"generate_monthly_royalty_invoices produced no invoice for {BRANCH}")
		return ours[0]["invoice"]

	# --- assertions ---------------------------------------------------------

	def test_all_print_formats_imported(self):
		"""Every shipped Print Format record exists in DB after migrate."""
		for pf, doctype in EXPECTED_FORMATS.items():
			self.assertTrue(frappe.db.exists("Print Format", pf), f"Print Format {pf!r} not imported")
			actual_doctype = frappe.db.get_value("Print Format", pf, "doc_type")
			self.assertEqual(
				actual_doctype, doctype, f"{pf} is bound to {actual_doctype!r}, want {doctype!r}"
			)

	def test_default_print_format_property_setters_exist(self):
		"""Each target doctype has a Property Setter pointing at the MYS format."""
		for pf, doctype in EXPECTED_FORMATS.items():
			value = frappe.db.get_value(
				"Property Setter",
				{
					"doc_type": doctype,
					"property": "default_print_format",
				},
				"value",
			)
			self.assertEqual(
				value, pf, f"Property Setter for {doctype} default_print_format = {value!r}, want {pf!r}"
			)

	def _render(self, doctype: str, name: str, print_format: str) -> str:
		out = get_html_and_style(doc=doctype, name=name, print_format=print_format, no_letterhead=0)
		return (out or {}).get("html") or ""

	# Marker that the default Letter Head fixture made it into the rendered
	# body — failure here usually means a template forgot to emit
	# `{{ letter_head|safe }}` (custom Jinja formats don't get it automatically
	# the way Frappe's Standard layout does).
	LETTERHEAD_LOGO = "/assets/myschools/images/mys-logo.svg"

	def test_royalty_invoice_renders(self):
		html = self._render("MYS Royalty Invoice", self.invoice, "MYS Royalty Invoice")
		self.assertIn(self.invoice, html)
		self.assertIn("ROYALTY INVOICE", html)
		self.assertIn(BRANCH, html)
		self.assertIn(self.LETTERHEAD_LOGO, html)

	def test_inspection_report_renders(self):
		html = self._render("MYS Inspection Visit", self.visit, "MYS Inspection Report")
		self.assertIn(self.visit, html)
		self.assertIn("INSPECTION REPORT", html)
		self.assertIn("Fire exits clear", html)
		self.assertIn(self.LETTERHEAD_LOGO, html)

	def test_fee_receipt_renders(self):
		html = self._render("Fees", self.fee, "MYS Fee Receipt")
		self.assertIn(self.fee, html)
		self.assertIn("FEE RECEIPT", html)
		self.assertIn(FEE_CATEGORY, html)
		self.assertIn(self.LETTERHEAD_LOGO, html)

	def test_franchise_agreement_renders(self):
		html = self._render("MYS Franchise Agreement", self.agreement, "MYS Franchise Agreement")
		self.assertIn(self.agreement, html)
		self.assertIn("FRANCHISE AGREEMENT", html)
		self.assertIn(BRANCH, html)
		self.assertIn(self.LETTERHEAD_LOGO, html)
