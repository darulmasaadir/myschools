"""Tests for the MYS Central Monitoring Dashboard.

Verifies that the JSON-shipped Number Cards, Dashboard Charts, and Dashboard
all imported on `bench migrate`, and that the three whitelisted Number Card
endpoints in `myschools.api.dashboard` return well-formed payloads.

Run via:
    bench --site test_site run-tests --app myschools --module myschools.tests.test_dashboard
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from myschools.api import dashboard as dashboard_api

DASHBOARD_NAME = "MYS Central Monitoring"

EXPECTED_CARDS = [
	"MYS - Active Branches",
	"MYS - Active Students",
	"MYS - Outstanding Royalty",
	"MYS - Overdue Invoices",
	"MYS - This Month Royalty Invoiced",
	"MYS - This Month Fees Collected",
	"MYS - Open Findings",
	"MYS - Overdue Findings",
]

EXPECTED_CHARTS = [
	"MYS - Findings by Severity",
	"MYS - Royalty by Cluster (YTD)",
	"MYS - Royalty Invoiced Trend (12m)",
]


class TestDashboardFixtures(FrappeTestCase):
	"""The dashboard ships as JSON fixtures, so migrate must import everything."""

	def test_dashboard_exists(self):
		self.assertTrue(frappe.db.exists("Dashboard", DASHBOARD_NAME))

	def test_dashboard_wires_all_cards_and_charts(self):
		doc = frappe.get_doc("Dashboard", DASHBOARD_NAME)
		self.assertEqual({c.card for c in doc.cards}, set(EXPECTED_CARDS))
		self.assertEqual({c.chart for c in doc.charts}, set(EXPECTED_CHARTS))

	def test_all_number_cards_exist(self):
		for name in EXPECTED_CARDS:
			self.assertTrue(frappe.db.exists("Number Card", name), msg=name)

	def test_all_dashboard_charts_exist(self):
		for name in EXPECTED_CHARTS:
			self.assertTrue(frappe.db.exists("Dashboard Chart", name), msg=name)

	def test_custom_method_cards_point_at_whitelisted_endpoints(self):
		expected = {
			"MYS - This Month Royalty Invoiced": "myschools.api.dashboard.current_month_royalty_invoiced",
			"MYS - This Month Fees Collected": "myschools.api.dashboard.current_month_fees_collected",
			"MYS - Overdue Findings": "myschools.api.dashboard.overdue_findings_count",
		}
		for card_name, method in expected.items():
			self.assertEqual(frappe.db.get_value("Number Card", card_name, "method"), method)


class TestDashboardEndpoints(FrappeTestCase):
	"""The three Custom-type cards call whitelisted Python endpoints — they must
	not raise and must return Frappe's expected `{value, fieldtype, ...}` shape."""

	def test_current_month_royalty_invoiced_shape(self):
		out = dashboard_api.current_month_royalty_invoiced()
		self.assertIn("value", out)
		self.assertEqual(out["fieldtype"], "Currency")
		self.assertEqual(out["currency"], "PKR")
		self.assertGreaterEqual(out["value"], 0)

	def test_current_month_fees_collected_shape(self):
		out = dashboard_api.current_month_fees_collected()
		self.assertIn("value", out)
		self.assertEqual(out["fieldtype"], "Currency")
		self.assertEqual(out["currency"], "PKR")
		self.assertGreaterEqual(out["value"], 0)

	def test_overdue_findings_count_shape(self):
		out = dashboard_api.overdue_findings_count()
		self.assertIn("value", out)
		self.assertEqual(out["fieldtype"], "Int")
		self.assertGreaterEqual(out["value"], 0)
