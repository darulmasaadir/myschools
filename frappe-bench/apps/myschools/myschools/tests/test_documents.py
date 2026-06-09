"""Phase 14 — Document registry: branch scoping + expiry status.

Run:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_documents
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from myschools.api.documents import (
	document_query,
	documents_expiring_within,
	refresh_document_expiry_status,
	scheduled_mark_documents_expired,
)
from myschools.setup.install import create_franchise_roles, grant_franchise_role_permissions

CLUSTER = "_TEST_14_DOC_CL"
BRANCH_A = "_TEST_14_DOC_BRA"
BRANCH_B = "_TEST_14_DOC_BRB"


class TestDocuments(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_franchise_roles()
		grant_franchise_role_permissions()
		cls.branch_a = cls._ensure_branch(BRANCH_A)
		cls.branch_b = cls._ensure_branch(BRANCH_B)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		for name in frappe.get_all(
			"MYS Document", filters={"branch": ["in", [BRANCH_A, BRANCH_B]]}, pluck="name"
		):
			frappe.delete_doc("MYS Document", name, force=True, ignore_permissions=True)
		for br in (BRANCH_A, BRANCH_B):
			if frappe.db.exists("MYS Branch", br):
				frappe.delete_doc("MYS Branch", br, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.delete_doc("MYS Cluster", CLUSTER, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	@classmethod
	def _ensure_branch(cls, code: str) -> str:
		existing = frappe.db.get_value("MYS Branch", {"branch_code": code}, "name")
		if existing:
			return existing
		if not frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.get_doc(
				{"doctype": "MYS Cluster", "cluster_name": "DOC Cluster", "cluster_code": CLUSTER}
			).insert(ignore_permissions=True)
		return (
			frappe.get_doc(
				{
					"doctype": "MYS Branch",
					"branch_name": f"DOC Branch {code}",
					"branch_code": code,
					"cluster": CLUSTER,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _new_document(self, branch: str, title: str, expiry: str | None = None):
		return frappe.get_doc(
			{
				"doctype": "MYS Document",
				"title": title,
				"branch": branch,
				"category": "Compliance",
				"expiry_date": expiry,
				"status": "Active",
			}
		)

	def test_expired_date_promotes_status_on_save(self):
		doc = self._new_document(self.branch_a, "Expired Cert", expiry=add_days(today(), -1))
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.status, "Expired")

	def test_scheduled_mark_documents_expired(self):
		doc = self._new_document(self.branch_a, "Scheduler Cert", expiry=add_days(today(), -2))
		doc.insert(ignore_permissions=True)
		frappe.db.set_value("MYS Document", doc.name, "status", "Active", update_modified=False)
		scheduled_mark_documents_expired()
		self.assertEqual(frappe.db.get_value("MYS Document", doc.name, "status"), "Expired")

	def test_documents_expiring_within_window(self):
		doc = self._new_document(self.branch_a, "Soon Cert", expiry=add_days(today(), 5))
		doc.insert(ignore_permissions=True)
		rows = documents_expiring_within(7, branch=self.branch_a)
		self.assertTrue(any(r["name"] == doc.name for r in rows))

	def test_refresh_skips_archived(self):
		doc = self._new_document(self.branch_a, "Archived Cert", expiry=add_days(today(), -1))
		doc.status = "Archived"
		refresh_document_expiry_status(doc)
		self.assertEqual(doc.status, "Archived")

	def test_document_query_scopes_branch_user(self):
		director = "doc-director@test.local"
		if not frappe.db.exists("User", director):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": director,
					"first_name": "DOC Director",
					"send_welcome_email": 0,
				}
			)
			user.insert(ignore_permissions=True)
			user.add_roles("Branch Director")
		company = frappe.db.get_value("Company", {}, "name")
		if not frappe.db.get_value("Employee", {"user_id": director}, "name"):
			frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": "DOC Director",
					"gender": "Male",
					"date_of_birth": "1985-01-01",
					"date_of_joining": today(),
					"company": company,
					"mys_branch": self.branch_a,
					"user_id": director,
				}
			).insert(ignore_permissions=True)

		cond = document_query(director)
		self.assertIn(self.branch_a, cond)
		self.assertNotIn("__none__", cond)

		a = self._new_document(self.branch_a, "Scope A")
		a.insert(ignore_permissions=True)
		b = self._new_document(self.branch_b, "Scope B")
		b.insert(ignore_permissions=True)

		prev = frappe.session.user
		try:
			frappe.set_user(director)
			visible = set(frappe.get_list("MYS Document", pluck="name", limit_page_length=500))
			self.assertIn(a.name, visible)
			self.assertNotIn(b.name, visible)
		finally:
			frappe.set_user(prev)
