"""End-to-end integration: submitted `Fees` → `MYS Royalty Invoice`.

Verifies that `get_branch_collection_for_period` rolls up Frappe Education
`Fees` by `Student.mys_campus`, and that `generate_monthly_royalty_invoices`
picks those collections into per-campus invoice lines.

Run via:
    bench --site test_site run-tests --app myschools \
        --module myschools.tests.test_royalty_from_fees
"""

from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from myschools.api.royalty import (
	generate_monthly_royalty_invoices,
	get_branch_collection_for_period,
)

CLUSTER = "_TEST_FEE_CL"
BRANCH = "_TEST_FEE_BR"
CAMPUS_KIDS = f"{BRANCH}-Kids"
CAMPUS_JUNIOR = f"{BRANCH}-Junior"
CAMPUS_SENIOR = f"{BRANCH}-Senior"

ACADEMIC_YEAR = "_TEST_AY_2026"
ACADEMIC_TERM_NAME = "_TEST_TERM"
ACADEMIC_TERM = f"{ACADEMIC_YEAR} ({ACADEMIC_TERM_NAME})"
PROGRAM_KIDS = "_TEST_PROG_KIDS"
PROGRAM_JUNIOR = "_TEST_PROG_JUNIOR"
PROGRAM_SENIOR = "_TEST_PROG_SENIOR"
FEE_CATEGORY = "_TEST_FEE_CAT"

# Pick a month inside the existing Fiscal Year (FY 2025-2026 covers Jul-25 to
# Jun-26) but distinct from the demo seed (which uses May 2026), so cleanup
# can safely scope to this period without touching real fixtures.
PERIOD_YEAR = 2025
PERIOD_MONTH = 9
POSTING_DATE = date(PERIOD_YEAR, PERIOD_MONTH, 15)
DUE_DATE = date(PERIOD_YEAR, PERIOD_MONTH, 28)
YEAR_START = date(2025, 8, 1)
YEAR_END = date(2026, 7, 31)
TERM_START = date(PERIOD_YEAR, PERIOD_MONTH, 1)
TERM_END = date(PERIOD_YEAR, PERIOD_MONTH, 30)

CAMPUS_AMOUNTS = {
	CAMPUS_KIDS: 100_000,
	CAMPUS_JUNIOR: 200_000,
	CAMPUS_SENIOR: 300_000,
}
PROGRAM_FOR_CAMPUS = {
	CAMPUS_KIDS: PROGRAM_KIDS,
	CAMPUS_JUNIOR: PROGRAM_JUNIOR,
	CAMPUS_SENIOR: PROGRAM_SENIOR,
}


