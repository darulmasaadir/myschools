"""Phase 12 — Transport: routes, vehicles, assignments, fee billing + scoping.

Run:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_transport
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from myschools.api.transport import (
	TRANSPORT_FEE_CATEGORY,
	ensure_transport_fee_category,
	generate_transport_fee,
	get_transport_for_guardian,
	student_transport_query,
)
from myschools.setup.install import create_franchise_roles, grant_franchise_role_permissions

CLUSTER = "_TEST_12_TR_CL"
BRANCH_A = "_TEST_12_TR_BRA"
BRANCH_B = "_TEST_12_TR_BRB"


class TestTransport(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_franchise_roles()
		grant_franchise_role_permissions()
		ensure_transport_fee_category()
		cls.company = frappe.db.get_value("Company", {}, "name")
		cls.branch_a = cls._ensure_branch(BRANCH_A, with_company=True)
		cls.branch_b = cls._ensure_branch(BRANCH_B, with_company=True)
		cls.student_a = cls._ensure_student(cls.branch_a, "TR Child A", "tr-child-a@tr.test")
		cls.student_b = cls._ensure_student(cls.branch_b, "TR Child B", "tr-child-b@tr.test")
		cls.vehicle_a = cls._ensure_vehicle(cls.branch_a, "TR-BUS-A", capacity=1)
		cls.route_a = cls._ensure_route(cls.branch_a, "TR Route A", cls.vehicle_a, 4500)
		cls.route_b = cls._ensure_route(cls.branch_b, "TR Route B", None, 5000)
		cls._ensure_enrollment(cls.student_a)
		pe = frappe.db.get_value(
			"Program Enrollment",
			{"student": cls.student_a, "docstatus": 1},
			["program", "academic_year"],
			as_dict=True,
		)
		if pe:
			cls._ensure_fee_structure(cls.branch_a, pe.program, pe.academic_year)
		# Commit fixtures so per-test ``tearDown`` rollbacks revert only the rows a
		# test created, leaving the shared fixtures intact across the class.
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		for dt, filt in (
			("MYS Student Transport", {"branch": ["in", [BRANCH_A, BRANCH_B]]}),
			("MYS Transport Route", {"branch": ["in", [BRANCH_A, BRANCH_B]]}),
			("MYS Vehicle", {"branch": ["in", [BRANCH_A, BRANCH_B]]}),
		):
			for name in frappe.get_all(dt, filters=filt, pluck="name"):
				frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
		for fee in frappe.get_all("Fees", {"mys_transport_for": ["!=", ""]}, pluck="name"):
			doc = frappe.get_doc("Fees", fee)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Fees", fee, force=True, ignore_permissions=True)
		for br in (BRANCH_A, BRANCH_B):
			if frappe.db.exists("MYS Branch", br):
				frappe.delete_doc("MYS Branch", br, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.delete_doc("MYS Cluster", CLUSTER, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	# ------------------------------------------------------------------ helpers
	@classmethod
	def _ensure_branch(cls, code: str, with_company: bool = False) -> str:
		existing = frappe.db.get_value("MYS Branch", {"branch_code": code}, "name")
		if existing:
			return existing
		if not frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.get_doc(
				{"doctype": "MYS Cluster", "cluster_name": "TR Cluster", "cluster_code": CLUSTER}
			).insert(ignore_permissions=True)
		doc = {
			"doctype": "MYS Branch",
			"branch_name": f"TR Branch {code}",
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
	def _ensure_vehicle(cls, branch: str, reg: str, capacity: int) -> str:
		existing = frappe.db.get_value("MYS Vehicle", {"registration_no": reg}, "name")
		if existing:
			return existing
		return (
			frappe.get_doc(
				{
					"doctype": "MYS Vehicle",
					"registration_no": reg,
					"branch": branch,
					"capacity": capacity,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	@classmethod
	def _ensure_route(cls, branch: str, name: str, vehicle: str | None, fee: float) -> str:
		existing = frappe.db.get_value("MYS Transport Route", {"route_name": name, "branch": branch}, "name")
		if existing:
			return existing
		return (
			frappe.get_doc(
				{
					"doctype": "MYS Transport Route",
					"route_name": name,
					"branch": branch,
					"vehicle": vehicle,
					"fee_amount": fee,
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
				frappe.get_doc({"doctype": "Program", "program_name": "TR Program", "program_code": "TRP"})
				.insert(ignore_permissions=True)
				.name
			)
		year = frappe.db.get_value("Academic Year", {}, "name")
		if not year:
			year = (
				frappe.get_doc(
					{
						"doctype": "Academic Year",
						"academic_year_name": "TR Year",
						"year_start_date": "2026-01-01",
						"year_end_date": "2026-12-31",
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		pe = frappe.get_doc(
			{
				"doctype": "Program Enrollment",
				"student": student,
				"program": program,
				"academic_year": year,
				"enrollment_date": today(),
			}
		)
		pe.insert(ignore_permissions=True)
		pe.submit()
		return pe.name

	@classmethod
	def _ensure_fee_structure(cls, branch: str, program: str, year: str) -> str:
		receivable = frappe.db.get_value(
			"Account",
			{"company": cls.company, "account_type": "Receivable", "is_group": 0},
			"name",
		)
		if not receivable:
			raise RuntimeError("No receivable account for transport fee tests")
		fs = frappe.db.get_value(
			"Fee Structure",
			{"program": program, "academic_year": year, "company": cls.company},
			"name",
		)
		if fs:
			return fs
		category = frappe.db.get_value("Fee Category", {}, "name")
		if not category:
			ensure_transport_fee_category()
			category = TRANSPORT_FEE_CATEGORY
		return (
			frappe.get_doc(
				{
					"doctype": "Fee Structure",
					"program": program,
					"academic_year": year,
					"company": cls.company,
					"receivable_account": receivable,
					"components": [{"fees_category": category, "amount": 1000}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _new_assignment(self, student: str, route: str, status: str = "Active"):
		return frappe.get_doc(
			{
				"doctype": "MYS Student Transport",
				"student": student,
				"route": route,
				"status": status,
			}
		)

	def tearDown(self):
		frappe.db.rollback()

	# ------------------------------------------------------------------- tests
	def test_fee_amount_defaults_from_route(self):
		st = self._new_assignment(self.student_a, self.route_a)
		st.insert(ignore_permissions=True)
		self.assertEqual(st.branch, self.branch_a)
		self.assertEqual(st.fee_amount, 4500)

	def test_branch_consistency_enforced(self):
		# student_a is on branch_a; route_b serves branch_b → reject
		st = self._new_assignment(self.student_a, self.route_b)
		with self.assertRaises(frappe.ValidationError):
			st.insert(ignore_permissions=True)

	def test_capacity_enforced(self):
		# vehicle_a capacity == 1; first active rider OK, second rejected
		first = self._new_assignment(self.student_a, self.route_a)
		first.insert(ignore_permissions=True)
		# student_b is branch_b, route_a is branch_a — branch check would fire
		# first, so move student_b onto branch_a for a clean capacity test.
		frappe.db.set_value("Student", self.student_b, "mys_branch", self.branch_a)
		second = self._new_assignment(self.student_b, self.route_a)
		with self.assertRaises(frappe.ValidationError):
			second.insert(ignore_permissions=True)

	def test_transport_fee_generation_and_idempotency(self):
		st = self._new_assignment(self.student_a, self.route_a)
		st.insert(ignore_permissions=True)
		posting = today()
		result = generate_transport_fee(st.name, posting)
		self.assertEqual(result["status"], "created")
		fee = frappe.get_doc("Fees", result["fees"])
		self.assertEqual(fee.docstatus, 1)
		self.assertEqual(fee.student, self.student_a)
		self.assertEqual(fee.mys_transport_for, st.name)
		self.assertEqual(int(fee.grand_total), 4500)
		categories = {c.fees_category for c in fee.components}
		self.assertIn(TRANSPORT_FEE_CATEGORY, categories)
		# Second run for the same posting date is a no-op skip.
		again = generate_transport_fee(st.name, posting)
		self.assertEqual(again["status"], "skipped")

	def test_stopped_assignment_not_billed(self):
		st = self._new_assignment(self.student_a, self.route_a, status="Stopped")
		st.insert(ignore_permissions=True)
		result = generate_transport_fee(st.name, today())
		self.assertEqual(result["status"], "skipped")

	def test_student_transport_query_scopes_branch_user(self):
		director = "tr-director@test.local"
		if not frappe.db.exists("User", director):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": director,
					"first_name": "TR Director",
					"send_welcome_email": 0,
				}
			)
			user.insert(ignore_permissions=True)
			user.add_roles("Branch Director")
		emp = frappe.db.get_value("Employee", {"user_id": director}, "name")
		if not emp:
			frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": "TR Director",
					"gender": "Male",
					"date_of_birth": "1985-01-01",
					"date_of_joining": today(),
					"company": self.company,
					"mys_branch": self.branch_a,
					"user_id": director,
				}
			).insert(ignore_permissions=True)

		cond = student_transport_query(director)
		self.assertIn(self.branch_a, cond)
		self.assertNotIn("__none__", cond)

		a = self._new_assignment(self.student_a, self.route_a)
		a.insert(ignore_permissions=True)
		frappe.db.set_value("Student", self.student_b, "mys_branch", self.branch_b)
		b = self._new_assignment(self.student_b, self.route_b)
		b.insert(ignore_permissions=True)

		prev = frappe.session.user
		try:
			frappe.set_user(director)
			visible = set(frappe.get_list("MYS Student Transport", pluck="name", limit_page_length=500))
			self.assertIn(a.name, visible)
			self.assertNotIn(b.name, visible)
		finally:
			frappe.set_user(prev)

	def test_get_transport_for_guardian(self):
		st = self._new_assignment(self.student_a, self.route_a)
		st.insert(ignore_permissions=True)
		guardian = self._ensure_guardian(self.student_a)
		rows = get_transport_for_guardian(guardian)
		names = {r["name"] for r in rows}
		self.assertIn(st.name, names)
		row = next(r for r in rows if r["name"] == st.name)
		self.assertEqual(row["route_name"], "TR Route A")

	@classmethod
	def _ensure_guardian(cls, student: str):
		email = "tr-guardian@tr.test"
		name = frappe.db.get_value("Guardian", {"email_address": email}, "name")
		if not name:
			name = (
				frappe.get_doc(
					{
						"doctype": "Guardian",
						"guardian_name": "TR Guardian",
						"email_address": email,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		stu = frappe.get_doc("Student", student)
		linked = {row.guardian for row in stu.get("guardians") or []}
		if name not in linked:
			stu.append("guardians", {"guardian": name, "relation": "Father"})
			stu.save(ignore_permissions=True)
		return frappe.get_doc("Guardian", name)
