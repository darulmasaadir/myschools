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

	def test_chart_filters_json_is_list_of_lists(self):
		"""Frappe's `dashboard_chart.get()` calls `.append()` on the parsed
		`filters_json`. If a chart fixture ships a JSON OBJECT
		(`{"docstatus":1}`) instead of an ARRAY of arrays
		(`[["DocType","docstatus","=",1,false]]`), the dashboard blows up with
		`'NoneType' object is not callable` at chart render time. This guard
		makes that shape mistake impossible to land again."""
		import json as _json

		for name in EXPECTED_CHARTS:
			raw = frappe.db.get_value("Dashboard Chart", name, "filters_json") or "[]"
			parsed = _json.loads(raw)
			self.assertIsInstance(
				parsed,
				list,
				msg=f"{name} filters_json must be a JSON array, got {type(parsed).__name__}: {raw}",
			)
			for row in parsed:
				self.assertIsInstance(
					row, list, msg=f"{name} filters_json rows must be arrays, got {type(row).__name__}: {row}"
				)

	def test_chart_get_endpoint_does_not_raise(self):
		"""End-to-end guard: hit Frappe's dashboard_chart.get for each MYS chart
		and assert no exception. Catches any future fixture or schema drift that
		would crash the desk dashboard for a real user."""
		from frappe.desk.doctype.dashboard_chart.dashboard_chart import get as chart_get

		for name in EXPECTED_CHARTS:
			with self.subTest(chart=name):
				# Just call — any exception fails the test. We don't assert on the
				# shape because Group By charts return None when there's no data,
				# which is legitimate.
				chart_get(chart_name=name, refresh=1)


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