class TestRoyaltyFromFees(FrappeTestCase):
	"""End-to-end Fees → Royalty Invoice integration."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = cls._pick_company()
		cls.receivable = cls._pick_receivable(cls.company)
		cls._build_franchise_tree()
		cls._build_education_prereqs()
		cls.agreement = cls._build_agreement(default_rate=7.0)
		cls._seed_students_and_fees()
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		# Cancel + delete any invoice created for our unique test period (2020-05),
		# regardless of branch — `generate_monthly_royalty_invoices` also visits
		# the demo BR001 / BR014 agreements and creates empty invoices for them.
		for inv_name in frappe.get_all(
			"MYS Royalty Invoice",
			filters={"period_year": str(PERIOD_YEAR), "period_month": f"{PERIOD_MONTH:02d}"},
			pluck="name",
		):
			inv = frappe.get_doc("MYS Royalty Invoice", inv_name)
			if inv.docstatus == 1:
				inv.cancel()
			frappe.delete_doc("MYS Royalty Invoice", inv_name, force=True, ignore_permissions=True)

		# Cancel + delete the submitted agreement.
		if frappe.db.exists("MYS Franchise Agreement", cls.agreement):
			ag = frappe.get_doc("MYS Franchise Agreement", cls.agreement)
			if ag.docstatus == 1:
				ag.cancel()
			frappe.delete_doc(
				"MYS Franchise Agreement", cls.agreement, force=True, ignore_permissions=True
			)
		if frappe.db.exists("MYS Franchise Owner", "_TEST_FEE_OWNER"):
			frappe.delete_doc(
				"MYS Franchise Owner", "_TEST_FEE_OWNER", force=True, ignore_permissions=True
			)

		# Cancel + delete submitted Fees and Program Enrollments, then Students.
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
		for stu in frappe.get_all(
			"Student", filters={"mys_branch": BRANCH}, pluck="name"
		):
			frappe.delete_doc("Student", stu, force=True, ignore_permissions=True)

		# Education prerequisites.
		for fs in frappe.get_all(
			"Fee Structure", filters={"academic_year": ACADEMIC_YEAR}, pluck="name"
		):
			frappe.delete_doc("Fee Structure", fs, force=True, ignore_permissions=True)
		for program in [PROGRAM_KIDS, PROGRAM_JUNIOR, PROGRAM_SENIOR]:
			if frappe.db.exists("Program", program):
				frappe.delete_doc("Program", program, force=True, ignore_permissions=True)
		if frappe.db.exists("Fee Category", FEE_CATEGORY):
			frappe.delete_doc("Fee Category", FEE_CATEGORY, force=True, ignore_permissions=True)
		if frappe.db.exists("Academic Term", ACADEMIC_TERM):
			frappe.delete_doc("Academic Term", ACADEMIC_TERM, force=True, ignore_permissions=True)
		if frappe.db.exists("Academic Year", ACADEMIC_YEAR):
			frappe.delete_doc("Academic Year", ACADEMIC_YEAR, force=True, ignore_permissions=True)

		# Franchise tree.
		for campus in [CAMPUS_KIDS, CAMPUS_JUNIOR, CAMPUS_SENIOR]:
			if frappe.db.exists("MYS Campus", campus):
				frappe.delete_doc("MYS Campus", campus, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Branch", BRANCH):
			frappe.delete_doc("MYS Branch", BRANCH, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.delete_doc("MYS Cluster", CLUSTER, force=True, ignore_permissions=True)

		frappe.db.commit()
		super().tearDownClass()

	# --- fixtures -----------------------------------------------------------

	@classmethod
	def _pick_company(cls):
		"""Reuse whatever Company the test site has (ERPNext setup creates one)."""
		company = frappe.db.get_value("Company", {}, "name")
		if not company:
			raise RuntimeError("No Company in test site; ERPNext setup expected.")
		return company

	@classmethod
	def _pick_receivable(cls, company):
		acct = frappe.db.get_value(
			"Account",
			{"company": company, "account_type": "Receivable", "is_group": 0},
			"name",
		)
		if not acct:
			raise RuntimeError(f"No Receivable Account for {company}")
		return acct

	@classmethod
	def _build_franchise_tree(cls):
		if not frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.get_doc(
				{
					"doctype": "MYS Cluster",
					"cluster_code": CLUSTER,
					"cluster_name": "Test Fee Cluster",
					"region": "Test",
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("MYS Branch", BRANCH):
			frappe.get_doc(
				{
					"doctype": "MYS Branch",
					"branch_code": BRANCH,
					"branch_name": "Test Fee Branch",
					"cluster": CLUSTER,
					"city": "Testville",
					"province": "Test",
					"is_active": 1,
					"company": cls.company,
				}
			).insert(ignore_permissions=True)
		for ctype in ["Kids", "Junior", "Senior"]:
			name = f"{BRANCH}-{ctype}"
			if not frappe.db.exists("MYS Campus", name):
				frappe.get_doc(
					{
						"doctype": "MYS Campus",
						"branch": BRANCH,
						"campus_type": ctype,
						"is_active": 1,
					}
				).insert(ignore_permissions=True)
		if not frappe.db.exists("MYS Franchise Owner", "_TEST_FEE_OWNER"):
			frappe.get_doc(
				{
					"doctype": "MYS Franchise Owner",
					"owner_name": "_TEST_FEE_OWNER",
					"status": "Active",
					"phone": "+92-300-0000000",
					"email": "test_fee_owner@example.com",
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
			frappe.get_doc(
				{"doctype": "Fee Category", "category_name": FEE_CATEGORY}
			).insert(ignore_permissions=True)
		for program in [PROGRAM_KIDS, PROGRAM_JUNIOR, PROGRAM_SENIOR]:
			if not frappe.db.exists("Program", program):
				frappe.get_doc(
					{
						"doctype": "Program",
						"program_name": program,
						"program_code": program,
					}
				).insert(ignore_permissions=True)

	@classmethod
	def _build_agreement(cls, default_rate: float):
		ag = frappe.get_doc(
			{
				"doctype": "MYS Franchise Agreement",
				"franchisee": frappe.db.get_value(
					"MYS Franchise Owner", {"owner_name": "_TEST_FEE_OWNER"}, "name"
				),
				"branch": BRANCH,
				"company": cls.company,
				"start_date": YEAR_START,
				"end_date": YEAR_END,
				"default_royalty_rate": default_rate,
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
	def _seed_students_and_fees(cls):
		for campus, amount in CAMPUS_AMOUNTS.items():
			program = PROGRAM_FOR_CAMPUS[campus]
			fs = frappe.get_doc(
				{
					"doctype": "Fee Structure",
					"program": program,
					"academic_year": ACADEMIC_YEAR,
					"company": cls.company,
					"receivable_account": cls.receivable,
					"components": [{"fees_category": FEE_CATEGORY, "amount": amount}],
				}
			).insert(ignore_permissions=True)

			stu = frappe.get_doc(
				{
					"doctype": "Student",
					"first_name": f"Test{campus}",
					"last_name": "Student",
					"student_email_id": f"test-{campus.lower()}@example.test",
					"mys_cluster": CLUSTER,
					"mys_branch": BRANCH,
					"mys_campus": campus,
				}
			).insert(ignore_permissions=True)

			pe = frappe.get_doc(
				{
					"doctype": "Program Enrollment",
					"student": stu.name,
					"program": program,
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
					"components": [{"fees_category": FEE_CATEGORY, "amount": amount}],
				}
			)
			fee.insert(ignore_permissions=True)
			fee.submit()

	# --- tests --------------------------------------------------------------

	def test_collection_rollup_groups_by_campus(self):
		"""get_branch_collection_for_period sums submitted Fees grouped by mys_campus."""
		collections = get_branch_collection_for_period(BRANCH, PERIOD_YEAR, PERIOD_MONTH)
		self.assertEqual(collections.get(CAMPUS_KIDS), 100_000)
		self.assertEqual(collections.get(CAMPUS_JUNIOR), 200_000)
		self.assertEqual(collections.get(CAMPUS_SENIOR), 300_000)

	def test_collection_excludes_other_months(self):
		"""Fees from a different month must not appear in the rollup."""
		collections = get_branch_collection_for_period(BRANCH, PERIOD_YEAR, PERIOD_MONTH + 1)
		self.assertEqual(collections, {})

	def test_invoice_generation_picks_real_fees(self):
		"""generate_monthly_royalty_invoices feeds real Fees into campus_lines."""
		results = generate_monthly_royalty_invoices(year=PERIOD_YEAR, month=PERIOD_MONTH)

		ours = [r for r in results if r.get("branch") == BRANCH]
		self.assertEqual(len(ours), 1, f"expected one invoice for {BRANCH}, got {ours!r}")
		inv = frappe.get_doc("MYS Royalty Invoice", ours[0]["invoice"])

		by_campus = {line.campus: line for line in inv.campus_lines}
		self.assertEqual(by_campus[CAMPUS_KIDS].collection_amount, 100_000)
		self.assertEqual(by_campus[CAMPUS_JUNIOR].collection_amount, 200_000)
		self.assertEqual(by_campus[CAMPUS_SENIOR].collection_amount, 300_000)

		# All three resolve to the agreement default (7%); no overrides.
		for line in inv.campus_lines:
			self.assertEqual(line.rate_percent, 7.0)
			self.assertEqual(line.rate_source, "agreement_default")

		# Total = 600,000 @ 7% = 42,000
		self.assertEqual(inv.total_collection, 600_000)
		self.assertEqual(inv.royalty_amount, 42_000)
