"""Integration tests for the inspection workflow: templates, visits with
scoring, findings auto-creation, and corrective action verification.

Run via:
    bench --site myschools.localhost run-tests --app myschools --module myschools.tests.test_inspection
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from myschools.api.inspection import (
	apply_template_to_visit,
	auto_create_findings_from_failed_results,
)

CLUSTER = "_TEST_INSP_CL"
BRANCH = "_TEST_INSP_BR"
CAMPUS = f"{BRANCH}-Kids"
EMPLOYEE_TAG = "_test_inspector@example.com"


class TestInspectionWorkflow(FrappeTestCase):
	"""End-to-end coverage of the inspection decomposition."""

	inspector: str = ""
	template: str = ""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.inspector = cls._build_fixture_tree()
		cls.template = cls._build_template()

	def tearDown(self):
		# Order matters: corrective actions -> findings -> visits.
		for ca in frappe.get_all("MYS Corrective Action", filters={"branch": BRANCH}, pluck="name"):
			frappe.delete_doc("MYS Corrective Action", ca, force=True, ignore_permissions=True)
		for f in frappe.get_all("MYS Inspection Finding", filters={"branch": BRANCH}, pluck="name"):
			doc = frappe.get_doc("MYS Inspection Finding", f)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("MYS Inspection Finding", f, force=True, ignore_permissions=True)
		for v in frappe.get_all("MYS Inspection Visit", filters={"branch": BRANCH}, pluck="name"):
			doc = frappe.get_doc("MYS Inspection Visit", v)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("MYS Inspection Visit", v, force=True, ignore_permissions=True)
		super().tearDown()

	@classmethod
	def tearDownClass(cls):
		if cls.template and frappe.db.exists("MYS Inspection Checklist Template", cls.template):
			frappe.delete_doc(
				"MYS Inspection Checklist Template", cls.template, force=True, ignore_permissions=True
			)
		if cls.inspector and frappe.db.exists("Employee", cls.inspector):
			frappe.delete_doc("Employee", cls.inspector, force=True, ignore_permissions=True)
		if frappe.db.exists("MYS Campus", CAMPUS):
			frappe.delete_doc("MYS Campus", CAMPUS, force=True, ignore_permissions=True)
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
					"cluster_name": "Test Inspection Cluster",
					"region": "Test",
				}
			).insert(ignore_permissions=True)

		if not frappe.db.exists("MYS Branch", BRANCH):
			frappe.get_doc(
				{
					"doctype": "MYS Branch",
					"branch_code": BRANCH,
					"branch_name": "Test Inspection Branch",
					"cluster": CLUSTER,
					"city": "Testville",
					"province": "Test",
					"is_active": 1,
				}
			).insert(ignore_permissions=True)

		if not frappe.db.exists("MYS Campus", CAMPUS):
			frappe.get_doc(
				{
					"doctype": "MYS Campus",
					"branch": BRANCH,
					"campus_type": "Kids",
					"is_active": 1,
				}
			).insert(ignore_permissions=True)

		# Employee uses autoname; identify by a tag we control (personal_email)
		# and return the actual name.
		existing = frappe.db.get_value("Employee", {"personal_email": EMPLOYEE_TAG}, "name")
		if existing:
			return existing
		emp = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": "Test",
				"last_name": "Inspector",
				"personal_email": EMPLOYEE_TAG,
				"gender": "Male",
				"date_of_birth": "1990-01-01",
				"date_of_joining": "2020-01-01",
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		return emp.name

	@classmethod
	def _build_template(cls):
		t = frappe.get_doc(
			{
				"doctype": "MYS Inspection Checklist Template",
				"template_name": "Test Routine Template",
				"visit_type": "Routine",
				"version": "1.0",
				"is_active": 1,
				"items": [
					{
						"item_text": "Fire exits clear",
						"category": "Safety",
						"severity": "Critical",
						"weight": 3,
						"max_score": 5,
					},
					{
						"item_text": "Classrooms clean",
						"category": "Cleanliness",
						"severity": "Major",
						"weight": 2,
						"max_score": 5,
					},
					{
						"item_text": "Bulletin board updated",
						"category": "Academic",
						"severity": "Minor",
						"weight": 1,
						"max_score": 5,
					},
				],
			}
		).insert(ignore_permissions=True)
		return t.name

	def _new_visit(self, *, visit_date=None):
		v = frappe.get_doc(
			{
				"doctype": "MYS Inspection Visit",
				"branch": BRANCH,
				"campus": CAMPUS,
				"visit_type": "Routine",
				"visit_date": visit_date or today(),
				"inspector": self.inspector,
			}
		).insert(ignore_permissions=True)
		return v

	# --- template application ----------------------------------------------

	def test_apply_template_populates_results(self):
		"""apply_template_to_visit snapshots template items into the visit's results table."""
		visit = self._new_visit()
		count = apply_template_to_visit(visit.name, self.template)
		visit.reload()
		self.assertEqual(count, 3)
		self.assertEqual(len(visit.checklist_results), 3)
		self.assertEqual(visit.checklist_template, self.template)
		# Snapshot fields propagated
		first = visit.checklist_results[0]
		self.assertEqual(first.item_text, "Fire exits clear")
		self.assertEqual(first.severity, "Critical")
		self.assertEqual(first.weight, 3)
		self.assertEqual(first.max_score, 5)

	def test_apply_template_rejects_submitted_visit(self):
		"""Cannot apply a template to an already-submitted visit."""
		visit = self._new_visit()
		visit.submit()
		with self.assertRaises(frappe.exceptions.ValidationError):
			apply_template_to_visit(visit.name, self.template)

	# --- score computation -------------------------------------------------

	def test_score_computes_correctly(self):
		"""Score = sum(score)/sum(max_score); weighted = sum(score*w)/sum(max*w). N/A skipped."""
		visit = self._new_visit()
		visit.append(
			"checklist_results",
			{
				"item_text": "A",
				"category": "Safety",
				"severity": "Critical",
				"weight": 3,
				"max_score": 5,
				"result": "Pass",
				"score": 5,
			},
		)
		visit.append(
			"checklist_results",
			{
				"item_text": "B",
				"category": "Cleanliness",
				"severity": "Major",
				"weight": 2,
				"max_score": 5,
				"result": "Fail",
				"score": 1,
			},
		)
		visit.append(
			"checklist_results",
			{
				"item_text": "C",
				"category": "Academic",
				"severity": "Minor",
				"weight": 1,
				"max_score": 5,
				"result": "N/A",
				"score": 0,
			},
		)
		visit.save()

		# Raw: passed=1, failed=1, na=1; score=6/10=60%
		self.assertEqual(visit.total_items, 3)
		self.assertEqual(visit.items_passed, 1)
		self.assertEqual(visit.items_failed, 1)
		self.assertEqual(visit.items_na, 1)
		self.assertEqual(visit.score_percent, 60)
		# Weighted: (5*3 + 1*2) / (5*3 + 5*2) = 17/25 = 68%
		self.assertEqual(visit.weighted_score, 68)

	def test_empty_checklist_gives_zero_score(self):
		"""A visit with no results has zero score, not a divide-by-zero error."""
		visit = self._new_visit()
		visit.save()
		self.assertEqual(visit.score_percent, 0)
		self.assertEqual(visit.weighted_score, 0)

	# --- branch/campus validation ------------------------------------------

	def test_campus_must_belong_to_branch(self):
		"""Cannot pick a campus that doesn't belong to the visit's branch."""
		# Create a second branch + campus
		other_branch = "_TEST_INSP_BR2"
		other_campus = f"{other_branch}-Kids"
		try:
			frappe.get_doc(
				{
					"doctype": "MYS Branch",
					"branch_code": other_branch,
					"branch_name": "Other Branch",
					"cluster": CLUSTER,
					"city": "X",
					"province": "X",
					"is_active": 1,
				}
			).insert(ignore_permissions=True)
			frappe.get_doc(
				{
					"doctype": "MYS Campus",
					"branch": other_branch,
					"campus_type": "Kids",
					"is_active": 1,
				}
			).insert(ignore_permissions=True)

			with self.assertRaises(frappe.exceptions.ValidationError):
				frappe.get_doc(
					{
						"doctype": "MYS Inspection Visit",
						"branch": BRANCH,
						"campus": other_campus,  # wrong branch
						"visit_type": "Routine",
						"visit_date": today(),
						"inspector": self.inspector,
					}
				).insert(ignore_permissions=True)
		finally:
			if frappe.db.exists("MYS Campus", other_campus):
				frappe.delete_doc("MYS Campus", other_campus, force=True, ignore_permissions=True)
			if frappe.db.exists("MYS Branch", other_branch):
				frappe.delete_doc("MYS Branch", other_branch, force=True, ignore_permissions=True)

	# --- auto-create findings ----------------------------------------------

	def test_findings_auto_created_for_critical_and_major_failures(self):
		"""On submit, every failed Critical/Major item becomes a Finding. Minor failures don't."""
		visit = self._new_visit()
		apply_template_to_visit(visit.name, self.template)
		visit.reload()
		# Fail all three
		for row in visit.checklist_results:
			row.result = "Fail"
			row.score = 0
		visit.save()
		visit.submit()

		findings = frappe.get_all(
			"MYS Inspection Finding",
			filters={"visit": visit.name},
			fields=["name", "severity", "category", "due_date"],
		)
		# 2 findings: Critical (Safety) + Major (Cleanliness). Minor is skipped.
		self.assertEqual(len(findings), 2)
		severities = {f.severity for f in findings}
		self.assertEqual(severities, {"Critical", "Major"})

		# Critical findings get a 7-day due_date, Major get 21
		by_sev = {f.severity: f for f in findings}
		self.assertEqual(by_sev["Critical"].due_date, add_days(visit.visit_date, 7))
		self.assertEqual(by_sev["Major"].due_date, add_days(visit.visit_date, 21))

	def test_findings_idempotent(self):
		"""Re-running auto_create on the same visit doesn't create duplicates."""
		visit = self._new_visit()
		apply_template_to_visit(visit.name, self.template)
		visit.reload()
		visit.checklist_results[0].result = "Fail"
		visit.checklist_results[0].score = 0
		visit.save()
		visit.submit()  # creates 1 finding (the Critical row)

		# Calling again returns [] and creates nothing new
		more = auto_create_findings_from_failed_results(visit.name)
		self.assertEqual(more, [])
		self.assertEqual(frappe.db.count("MYS Inspection Finding", {"visit": visit.name}), 1)

	# --- finding workflow --------------------------------------------------

	def test_finding_cannot_be_verified_without_resolution_notes(self):
		"""Status=Verified requires resolution_notes.

		With the Phase-5 workflow attached, Open -> Verified is not a valid
		transition (must go through Resolved first). We seed the workflow
		state to Resolved via ``db.set_value`` (bypasses workflow validation)
		so this test exercises only the controller's resolution_notes guard,
		not the workflow's transition rules.
		"""
		visit = self._new_visit()
		apply_template_to_visit(visit.name, self.template)
		visit.reload()
		visit.checklist_results[0].result = "Fail"
		visit.checklist_results[0].score = 0
		visit.save()
		visit.submit()

		finding_name = frappe.get_all("MYS Inspection Finding", filters={"visit": visit.name}, pluck="name")[
			0
		]
		frappe.db.set_value("MYS Inspection Finding", finding_name, "status", "Resolved")
		finding = frappe.get_doc("MYS Inspection Finding", finding_name)
		finding.status = "Verified"
		# resolution_notes is blank — controller throws, not workflow.
		with self.assertRaises(frappe.exceptions.ValidationError):
			finding.save()

	# --- corrective action flips finding ----------------------------------

	def test_verified_corrective_action_flips_finding_status(self):
		"""When all corrective actions for a finding are Verified, finding flips to Verified."""
		visit = self._new_visit()
		apply_template_to_visit(visit.name, self.template)
		visit.reload()
		visit.checklist_results[0].result = "Fail"  # Critical
		visit.checklist_results[0].score = 0
		visit.save()
		visit.submit()

		finding_name = frappe.get_all("MYS Inspection Finding", filters={"visit": visit.name}, pluck="name")[
			0
		]

		# Create two corrective actions, both initially Planned
		ca1 = frappe.get_doc(
			{
				"doctype": "MYS Corrective Action",
				"finding": finding_name,
				"branch": BRANCH,
				"campus": CAMPUS,
				"status": "Planned",
				"due_date": add_days(today(), 7),
				"action_description": "Clear fire exits",
				"assigned_to": "Administrator",
			}
		).insert(ignore_permissions=True)
		ca2 = frappe.get_doc(
			{
				"doctype": "MYS Corrective Action",
				"finding": finding_name,
				"branch": BRANCH,
				"campus": CAMPUS,
				"status": "Planned",
				"due_date": add_days(today(), 7),
				"action_description": "Post evacuation map",
				"assigned_to": "Administrator",
			}
		).insert(ignore_permissions=True)
		# Finding still Open
		self.assertEqual(frappe.db.get_value("MYS Inspection Finding", finding_name, "status"), "Open")

		# Verify CA1 — finding still Open because CA2 is still Planned
		ca1.status = "Verified"
		ca1.verification_notes = "Inspector confirmed on-site"
		ca1.save()
		self.assertEqual(frappe.db.get_value("MYS Inspection Finding", finding_name, "status"), "Open")

		# Verify CA2 — now all CAs are Verified, finding should flip
		ca2.status = "Verified"
		ca2.verification_notes = "Photo attached, signed off"
		ca2.save()
		self.assertEqual(frappe.db.get_value("MYS Inspection Finding", finding_name, "status"), "Verified")
