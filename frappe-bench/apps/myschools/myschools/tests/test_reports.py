"""Tests for the Phase 6 Query Reports.

Four Script Reports ship in this slice:
- MYS Royalty Aging
- MYS Fee Collection by Branch
- MYS Findings by Branch and Severity
- MYS Branch Health Scorecard

These tests confirm:
1. The Report fixtures import cleanly.
2. Each report's `execute()` callable runs without raising against the
   current site data and returns a (columns, rows) tuple shaped the way
   Frappe expects.
3. Each report's `ref_doctype` resolves to a real DocType.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from myschools.my_school_erp.report.mys_branch_health_scorecard import mys_branch_health_scorecard
from myschools.my_school_erp.report.mys_fee_collection_by_branch import mys_fee_collection_by_branch
from myschools.my_school_erp.report.mys_findings_by_branch_and_severity import (
	mys_findings_by_branch_and_severity,
)
from myschools.my_school_erp.report.mys_royalty_aging import mys_royalty_aging

REPORTS = {
	"MYS Royalty Aging": ("MYS Royalty Invoice", mys_royalty_aging.execute, 9),
	"MYS Fee Collection by Branch": ("Fees", mys_fee_collection_by_branch.execute, 7),
	"MYS Findings by Branch and Severity": (
		"MYS Inspection Finding",
		mys_findings_by_branch_and_severity.execute,
		5,
	),
	"MYS Branch Health Scorecard": ("MYS Branch", mys_branch_health_scorecard.execute, 7),
}


class TestMysReportFixtures(FrappeTestCase):
	def test_all_reports_imported(self):
		for name in REPORTS:
			with self.subTest(report=name):
				self.assertTrue(
					frappe.db.exists("Report", name),
					f"Report fixture '{name}' should be imported",
				)
				row = frappe.db.get_value(
					"Report", name, ["report_type", "ref_doctype", "is_standard"], as_dict=True
				)
				self.assertEqual(row.report_type, "Script Report")
				self.assertEqual(row.is_standard, "Yes")
				self.assertEqual(row.ref_doctype, REPORTS[name][0])
				self.assertTrue(frappe.db.exists("DocType", row.ref_doctype))


class TestMysReportExecution(FrappeTestCase):
	"""execute() runs against real site data and returns a sane shape."""

	def test_each_execute_returns_columns_and_rows(self):
		for name, (_, execute, expected_cols) in REPORTS.items():
			with self.subTest(report=name):
				columns, rows = execute(filters={})
				self.assertEqual(
					len(columns),
					expected_cols,
					f"{name}: expected {expected_cols} columns, got {len(columns)}",
				)
				self.assertIsInstance(rows, list)
				# Every row must be a dict whose keys match column fieldnames.
				if rows:
					fieldnames = {c["fieldname"] for c in columns}
					missing = fieldnames - set(rows[0].keys())
					self.assertFalse(
						missing,
						f"{name}: first row is missing fieldnames {missing}",
					)

	def test_royalty_aging_bucket_math(self):
		columns, rows = mys_royalty_aging.execute(filters={})
		# Every row's bucket sum must equal its outstanding (within rounding).
		for row in rows:
			bucket_total = row["b_0_30"] + row["b_31_60"] + row["b_61_90"] + row["b_over_90"]
			self.assertAlmostEqual(
				row["outstanding"],
				bucket_total,
				places=2,
				msg=f"{row['branch']}: outstanding {row['outstanding']} != bucket sum {bucket_total}",
			)

	def test_fee_collection_rate_in_range(self):
		columns, rows = mys_fee_collection_by_branch.execute(filters={})
		for row in rows:
			self.assertGreaterEqual(row["collection_rate"], 0)
			self.assertLessEqual(row["collection_rate"], 100)

	def test_findings_pivot_totals_match_per_row(self):
		columns, rows = mys_findings_by_branch_and_severity.execute(filters={})
		for row in rows:
			self.assertEqual(
				row["total"],
				row["critical"] + row["major"] + row["minor"],
				f"{row['branch']}: total != critical+major+minor",
			)
