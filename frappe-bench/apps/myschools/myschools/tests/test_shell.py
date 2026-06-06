"""Tests for the MY School ERP shell — branding, workspaces, role landing pages,
and the Module Profile auto-attach behavior.

Verifies that the Phase 1+2 fixtures imported cleanly on `bench migrate` and
that creating a User with a franchise role automatically attaches the right
Module Profile via the `attach_module_profile_to_user` doc_event hook.

Run via:
    bench --site test_site run-tests --app myschools --module myschools.tests.test_shell
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from myschools.api.user_profile import resolve_profile_for_roles, resolve_workspace_for_roles

EXPECTED_WORKSPACES = [
	"mys-head-office",
	"mys-cluster",
	"mys-branch",
	"mys-campus",
	"mys-inspection",
]

EXPECTED_MODULE_PROFILES = [
	"MYS HO",
	"MYS Cluster",
	"MYS Branch",
	"MYS Campus",
	"MYS Inspection",
]

EXPECTED_ROLE_HOMES = {
	"Chief Executive": "mys-head-office",
	"HO Dept Head": "mys-head-office",
	"Cluster Director": "mys-cluster",
	"Academic Monitor": "mys-inspection",
	"Audit Officer": "mys-inspection",
	"Branch Director": "mys-branch",
	"Branch Principal": "mys-branch",
	"Branch Admin": "mys-branch",
	"Branch Accountant": "mys-branch",
	"Campus Incharge": "mys-campus",
	"Teacher": "teacher",
}


class TestWorkspaceFixtures(FrappeTestCase):
	def test_all_workspaces_imported(self):
		for name in EXPECTED_WORKSPACES:
			self.assertTrue(frappe.db.exists("Workspace", name), msg=name)

	def test_workspaces_restricted_to_correct_roles(self):
		expected_roles = {
			"mys-head-office": {"Chief Executive", "HO Dept Head"},
			"mys-cluster": {"Cluster Director"},
			"mys-branch": {
				"Branch Director",
				"Branch Principal",
				"Branch Admin",
				"Branch Accountant",
			},
			"mys-campus": {"Campus Incharge"},
			"mys-inspection": {"Academic Monitor", "Audit Officer"},
		}
		for ws_name, roles in expected_roles.items():
			doc = frappe.get_doc("Workspace", ws_name)
			actual = {r.role for r in doc.roles}
			self.assertEqual(actual, roles, msg=ws_name)


class TestLetterHead(FrappeTestCase):
	def test_default_letter_head_exists(self):
		self.assertTrue(frappe.db.exists("Letter Head", "MYS Default"))

	def test_default_letter_head_is_marked_default(self):
		self.assertEqual(frappe.db.get_value("Letter Head", "MYS Default", "is_default"), 1)


class TestModuleProfiles(FrappeTestCase):
	def test_all_profiles_imported(self):
		for name in EXPECTED_MODULE_PROFILES:
			self.assertTrue(frappe.db.exists("Module Profile", name), msg=name)

	def test_profiles_have_block_modules(self):
		for name in EXPECTED_MODULE_PROFILES:
			doc = frappe.get_doc("Module Profile", name)
			self.assertGreater(len(doc.block_modules), 0, msg=name)


class TestRoleHomePage(FrappeTestCase):
	def test_role_home_page_hook_complete(self):
		hooks = frappe.get_hooks("role_home_page") or {}
		for role, expected in EXPECTED_ROLE_HOMES.items():
			value = hooks.get(role)
			if isinstance(value, list):
				value = value[0] if value else None
			self.assertEqual(value, expected, msg=role)


class TestTierResolvers(FrappeTestCase):
	def test_profile_resolver_picks_highest_tier(self):
		self.assertEqual(resolve_profile_for_roles({"Chief Executive"}), "MYS HO")
		self.assertEqual(resolve_profile_for_roles({"Cluster Director"}), "MYS Cluster")
		self.assertEqual(resolve_profile_for_roles({"Branch Admin"}), "MYS Branch")
		self.assertEqual(resolve_profile_for_roles({"Campus Incharge"}), "MYS Campus")
		self.assertEqual(resolve_profile_for_roles({"Audit Officer"}), "MYS Inspection")

	def test_workspace_resolver_picks_highest_tier(self):
		self.assertEqual(resolve_workspace_for_roles({"Chief Executive"}), "mys-head-office")
		self.assertEqual(resolve_workspace_for_roles({"Cluster Director"}), "mys-cluster")
		self.assertEqual(resolve_workspace_for_roles({"Branch Admin"}), "mys-branch")
		self.assertEqual(resolve_workspace_for_roles({"Campus Incharge"}), "mys-campus")
		self.assertEqual(resolve_workspace_for_roles({"Audit Officer"}), "mys-inspection")

	def test_resolvers_prefer_higher_tier_when_multiple(self):
		# A user with both Branch Admin and Cluster Director gets Cluster.
		self.assertEqual(
			resolve_profile_for_roles({"Branch Admin", "Cluster Director"}),
			"MYS Cluster",
		)
		self.assertEqual(
			resolve_workspace_for_roles({"Branch Admin", "Cluster Director"}),
			"mys-cluster",
		)

	def test_resolvers_return_none_for_no_franchise_role(self):
		self.assertIsNone(resolve_profile_for_roles({"System Manager"}))
		self.assertIsNone(resolve_workspace_for_roles({"System Manager"}))
		self.assertIsNone(resolve_profile_for_roles(set()))


class TestUserAutoAttach(FrappeTestCase):
	"""Creating a User with a franchise role should auto-attach the Module Profile
	via the `User.after_insert` doc_event."""

	TEST_EMAIL = "shell-test-branch-admin@myschools.test"

	def setUp(self):
		# Ensure clean slate — each test creates and tears down its own user.
		if frappe.db.exists("User", self.TEST_EMAIL):
			frappe.delete_doc("User", self.TEST_EMAIL, force=True, ignore_permissions=True)

	def tearDown(self):
		if frappe.db.exists("User", self.TEST_EMAIL):
			frappe.delete_doc("User", self.TEST_EMAIL, force=True, ignore_permissions=True)

	def test_branch_admin_gets_branch_profile_and_workspace(self):
		user = frappe.new_doc("User")
		user.email = self.TEST_EMAIL
		user.first_name = "Shell"
		user.last_name = "Test"
		user.send_welcome_email = 0
		user.append("roles", {"role": "Branch Admin"})
		user.insert(ignore_permissions=True)

		user.reload()
		self.assertEqual(user.module_profile, "MYS Branch")
		self.assertEqual(user.default_workspace, "mys-branch")
