"""Tests for the Phase 6 custom setup-wizard stage.

`get_setup_stages` is registered via the `setup_wizard_stages` hook in
`hooks.py`. It returns one Frappe stage that — given args dict POSTed
from the wizard's JS slide — optionally creates a Cluster + Branch +
Campus. Every field is optional, the stage is idempotent, and partial
input is silently dropped.

Run via:
    bench --site test_site run-tests --app myschools \
      --module myschools.tests.test_setup_wizard
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from myschools.scripts.setup_wizard import create_first_franchise_tree, get_setup_stages


def _seeded(prefix):
	return {
		"mys_cluster_code": f"{prefix}-CLR",
		"mys_cluster_name": f"{prefix} Cluster",
		"mys_cluster_region": f"{prefix} Region",
		"mys_branch_code": f"{prefix}-BR",
		"mys_branch_name": f"{prefix} Branch",
		"mys_campus_type": "Junior",
	}


class TestSetupWizardStages(FrappeTestCase):
	def test_get_setup_stages_returns_one_stage(self):
		stages = get_setup_stages({})
		self.assertEqual(len(stages), 1)
		stage = stages[0]
		self.assertIn("tasks", stage)
		self.assertEqual(len(stage["tasks"]), 1)
		self.assertIs(stage["tasks"][0]["fn"], create_first_franchise_tree)

	def test_hook_registered(self):
		# Frappe aggregates `setup_wizard_stages` across all installed apps
		# (ERPNext registers one too); we just need ours present.
		self.assertIn(
			"myschools.scripts.setup_wizard.get_setup_stages",
			frappe.get_hooks("setup_wizard_stages"),
		)
		self.assertIn(
			"/assets/myschools/js/setup_wizard.js",
			frappe.get_hooks("setup_wizard_requires"),
		)


class TestCreateFirstFranchiseTree(FrappeTestCase):
	"""End-to-end behaviour of the stage's task function."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._created = []

	def tearDown(self):
		# Tests in this class create real records; FrappeTestCase rolls
		# back at class level, so per-test cleanup keeps assertions isolated.
		for doctype, name in reversed(self._created):
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		self._created.clear()

	def _track(self, doctype, name):
		self._created.append((doctype, name))

	def test_full_args_creates_full_tree(self):
		args = _seeded("WZ1")
		create_first_franchise_tree(args)
		self._track("MYS Cluster", "WZ1-CLR")
		self._track("MYS Branch", "WZ1-BR")
		self._track("MYS Campus", "WZ1-BR-Junior")
		self.assertTrue(frappe.db.exists("MYS Cluster", "WZ1-CLR"))
		self.assertTrue(frappe.db.exists("MYS Branch", "WZ1-BR"))
		self.assertTrue(frappe.db.exists("MYS Campus", "WZ1-BR-Junior"))
		# Branch was linked to the Cluster.
		self.assertEqual(
			frappe.db.get_value("MYS Branch", "WZ1-BR", "cluster"),
			"WZ1-CLR",
		)

	def test_empty_args_is_noop(self):
		# Snapshot counts before.
		before = {
			dt: frappe.db.count(dt)
			for dt in ("MYS Cluster", "MYS Branch", "MYS Campus")
		}
		create_first_franchise_tree({})
		after = {
			dt: frappe.db.count(dt)
			for dt in ("MYS Cluster", "MYS Branch", "MYS Campus")
		}
		self.assertEqual(before, after)

	def test_partial_branch_args_skips_branch(self):
		# Cluster alone — Branch fields missing.
		args = {"mys_cluster_code": "WZ2-CLR", "mys_cluster_name": "WZ2 Cluster"}
		create_first_franchise_tree(args)
		self._track("MYS Cluster", "WZ2-CLR")
		self.assertTrue(frappe.db.exists("MYS Cluster", "WZ2-CLR"))
		# No Branch was created (we tracked none with code "WZ2-").
		self.assertFalse(
			frappe.db.exists("MYS Branch", {"cluster": "WZ2-CLR"}),
		)

	def test_idempotent_rerun(self):
		args = _seeded("WZ3")
		create_first_franchise_tree(args)
		self._track("MYS Cluster", "WZ3-CLR")
		self._track("MYS Branch", "WZ3-BR")
		self._track("MYS Campus", "WZ3-BR-Junior")
		# Second call must not raise even though everything already exists.
		create_first_franchise_tree(args)
		self.assertEqual(frappe.db.count("MYS Cluster", {"cluster_code": "WZ3-CLR"}), 1)
		self.assertEqual(frappe.db.count("MYS Branch", {"branch_code": "WZ3-BR"}), 1)

	def test_campus_without_branch_is_skipped(self):
		# Campus type set but no Branch — campus must be skipped, not error.
		# Site fixtures may already include `*-Senior` campuses, so assert
		# the count is unchanged rather than absence by type.
		before = frappe.db.count("MYS Campus")
		create_first_franchise_tree({"mys_campus_type": "Senior"})
		self.assertEqual(frappe.db.count("MYS Campus"), before)
