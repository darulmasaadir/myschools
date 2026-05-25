"""Seed Education prerequisites + students + submitted fees so the royalty
engine has real data to roll up. Run via:

  bench --site myschools.localhost execute myschools.scripts.seed_education.run

Idempotent. Re-runs find existing records by their natural keys and skip.

Closes the loop on the royalty pipeline:
    Student.mys_branch + Fees.posting_date  -->  per-campus collection  -->  Royalty Invoice
"""

import frappe
from frappe.utils import getdate

from myschools.scripts.seed_demo import CLUSTER_COMPANIES

ACADEMIC_YEAR = "2025-2026"
ACADEMIC_TERM_NAME = "May 2026"
# Academic Term's autoname is "{academic_year} ({term_name})"
ACADEMIC_TERM = f"{ACADEMIC_YEAR} ({ACADEMIC_TERM_NAME})"
YEAR_START = "2025-08-01"
YEAR_END = "2026-07-31"
TERM_START = "2026-05-01"
TERM_END = "2026-05-31"

POSTING_DATE = "2026-05-15"
DUE_DATE = "2026-05-31"

FEE_CATEGORY = "Tuition"

PROGRAMS = {
	"Kids": "MYS Kids",
	"Junior": "MYS Junior",
	"Senior": "MYS Senior",
}

CAMPUS_FEE_AMOUNT = {
	"Kids": 300_000,
	"Junior": 400_000,
	"Senior": 600_000,
}

STUDENTS_PER_CAMPUS = 5

BRANCHES = [
	("BR001", "CL01", "MY School Northern Punjab", "Debtors - MSCL01"),
	("BR014", "CL03", "MY School Sindh", "Debtors - MSCL03"),
]


def run():
	_ensure_academic_year_and_term()
	_ensure_fee_category()
	_ensure_programs()
	for branch, cluster, company, receivable in BRANCHES:
		_ensure_fee_structures(company, receivable)
		_ensure_students_and_fees(branch, cluster, company, receivable)
	frappe.db.commit()
	_print_summary()


def _ensure_academic_year_and_term():
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


def _ensure_fee_category():
	if not frappe.db.exists("Fee Category", FEE_CATEGORY):
		frappe.get_doc({"doctype": "Fee Category", "category_name": FEE_CATEGORY}).insert(
			ignore_permissions=True
		)


def _ensure_programs():
	for _campus_type, program_name in PROGRAMS.items():
		if not frappe.db.exists("Program", program_name):
			frappe.get_doc(
				{
					"doctype": "Program",
					"program_name": program_name,
					"program_code": program_name.replace(" ", "-").upper(),
				}
			).insert(ignore_permissions=True)


def _ensure_fee_structures(company, receivable):
	for campus_type, program in PROGRAMS.items():
		amount = CAMPUS_FEE_AMOUNT[campus_type]
		if frappe.db.exists(
			"Fee Structure", {"program": program, "academic_year": ACADEMIC_YEAR, "company": company}
		):
			continue
		fs = frappe.get_doc(
			{
				"doctype": "Fee Structure",
				"program": program,
				"academic_year": ACADEMIC_YEAR,
				"company": company,
				"receivable_account": receivable,
				"components": [
					{
						"fees_category": FEE_CATEGORY,
						"amount": amount,
					}
				],
			}
		)
		fs.insert(ignore_permissions=True)


def _ensure_students_and_fees(branch, cluster, company, receivable):
	for campus_type, program in PROGRAMS.items():
		campus = f"{branch}-{campus_type}"
		amount = CAMPUS_FEE_AMOUNT[campus_type]
		fee_structure = frappe.db.get_value(
			"Fee Structure",
			{"program": program, "academic_year": ACADEMIC_YEAR, "company": company},
			"name",
		)
		if not fee_structure:
			raise RuntimeError(f"Fee Structure missing for {program}/{company}; ordering bug")

		for i in range(1, STUDENTS_PER_CAMPUS + 1):
			email = f"demo-{branch.lower()}-{campus_type.lower()}-{i:02d}@example.test"
			student = _ensure_student(email, branch, cluster, campus, i)
			enrollment = _ensure_program_enrollment(student, program)
			_ensure_submitted_fee(student, enrollment, fee_structure, company, receivable, amount)


def _ensure_student(email, branch, cluster, campus, idx):
	existing = frappe.db.get_value("Student", {"student_email_id": email}, "name")
	if existing:
		# Re-stamp MYS fields in case fixtures were re-applied
		frappe.db.set_value(
			"Student",
			existing,
			{"mys_cluster": cluster, "mys_branch": branch, "mys_campus": campus},
		)
		return existing
	s = frappe.get_doc(
		{
			"doctype": "Student",
			"first_name": f"Demo{branch}{idx:02d}",
			"last_name": campus.split("-")[-1],
			"student_email_id": email,
			"mys_cluster": cluster,
			"mys_branch": branch,
			"mys_campus": campus,
		}
	)
	s.insert(ignore_permissions=True)
	return s.name


def _ensure_program_enrollment(student, program):
	existing = frappe.db.get_value(
		"Program Enrollment",
		{"student": student, "program": program, "academic_year": ACADEMIC_YEAR, "docstatus": 1},
		"name",
	)
	if existing:
		return existing
	pe = frappe.get_doc(
		{
			"doctype": "Program Enrollment",
			"student": student,
			"program": program,
			"academic_year": ACADEMIC_YEAR,
			"academic_term": ACADEMIC_TERM,
			"enrollment_date": POSTING_DATE,
		}
	)
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


def _ensure_submitted_fee(student, enrollment, fee_structure, company, receivable, amount):
	existing = frappe.db.get_value(
		"Fees",
		{
			"student": student,
			"program_enrollment": enrollment,
			"posting_date": POSTING_DATE,
			"docstatus": 1,
		},
		"name",
	)
	if existing:
		return existing
	fee = frappe.get_doc(
		{
			"doctype": "Fees",
			"student": student,
			"program_enrollment": enrollment,
			"fee_structure": fee_structure,
			"company": company,
			"receivable_account": receivable,
			"academic_year": ACADEMIC_YEAR,
			"academic_term": ACADEMIC_TERM,
			"posting_date": POSTING_DATE,
			"due_date": DUE_DATE,
			"components": [{"fees_category": FEE_CATEGORY, "amount": amount}],
		}
	)
	fee.insert(ignore_permissions=True)
	fee.submit()
	return fee.name


def _print_summary():
	print("\nEducation seed summary (per branch, May 2026):")
	rows = frappe.db.sql(
		"""
		SELECT s.mys_branch AS branch, s.mys_campus AS campus,
		       COUNT(f.name) AS fees_count,
		       COALESCE(SUM(f.grand_total), 0) AS total
		FROM `tabStudent` s
		LEFT JOIN `tabFees` f
		  ON f.student = s.name
		 AND f.docstatus = 1
		 AND f.posting_date BETWEEN '2026-05-01' AND '2026-05-31'
		WHERE s.mys_branch IS NOT NULL
		GROUP BY s.mys_branch, s.mys_campus
		ORDER BY s.mys_branch, s.mys_campus
		""",
		as_dict=True,
	)
	for r in rows:
		print(
			f"  {r.branch}  {r.campus or '(no campus)':25s}  fees={r.fees_count:2d}  total=PKR {r.total:,.0f}"
		)
