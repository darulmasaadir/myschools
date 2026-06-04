"""Phase 8b — student transfer, leaving, enrollment guards."""

from __future__ import annotations

from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from myschools.api.student_lifecycle import (
	generate_leaving_certificate_number,
	validate_program_enrollment,
)

CLUSTER = "_TEST_SL_CL"
BRANCH = "SLBR1"
BRANCH2 = "SLBR2"
CAMPUS_KIDS = f"{BRANCH}-Kids"
CAMPUS_JUNIOR = f"{BRANCH}-Junior"
CAMPUS2 = f"{BRANCH2}-Kids"
ACADEMIC_YEAR = "_TEST_SL_AY"
ACADEMIC_TERM_NAME = "_TEST_SL_TERM"
ACADEMIC_TERM = f"{ACADEMIC_YEAR} ({ACADEMIC_TERM_NAME})"
PROGRAM = "_TEST_SL_PROG"


class TestStudentLifecycle(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._build_tree()
		cls._build_education()
		cls.student = cls._ensure_student(CAMPUS_KIDS)
		cls.enrollment = cls._ensure_enrollment(cls.student)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		for name in frappe.get_all("MYS Student Leaving", {"branch": ["in", [BRANCH, BRANCH2]]}, pluck="name"):
			doc = frappe.get_doc("MYS Student Leaving", name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("MYS Student Leaving", name, force=True, ignore_permissions=True)
		for name in frappe.get_all("MYS Student Transfer", pluck="name"):
			if frappe.db.get_value("MYS Student Transfer", name, "student") == cls.student:
				doc = frappe.get_doc("MYS Student Transfer", name)
				if doc.docstatus == 1:
					doc.cancel()
				frappe.delete_doc("MYS Student Transfer", name, force=True, ignore_permissions=True)
		if cls.enrollment and frappe.db.exists("Program Enrollment", cls.enrollment):
			pe = frappe.get_doc("Program Enrollment", cls.enrollment)
			if pe.docstatus == 1:
				pe.cancel()
			frappe.delete_doc("Program Enrollment", cls.enrollment, force=True, ignore_permissions=True)
		if cls.student and frappe.db.exists("Student", cls.student):
			frappe.delete_doc("Student", cls.student, force=True, ignore_permissions=True)
		for br in (BRANCH, BRANCH2):
			if frappe.db.exists("MYS Campus", f"{br}-Kids"):
				frappe.delete_doc("MYS Campus", f"{br}-Kids", force=True, ignore_permissions=True)
			if frappe.db.exists("MYS Campus", f"{br}-Junior"):
				frappe.delete_doc("MYS Campus", f"{br}-Junior", force=True, ignore_permissions=True)
			if frappe.db.exists("MYS Branch", br):
				frappe.delete_doc("MYS Branch", br, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.delete_doc("MYS Cluster", CLUSTER, force=True, ignore_permissions=True)
		if frappe.db.exists("Program", PROGRAM):
			frappe.delete_doc("Program", PROGRAM, force=True, ignore_permissions=True)
		if frappe.db.exists("Academic Term", ACADEMIC_TERM):
			frappe.delete_doc("Academic Term", ACADEMIC_TERM, force=True, ignore_permissions=True)
		if frappe.db.exists("Academic Year", ACADEMIC_YEAR):
			frappe.delete_doc("Academic Year", ACADEMIC_YEAR, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	@classmethod
	def _build_tree(cls):
		company = frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.get_doc(
				{"doctype": "MYS Cluster", "cluster_code": CLUSTER, "cluster_name": CLUSTER, "is_active": 1}
			).insert(ignore_permissions=True)
		for br, code in ((BRANCH, BRANCH), (BRANCH2, BRANCH2)):
			if not frappe.db.exists("MYS Branch", br):
				frappe.get_doc(
					{
						"doctype": "MYS Branch",
						"branch_code": code,
						"branch_name": f"Test {code}",
						"cluster": CLUSTER,
						"company": company,
						"is_active": 1,
					}
				).insert(ignore_permissions=True)
		for campus in (CAMPUS_KIDS, CAMPUS_JUNIOR, CAMPUS2):
			if not frappe.db.exists("MYS Campus", campus):
				branch = BRANCH if campus.startswith(BRANCH) else BRANCH2
				campus_type = campus.split("-")[-1]
				frappe.get_doc(
					{
						"doctype": "MYS Campus",
						"campus_type": campus_type,
						"branch": branch,
						"is_active": 1,
					}
				).insert(ignore_permissions=True)

	@classmethod
	def _build_education(cls):
		if not frappe.db.exists("Academic Year", ACADEMIC_YEAR):
			frappe.get_doc(
				{
					"doctype": "Academic Year",
					"academic_year_name": ACADEMIC_YEAR,
					"year_start_date": date(2025, 8, 1),
					"year_end_date": date(2026, 7, 31),
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Academic Term", ACADEMIC_TERM):
			frappe.get_doc(
				{
					"doctype": "Academic Term",
					"academic_year": ACADEMIC_YEAR,
					"term_name": ACADEMIC_TERM_NAME,
					"term_start_date": date(2025, 9, 1),
					"term_end_date": date(2025, 12, 31),
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Program", PROGRAM):
			frappe.get_doc(
				{
					"doctype": "Program",
					"program_name": PROGRAM,
					"program_code": PROGRAM,
				}
			).insert(ignore_permissions=True)

	@classmethod
	def _ensure_student(cls, campus: str) -> str:
		email = "sl-test-student@example.test"
		existing = frappe.db.get_value("Student", {"student_email_id": email}, "name")
		if existing:
			frappe.db.set_value(
				"Student",
				existing,
				{"mys_cluster": CLUSTER, "mys_branch": BRANCH, "mys_campus": campus, "enabled": 1},
			)
			return existing
		doc = frappe.get_doc(
			{
				"doctype": "Student",
				"first_name": "SL",
				"last_name": "Test",
				"student_email_id": email,
				"mys_cluster": CLUSTER,
				"mys_branch": BRANCH,
				"mys_campus": campus,
				"enabled": 1,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	@classmethod
	def _ensure_enrollment(cls, student: str) -> str:
		existing = frappe.db.get_value(
			"Program Enrollment",
			{"student": student, "program": PROGRAM, "academic_year": ACADEMIC_YEAR, "docstatus": 1},
			"name",
		)
		if existing:
			return existing
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
		return pe.name

	def test_campus_transfer_updates_student(self):
		tr = frappe.get_doc(
			{
				"doctype": "MYS Student Transfer",
				"student": self.student,
				"to_branch": BRANCH,
				"to_campus": CAMPUS_JUNIOR,
				"transfer_date": today(),
				"reason": "Campus promotion",
			}
		)
		tr.insert(ignore_permissions=True)
		tr.submit()
		self.assertEqual(frappe.db.get_value("Student", self.student, "mys_campus"), CAMPUS_JUNIOR)

	def test_inter_branch_transfer_updates_cluster(self):
		tr = frappe.get_doc(
			{
				"doctype": "MYS Student Transfer",
				"student": self.student,
				"to_branch": BRANCH2,
				"to_campus": CAMPUS2,
				"transfer_date": today(),
				"reason": "Family relocation",
			}
		)
		tr.insert(ignore_permissions=True)
		tr.submit()
		self.assertEqual(frappe.db.get_value("Student", self.student, "mys_branch"), BRANCH2)
		self.assertEqual(frappe.db.get_value("Student", self.student, "mys_campus"), CAMPUS2)

	def test_program_enrollment_blocked_for_inactive_student(self):
		frappe.db.set_value("Student", self.student, "enabled", 0)
		pe = frappe.get_doc(
			{
				"doctype": "Program Enrollment",
				"student": self.student,
				"program": PROGRAM,
				"academic_year": ACADEMIC_YEAR,
				"academic_term": ACADEMIC_TERM,
				"enrollment_date": today(),
			}
		)
		with self.assertRaises(frappe.ValidationError):
			validate_program_enrollment(pe)
		frappe.db.set_value("Student", self.student, "enabled", 1)

	def test_program_enrollment_blocked_without_mys_branch(self):
		frappe.db.set_value("Student", self.student, "mys_branch", None)
		pe = frappe.get_doc(
			{
				"doctype": "Program Enrollment",
				"student": self.student,
				"program": PROGRAM,
				"academic_year": ACADEMIC_YEAR,
				"academic_term": ACADEMIC_TERM,
				"enrollment_date": today(),
			}
		)
		with self.assertRaises(frappe.ValidationError):
			validate_program_enrollment(pe)
		frappe.db.set_value("Student", self.student, "mys_branch", BRANCH)

	def test_leaving_certificate_numbers_are_unique(self):
		branch = frappe.db.get_value("Student", self.student, "mys_branch")
		n1 = generate_leaving_certificate_number(branch)
		doc = frappe.get_doc(
			{
				"doctype": "MYS Student Leaving",
				"student": self.student,
				"leaving_date": today(),
				"reason_for_leaving": "Test",
				"certificate_number": n1,
			}
		)
		doc.insert(ignore_permissions=True)
		n2 = generate_leaving_certificate_number(branch)
		self.assertNotEqual(n1, n2)

	def test_leaving_certificate_print_renders(self):
		from frappe.utils.jinja import render_template

		leaving = frappe.get_doc(
			{
				"doctype": "MYS Student Leaving",
				"student": self.student,
				"leaving_date": today(),
				"reason_for_leaving": "Transfer abroad",
				"certificate_number": generate_leaving_certificate_number(
					frappe.db.get_value("Student", self.student, "mys_branch")
				),
			}
		)
		pf = frappe.get_doc("Print Format", "MYS Leaving Certificate")
		html = render_template(pf.html, {"doc": leaving, "letter_head": "", "no_letterhead": 1})
		self.assertNotIn("{{", html)
		self.assertIn(leaving.certificate_number, html)
		self.assertIn("SCHOOL LEAVING CERTIFICATE", html)

	def test_leaving_disables_student_and_cancels_enrollment(self):
		leaving = frappe.get_doc(
			{
				"doctype": "MYS Student Leaving",
				"student": self.student,
				"leaving_date": today(),
				"reason_for_leaving": "Graduated",
			}
		)
		leaving.insert(ignore_permissions=True)
		self.assertTrue(leaving.certificate_number)
		leaving.submit()
		self.assertEqual(frappe.db.get_value("Student", self.student, "enabled"), 0)
		self.assertEqual(
			frappe.db.get_value("Student", self.student, "leaving_certificate_number"),
			leaving.certificate_number,
		)
		self.assertEqual(frappe.db.get_value("Program Enrollment", self.enrollment, "docstatus"), 2)
