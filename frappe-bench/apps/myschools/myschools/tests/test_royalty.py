"""Integration tests for the royalty rate resolver and invoice generation.

Run via:
    bench --site test_site run-tests --app myschools --module myschools.tests.test_royalty
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from myschools.api.royalty import resolve_royalty_rate

CLUSTER = "_TEST_CL99"
BRANCH = "_TEST_BR99"
CAMPUS_KIDS = f"{BRANCH}-Kids"
CAMPUS_JUNIOR = f"{BRANCH}-Junior"
CAMPUS_SENIOR = f"{BRANCH}-Senior"


class TestRoyaltyResolution(FrappeTestCase):
	"""Verifies the rate-precedence rules: campus > branch > agreement default."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._build_fixture_tree()
		cls.agreement = cls._build_agreement(default_rate=7.0)

	def tearDown(self):
		# FrappeTestCase only rolls back at the class level, so we clean up
		# per-test artifacts ourselves to keep precedence tests isolated.
		frappe.db.delete("MYS Royalty Invoice Campus Line", {"parent": ["like", "MYS-RI-%"]})
		frappe.db.delete("MYS Royalty Invoice", {"branch": BRANCH})
		frappe.db.delete("MYS Royalty Rate Override", {"branch": BRANCH})
		super().tearDown()

	@classmethod
	def tearDownClass(cls):
		# Submitted agreement must be cancelled before delete.
		if frappe.db.exists("MYS Franchise Agreement", cls.agreement):
			ag = frappe.get_doc("MYS Franchise Agreement", cls.agreement)
			if ag.docstatus == 1:
				ag.cancel()
			frappe.delete_doc("MYS Franchise Agreement", cls.agreement, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Franchise Owner", "_TEST_OWNER_99"):
			frappe.delete_doc("MYS Franchise Owner", "_TEST_OWNER_99", force=True, ignore_permissions=True)
		for campus in [CAMPUS_KIDS, CAMPUS_JUNIOR, CAMPUS_SENIOR]:
			if frappe.db.exists("MYS Campus", campus):
				frappe.delete_doc("MYS Campus", campus, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Branch", BRANCH):
			frappe.delete_doc("MYS Branch", BRANCH, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.delete_doc("MYS Cluster", CLUSTER, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	@classmethod
	def _build_fixture_tree(cls):
		if not frappe.db.exists("MYS Cluster", CLUSTER):
			frappe.get_doc(
				{
					"doctype": "MYS Cluster",
					"cluster_code": CLUSTER,
					"cluster_name": "Test Cluster",
					"region": "Test Region",
				}
			).insert(ignore_permissions=True)

		if not frappe.db.exists("MYS Branch", BRANCH):
			frappe.get_doc(
				{
					"doctype": "MYS Branch",
					"branch_code": BRANCH,
					"branch_name": "Test Branch",
					"cluster": CLUSTER,
					"city": "Testville",
					"province": "Test",
					"is_active": 1,
				}
			).insert(ignore_permissions=True)

		for ctype in ["Kids", "Junior", "Senior"]:
			name = f"{BRANCH}-{ctype}"
			if not frappe.db.exists("MYS Campus", name):
				frappe.get_doc(
					{
						"doctype": "MYS Campus",
						"branch": BRANCH,
						"campus_type": ctype,
						"is_active": 1,
					}
				).insert(ignore_permissions=True)

		if not frappe.db.exists("MYS Franchise Owner", "_TEST_OWNER_99"):
			frappe.get_doc(
				{
					"doctype": "MYS Franchise Owner",
					"owner_name": "_TEST_OWNER_99",
					"status": "Active",
					"phone": "+92-300-0000000",
					"email": "test_owner@example.com",
				}
			).insert(ignore_permissions=True)

	@classmethod
	def _build_agreement(cls, default_rate: float):
		ag = frappe.get_doc(
			{
				"doctype": "MYS Franchise Agreement",
				"franchisee": frappe.db.get_value(
					"MYS Franchise Owner", {"owner_name": "_TEST_OWNER_99"}, "name"
				),
				"branch": BRANCH,
				"start_date": today(),
				"end_date": add_days(today(), 365),
				"default_royalty_rate": default_rate,
				"royalty_base": "Gross Fee Collection",
				"billing_day": 5,
				"grace_days": 10,
				"currency": "PKR",
				"status": "Draft",
			}
		).insert(ignore_permissions=True)
		ag.submit()
		return ag.name

	def _new_override(self, *, campus=None, rate, effective_from=None, effective_to=None):
		ov = frappe.get_doc(
			{
				"doctype": "MYS Royalty Rate Override",
				"agreement": self.agreement,
				"branch": BRANCH,
				"campus": campus,
				"rate_percent": rate,
				"effective_from": effective_from or today(),
				"effective_to": effective_to,
				"is_active": 1,
				"reason": "test",
			}
		).insert(ignore_permissions=True)
		return ov.name

	# --- precedence ---------------------------------------------------------

	def test_default_rate_when_no_overrides(self):
		"""With no overrides, every campus resolves to the agreement default."""
		for campus in [CAMPUS_KIDS, CAMPUS_JUNIOR, CAMPUS_SENIOR]:
			rate, source = resolve_royalty_rate(self.agreement, BRANCH, campus)
			self.assertEqual(rate, 7.0)
			self.assertEqual(source, "agreement_default")

	def test_branch_override_applies_to_all_campuses(self):
		"""A branch-level override (campus = None) covers every campus."""
		self._new_override(campus=None, rate=6.0)
		for campus in [CAMPUS_KIDS, CAMPUS_JUNIOR, CAMPUS_SENIOR]:
			rate, source = resolve_royalty_rate(self.agreement, BRANCH, campus)
			self.assertEqual(rate, 6.0)
			self.assertEqual(source, "branch_override")

	def test_campus_override_wins_over_branch_override(self):
		"""Campus override beats branch override for that campus only."""
		self._new_override(campus=None, rate=6.0)
		self._new_override(campus=CAMPUS_JUNIOR, rate=5.0)

		# Junior gets the campus override
		rate, source = resolve_royalty_rate(self.agreement, BRANCH, CAMPUS_JUNIOR)
		self.assertEqual(rate, 5.0)
		self.assertEqual(source, "campus_override")

		# Kids and Senior still use the branch override
		for campus in [CAMPUS_KIDS, CAMPUS_SENIOR]:
			rate, source = resolve_royalty_rate(self.agreement, BRANCH, campus)
			self.assertEqual(rate, 6.0)
			self.assertEqual(source, "branch_override")

	# --- effective-date gating ----------------------------------------------

	def test_future_override_does_not_apply_yet(self):
		"""An override with effective_from in the future is ignored today."""
		future = add_days(today(), 30)
		self._new_override(campus=CAMPUS_JUNIOR, rate=4.0, effective_from=future)

		# Today: still default
		rate, source = resolve_royalty_rate(self.agreement, BRANCH, CAMPUS_JUNIOR, on_date=today())
		self.assertEqual(rate, 7.0)
		self.assertEqual(source, "agreement_default")

		# 31 days out: the override is in scope
		rate, source = resolve_royalty_rate(
			self.agreement, BRANCH, CAMPUS_JUNIOR, on_date=add_days(today(), 31)
		)
		self.assertEqual(rate, 4.0)
		self.assertEqual(source, "campus_override")

	def test_expired_override_falls_through(self):
		"""An override past its effective_to date no longer applies."""
		yesterday = add_days(today(), -1)
		self._new_override(
			campus=CAMPUS_JUNIOR,
			rate=3.0,
			effective_from=add_days(today(), -10),
			effective_to=yesterday,
		)
		rate, source = resolve_royalty_rate(self.agreement, BRANCH, CAMPUS_JUNIOR, on_date=today())
		self.assertEqual(rate, 7.0)
		self.assertEqual(source, "agreement_default")

	def test_inactive_override_is_ignored(self):
		"""is_active = 0 disables an override even if dates are in scope."""
		ov_name = self._new_override(campus=CAMPUS_JUNIOR, rate=2.0)
		frappe.db.set_value("MYS Royalty Rate Override", ov_name, "is_active", 0)

		rate, source = resolve_royalty_rate(self.agreement, BRANCH, CAMPUS_JUNIOR)
		self.assertEqual(rate, 7.0)
		self.assertEqual(source, "agreement_default")

	# --- invoice computation -----------------------------------------------

	def test_invoice_computes_per_campus_royalty_correctly(self):
		"""An invoice with per-campus lines sums each line's collection x resolved rate."""
		self._new_override(campus=None, rate=6.0)
		self._new_override(campus=CAMPUS_JUNIOR, rate=5.0)

		inv = frappe.get_doc(
			{
				"doctype": "MYS Royalty Invoice",
				"agreement": self.agreement,
				"branch": BRANCH,
				"period_year": "2026",
				"period_month": "06",
				"invoice_date": today(),
				"due_date": add_days(today(), 10),
				"campus_lines": [
					{
						"campus": CAMPUS_KIDS,
						"campus_type": "Kids",
						"collection_amount": 1_000_000,
						"rate_percent": 6.0,  # branch override
						"rate_source": "branch_override",
					},
					{
						"campus": CAMPUS_JUNIOR,
						"campus_type": "Junior",
						"collection_amount": 2_000_000,
						"rate_percent": 5.0,  # campus override
						"rate_source": "campus_override",
					},
					{
						"campus": CAMPUS_SENIOR,
						"campus_type": "Senior",
						"collection_amount": 3_000_000,
						"rate_percent": 6.0,  # branch override
						"rate_source": "branch_override",
					},
				],
			}
		).insert(ignore_permissions=True)

		self.assertEqual(inv.total_collection, 6_000_000)
		# 60,000 + 100,000 + 180,000 = 340,000
		self.assertEqual(inv.royalty_amount, 340_000)
		# Weighted effective rate = 340,000 / 6,000,000 = 5.6667%
		self.assertAlmostEqual(inv.applicable_rate, 5.6667, places=4)
		# Outstanding = royalty - paid (0)
		self.assertEqual(inv.outstanding_amount, 340_000)
