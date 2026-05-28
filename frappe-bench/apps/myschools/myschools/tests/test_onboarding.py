"""Tests for the Phase 6 MYS Module Onboarding fixtures.

Asserts that the `MYS Franchise Setup` Module Onboarding and its six
Onboarding Step fixtures import cleanly from disk, are wired to one
another in the correct order, and reference real DocTypes / paths.
"""

import frappe
from frappe.tests.utils import FrappeTestCase


EXPECTED_STEPS = [
	("MYS Add First Cluster", "Create Entry", "MYS Cluster"),
	("MYS Add First Branch", "Create Entry", "MYS Branch"),
	("MYS Add First Campus", "Create Entry", "MYS Campus"),
	("MYS Sign First Agreement", "Create Entry", "MYS Franchise Agreement"),
	("MYS Book First Inspection", "Create Entry", "MYS Inspection Visit"),
	("MYS View Central Dashboard", "Go to Page", None),
]

EXPECTED_ROLES = {
	"Chief Executive",
	"HO Dept Head",
	"Cluster Director",
	"Branch Director",
	"Branch Principal",
	"Branch Admin",
}


class TestMysFranchiseSetupOnboarding(FrappeTestCase):
	def test_module_onboarding_exists(self):
		self.assertTrue(
			frappe.db.exists("Module Onboarding", "MYS Franchise Setup"),
			"Module Onboarding 'MYS Franchise Setup' should be imported as a fixture",
		)

	def test_module_onboarding_targets_mys_module(self):
		module = frappe.db.get_value("Module Onboarding", "MYS Franchise Setup", "module")
		self.assertEqual(module, "MY School ERP")

	def test_steps_in_correct_order(self):
		mo = frappe.get_doc("Module Onboarding", "MYS Franchise Setup")
		ordered = [s.step for s in mo.steps]
		self.assertEqual(ordered, [name for name, _, _ in EXPECTED_STEPS])

	def test_each_step_exists_and_is_wired(self):
		for name, action, reference in EXPECTED_STEPS:
			with self.subTest(step=name):
				self.assertTrue(
					frappe.db.exists("Onboarding Step", name),
					f"Onboarding Step '{name}' should exist",
				)
				step = frappe.get_doc("Onboarding Step", name)
				self.assertEqual(step.action, action)
				if action == "Create Entry":
					self.assertEqual(step.reference_document, reference)
					# The DocType the step opens must exist.
					self.assertTrue(
						frappe.db.exists("DocType", reference),
						f"reference_document '{reference}' for step '{name}' must be a real DocType",
					)
				elif action == "Go to Page":
					self.assertTrue(step.path, f"step '{name}' must set a path")

	def test_dashboard_step_path_points_at_real_dashboard(self):
		path = frappe.db.get_value("Onboarding Step", "MYS View Central Dashboard", "path")
		# Path is `dashboard-view/<Dashboard name>`.
		self.assertTrue(path.startswith("dashboard-view/"))
		dashboard_name = path.split("/", 1)[1]
		self.assertTrue(
			frappe.db.exists("Dashboard", dashboard_name),
			f"Dashboard '{dashboard_name}' referenced by onboarding step must exist",
		)

	def test_franchise_roles_can_see_onboarding(self):
		roles = {
			r.role
			for r in frappe.get_doc("Module Onboarding", "MYS Franchise Setup").allow_roles
		}
		self.assertEqual(roles, EXPECTED_ROLES)
