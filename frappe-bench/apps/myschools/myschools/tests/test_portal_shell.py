"""Phase 7a — portal foundations (role, Guardian.user link, www routes).

Run via:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_portal_shell
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from myschools.api.identity import link_guardian_user
from myschools.api.portal import get_portal_redirect
from myschools.setup.install import create_portal_roles


class TestPortalRole(FrappeTestCase):
	def test_guardian_role_is_website_only(self):
		create_portal_roles()
		self.assertTrue(frappe.db.exists("Role", "Guardian"))
		self.assertEqual(frappe.db.get_value("Role", "Guardian", "desk_access"), 0)

	def test_guardian_user_custom_field_exists(self):
		self.assertTrue(frappe.db.exists("Custom Field", "Guardian-user"))

	def test_role_home_page_guardian(self):
		hooks = frappe.get_hooks("role_home_page") or {}
		value = hooks.get("Guardian")
		if isinstance(value, list):
			value = value[0] if value else None
		self.assertEqual(value, "guardian")


class TestPortalRouting(FrappeTestCase):
	def test_resolve_guardian_before_branch(self):
		self.assertEqual(
			get_portal_redirect(["Branch Director", "Guardian"]),
			"/guardian",
		)

	def test_resolve_inspection_roles(self):
		self.assertEqual(get_portal_redirect(["Audit Officer"]), "/inspection")

	def test_resolve_branch_roles(self):
		self.assertEqual(get_portal_redirect(["Branch Principal"]), "/branch")

	def test_unknown_roles_return_none(self):
		self.assertIsNone(get_portal_redirect(["Chief Executive"]))


class TestGuardianUserLink(FrappeTestCase):
	def test_link_guardian_user_matches_email(self):
		email = "mys-portal-guardian-link@test.local"
		user_name = frappe.db.get_value("User", {"email": email})
		if not user_name:
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Portal",
					"last_name": "Guardian",
					"send_welcome_email": 0,
					"user_type": "Website User",
				}
			)
			user.append("roles", {"role": "Guardian"})
			user.insert(ignore_permissions=True)
			user_name = user.name

		guardian = frappe.get_doc(
			{
				"doctype": "Guardian",
				"guardian_name": "Portal Link Test",
				"email_address": email,
			}
		)
		link_guardian_user(guardian)
		self.assertEqual(guardian.user, user_name)


class TestPortalHTTP(FrappeTestCase):
	def test_portal_guest_redirects_to_login(self):
		from frappe.app import application
		from werkzeug.test import Client

		client = Client(application)
		host = frappe.get_site_config().host_name or frappe.local.site
		response = client.get("/portal", headers={"Host": host})
		self.assertIn(response.status_code, (301, 302, 303))
		location = (response.headers.get("Location") or "").lower()
		self.assertIn("login", location)
