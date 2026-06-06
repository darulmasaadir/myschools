"""Phase 7a — portal foundations (role, Guardian.user link, www routes).

Run via:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_portal_shell
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from myschools.api.identity import link_guardian_user
from myschools.api.portal import get_portal_redirect, redirect_guest_to_login, redirect_to_portal_home
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

	def test_resolve_teacher_role(self):
		self.assertEqual(get_portal_redirect(["Teacher"]), "/teacher")

	def test_teacher_before_branch_staff(self):
		self.assertEqual(get_portal_redirect(["Teacher", "Branch Principal"]), "/teacher")

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


class TestPortalRedirectHelpers(FrappeTestCase):
	"""Direct unit coverage of /portal dispatcher logic.

	Avoid calling into the full WSGI stack here — `werkzeug.test.Client`
	leaves `frappe.session.user` set to Guest and pollutes the next
	test class's `setUpClass`. Live HTTP smoke runs in the PR battery.
	"""

	def setUp(self):
		frappe.local.flags.redirect_location = None

	def tearDown(self):
		frappe.local.flags.redirect_location = None

	def test_guest_helper_sets_login_location(self):
		with self.assertRaises(frappe.Redirect):
			redirect_guest_to_login()
		self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=/portal")

	def test_helper_throws_for_user_without_portal_role(self):
		original = frappe.session.user
		try:
			frappe.set_user("Guest")
			with self.assertRaises(frappe.PermissionError):
				redirect_to_portal_home()
		finally:
			frappe.set_user(original)
