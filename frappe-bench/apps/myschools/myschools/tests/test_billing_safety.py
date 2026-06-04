"""8a-2 — billing safety: no split-brain Fee Schedule / Sales Invoice paths."""

from __future__ import annotations

import json
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from myschools.setup.install import restrict_split_brain_billing_paths


class TestBillingSafety(FrappeTestCase):
	def test_branch_module_profile_blocks_accounts(self):
		fixture = Path(__file__).resolve().parents[1] / "fixtures" / "module_profile.json"
		profiles = json.loads(fixture.read_text())
		branch = next(p for p in profiles if p["name"] == "MYS Branch")
		blocked = {row["module"] for row in branch.get("block_modules", [])}
		self.assertIn("Accounts", blocked)
		self.assertIn("Selling", blocked)

	def test_franchise_role_cannot_create_fee_schedule(self):
		restrict_split_brain_billing_paths()
		user = "branch.dir@mys.local"
		if not frappe.db.exists("User", user):
			self.skipTest(f"{user} not on site — run seed_test_users")
		prev = frappe.session.user
		try:
			frappe.set_user(user)
			self.assertFalse(frappe.has_permission("Fee Schedule", ptype="create"))
			self.assertFalse(frappe.has_permission("Sales Invoice", ptype="create"))
		finally:
			frappe.set_user(prev)
