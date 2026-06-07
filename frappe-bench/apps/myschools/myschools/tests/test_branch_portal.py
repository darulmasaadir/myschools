"""Phase 7c — Branch portal (dashboard, findings, royalty, fees).

Run via:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_branch_portal
"""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from myschools.api.branch_portal import (
	get_branch_for_user,
	get_fees_summary,
	get_findings_for_branch,
	get_findings_summary,
	get_royalty_for_branch,
	get_royalty_summary,
	populate_branch_context,
	require_branch_role,
)


class TestBranchPortalAccess(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.email = "mys-portal-7c-director@test.local"
		cls.branch = cls._ensure_branch()
		cls._ensure_user_and_employee()

	@classmethod
	def _ensure_branch(cls) -> str:
		branch = frappe.db.get_value("MYS Branch", {}, "name")
		if branch:
			return branch
		cluster = frappe.get_doc(
			{"doctype": "MYS Cluster", "cluster_name": "Portal 7c", "cluster_code": "P7C"}
		).insert(ignore_permissions=True)
		return (
			frappe.get_doc(
				{
					"doctype": "MYS Branch",
					"branch_name": "Portal 7c Branch",
					"branch_code": "P7CB",
					"cluster": cluster.name,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	@classmethod
	def _ensure_user_and_employee(cls):
		if not frappe.db.exists("User", cls.email):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": cls.email,
					"first_name": "Portal",
					"last_name": "Director",
					"send_welcome_email": 0,
					"user_type": "System User",
				}
			)
			user.append("roles", {"role": "Branch Director"})
			user.insert(ignore_permissions=True)
		emp = frappe.db.get_value("Employee", {"user_id": cls.email}, "name")
		if not emp:
			company = frappe.db.get_value("MYS Branch", cls.branch, "company") or frappe.db.get_value(
				"Company", {}, "name"
			)
			frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": "Portal",
					"last_name": "Director",
					"gender": "Male",
					"date_of_birth": "1985-01-01",
					"date_of_joining": today(),
					"status": "Active",
					"company": company,
					"user_id": cls.email,
					"mys_branch": cls.branch,
				}
			).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Employee", emp, {"mys_branch": cls.branch, "status": "Active"})

	def test_branch_resolution(self):
		frappe.set_user(self.email)
		try:
			self.assertEqual(get_branch_for_user(), self.branch)
		finally:
			frappe.set_user("Administrator")

	def test_require_branch_role_throws_for_other_user(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises((frappe.Redirect, frappe.PermissionError)):
				require_branch_role()
		finally:
			frappe.set_user("Administrator")

	def test_populate_branch_context_populates_nav(self):
		frappe.set_user(self.email)
		try:
			context = frappe._dict()
			branch = populate_branch_context(context)
			self.assertEqual(branch, self.branch)
			routes = {n["route"] for n in context.nav_items}
			self.assertEqual(
				routes,
				{
					"/branch",
					"/branch/findings",
					"/branch/royalty",
					"/branch/fees",
					"/branch/timetable",
				},
			)
		finally:
			frappe.set_user("Administrator")

	def test_findings_summary_isolates_branch(self):
		visit = frappe.get_doc(
			{
				"doctype": "MYS Inspection Visit",
				"branch": self.branch,
				"visit_date": today(),
				"visit_type": "Routine",
				"inspector": frappe.db.get_value("Employee", {"user_id": self.email}, "name"),
			}
		)
		visit.insert(ignore_permissions=True)
		visit.submit()
		finding = frappe.get_doc(
			{
				"doctype": "MYS Inspection Finding",
				"visit": visit.name,
				"branch": self.branch,
				"severity": "Major",
				"category": "Safety",
				"status": "Draft",
				"description": "phase-7c test finding",
				"due_date": add_days(today(), -7),
				"reported_by": "Administrator",
				"reported_on": today(),
			}
		)
		finding.insert(ignore_permissions=True)
		apply_workflow(finding, "Submit")

		rows = get_findings_for_branch(self.branch)
		self.assertTrue(any(r.name == finding.name for r in rows))
		summary = get_findings_summary(self.branch)
		self.assertGreaterEqual(summary["open_total"], 1)
		self.assertGreaterEqual(summary["overdue_total"], 1)
		self.assertGreaterEqual(summary["by_severity"]["Major"], 1)

	def test_royalty_and_fees_smoke(self):
		royalty = get_royalty_summary(self.branch)
		self.assertIn("outstanding", royalty)
		self.assertIn("overdue", royalty)
		invoices = get_royalty_for_branch(self.branch)
		self.assertIsInstance(invoices, list)
		fees = get_fees_summary(self.branch)
		self.assertIn("collected_mtd", fees)
		self.assertIn("outstanding_total", fees)
