"""Phase 7d — Inspection portal + admission enquiry.

Run:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_inspection_portal
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from myschools.api.inspection_portal import (
	apply_template,
	get_allowed_branches,
	get_dashboard_summary,
	populate_inspection_context,
	require_inspection_role,
	save_checklist,
	submit_admission_enquiry,
	submit_visit,
)


class TestInspectionPortalAccess(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.email = "mys-portal-7d-monitor@test.local"
		cls.branch = cls._ensure_branch()
		cls._ensure_user_and_employee()
		cls.template = cls._ensure_template()

	@classmethod
	def _ensure_branch(cls) -> str:
		branch = frappe.db.get_value("MYS Branch", {}, "name")
		if branch:
			return branch
		cluster = frappe.get_doc(
			{"doctype": "MYS Cluster", "cluster_name": "Portal 7d", "cluster_code": "P7D"}
		).insert(ignore_permissions=True)
		return (
			frappe.get_doc(
				{
					"doctype": "MYS Branch",
					"branch_name": "Portal 7d Branch",
					"branch_code": "P7DB",
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
					"last_name": "Monitor",
					"send_welcome_email": 0,
					"user_type": "System User",
				}
			)
			user.append("roles", {"role": "Academic Monitor"})
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
					"last_name": "Monitor",
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

	@classmethod
	def _ensure_template(cls) -> str:
		name = frappe.db.get_value("MYS Inspection Checklist Template", {"is_active": 1}, "name")
		if name:
			return name
		doc = frappe.get_doc(
			{
				"doctype": "MYS Inspection Checklist Template",
				"template_name": "Portal 7d Smoke",
				"visit_type": "Routine",
				"version": 1,
				"is_active": 1,
				"items": [
					{
						"item_text": "Fire extinguisher accessible",
						"category": "Safety",
						"severity": "Critical",
						"weight": 1,
						"max_score": 1,
					},
					{
						"item_text": "Classrooms clean",
						"category": "Cleanliness",
						"severity": "Minor",
						"weight": 1,
						"max_score": 1,
					},
				],
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def test_allowed_branches_cluster_scoped(self):
		frappe.set_user(self.email)
		branches = get_allowed_branches()
		self.assertIn(self.branch, branches)

	def test_dashboard_summary(self):
		frappe.set_user(self.email)
		summary = get_dashboard_summary(get_allowed_branches())
		self.assertIn("open_findings", summary)
		self.assertIn("recent_visits", summary)

	def test_checklist_apply_save_submit(self):
		frappe.set_user(self.email)
		inspector = frappe.db.get_value("Employee", {"user_id": self.email}, "name")
		visit = frappe.get_doc(
			{
				"doctype": "MYS Inspection Visit",
				"branch": self.branch,
				"visit_type": "Routine",
				"visit_date": today(),
				"inspector": inspector,
			}
		).insert(ignore_permissions=True)
		apply_template(visit.name, self.template)
		visit.reload()
		self.assertEqual(len(visit.checklist_results), 2)
		rows = [
			{"idx": 0, "result": "Pass", "notes": ""},
			{"idx": 1, "result": "N/A", "notes": ""},
		]
		save_checklist(visit.name, json.dumps(rows))
		submit_visit(visit.name)
		visit.reload()
		self.assertEqual(visit.docstatus, 1)

	def test_admission_enquiry_guest(self):
		frappe.set_user("Guest")
		try:
			out = submit_admission_enquiry(
				branch=self.branch,
				parent_name="Test Parent",
				phone="03001234567",
				message="Interested in admission",
			)
			self.assertTrue(out.get("ok"))
			log = frappe.get_doc("MYS Communication Log", out["name"])
			self.assertIn("Test Parent", log.body)
			self.assertEqual(log.branch, self.branch)
		finally:
			frappe.set_user("Administrator")

	def test_populate_context(self):
		frappe.set_user(self.email)
		ctx = frappe._dict()
		populate_inspection_context(ctx)
		self.assertEqual(ctx.nav_items[0]["route"], "/inspection")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_branch_director_denied(self):
		email = "mys-portal-7d-denied@test.local"
		if not frappe.db.exists("User", email):
			u = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Denied",
					"send_welcome_email": 0,
					"user_type": "System User",
				}
			)
			u.append("roles", {"role": "Branch Director"})
			u.insert(ignore_permissions=True)
		frappe.set_user(email)
		self.assertRaises(frappe.PermissionError, require_inspection_role)
