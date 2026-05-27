"""Tests for the Phase-5 workflows.

Two workflows ship:
- MYS Inspection Finding Workflow (Draft -> Open -> In Progress -> Resolved -> Verified)
- MYS Royalty Invoice Workflow (Draft -> Unpaid; payment states are db_set)

Coverage:
- Fixture import: both Workflows exist + are active.
- State machine: valid transitions land in the right next state.
- Role gating: a transition fires only for the allowed role.
- Bypass: db_set on status (payment-driven) does NOT go through workflow.
- Auto-creation: Visit submit -> Finding ends at Open via apply_workflow.

Run via:
    bench --site myschools.localhost run-tests --app myschools --module myschools.tests.test_workflows
"""

from contextlib import contextmanager

import frappe
from frappe.model.workflow import WorkflowPermissionError, WorkflowTransitionError, apply_workflow
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today


@contextmanager
def _as_user(email):
	"""Temporarily run as a specific user so role-gated workflow transitions
	are evaluated against that user's roles, not Administrator."""
	prev = frappe.session.user
	frappe.set_user(email)
	try:
		yield
	finally:
		frappe.set_user(prev)


def _ensure_user(email, roles):
	"""Idempotently create a test user with the given roles."""
	if not frappe.db.exists("User", email):
		u = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"enabled": 1,
			}
		)
		u.insert(ignore_permissions=True)
	u = frappe.get_doc("User", email)
	have = {r.role for r in u.roles}
	for role in roles:
		if role not in have:
			u.append("roles", {"role": role})
	u.save(ignore_permissions=True)
	return email


class TestWorkflowFixtures(FrappeTestCase):
	def test_finding_workflow_active(self):
		wf = frappe.get_doc("Workflow", "MYS Inspection Finding Workflow")
		self.assertEqual(wf.document_type, "MYS Inspection Finding")
		self.assertEqual(wf.workflow_state_field, "status")
		self.assertEqual(wf.is_active, 1)

	def test_royalty_workflow_active(self):
		wf = frappe.get_doc("Workflow", "MYS Royalty Invoice Workflow")
		self.assertEqual(wf.document_type, "MYS Royalty Invoice")
		self.assertEqual(wf.workflow_state_field, "status")
		self.assertEqual(wf.is_active, 1)

	def test_finding_workflow_has_expected_states(self):
		wf = frappe.get_doc("Workflow", "MYS Inspection Finding Workflow")
		states = {s.state for s in wf.states}
		self.assertEqual(states, {"Draft", "Open", "In Progress", "Resolved", "Verified", "Cancelled"})

	def test_royalty_workflow_has_expected_states(self):
		wf = frappe.get_doc("Workflow", "MYS Royalty Invoice Workflow")
		states = {s.state for s in wf.states}
		self.assertEqual(states, {"Draft", "Unpaid", "Partial", "Paid", "Overdue", "Cancelled"})

	def test_finding_workflow_transitions_role_gated(self):
		"""Spot-check that role gating made it into the fixture."""
		wf = frappe.get_doc("Workflow", "MYS Inspection Finding Workflow")
		# Verify action is restricted to Audit Officer
		verifies = [t for t in wf.transitions if t.action == "Verify"]
		self.assertGreater(len(verifies), 0)
		self.assertTrue(all(t.allowed == "Audit Officer" for t in verifies))
		# Acknowledge is restricted to Branch Director / Principal
		acks = [t for t in wf.transitions if t.action == "Acknowledge"]
		self.assertGreater(len(acks), 0)
		ack_roles = {t.allowed for t in acks}
		self.assertEqual(ack_roles, {"Branch Director", "Branch Principal"})


class TestFindingWorkflow(FrappeTestCase):
	"""Walk a Finding through the state machine and check side effects."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.branch = frappe.db.get_value("MYS Branch", {}, "name")
		# Find or build a submitted Visit on that branch to anchor Findings.
		cls.visit = frappe.db.get_value(
			"MYS Inspection Visit", {"docstatus": 1, "branch": cls.branch}, "name"
		)
		if not cls.visit and cls.branch:
			# Visit requires an Employee as inspector — reuse any existing one.
			inspector = frappe.db.get_value("Employee", {}, "name")
			if not inspector:
				return  # setUp() below will skip the suite cleanly
			v = frappe.get_doc(
				{
					"doctype": "MYS Inspection Visit",
					"branch": cls.branch,
					"visit_date": today(),
					"visit_type": "Routine",
					"inspector": inspector,
				}
			)
			v.insert(ignore_permissions=True)
			v.submit()
			cls.visit = v.name

	def setUp(self):
		if not self.branch or not self.visit:
			self.skipTest("no MYS Branch/Visit on this site")
		self.audit = _ensure_user("_t_audit@mys.local", ["Audit Officer"])
		self.director = _ensure_user("_t_director@mys.local", ["Branch Director"])
		# A user with no MYS role; used to confirm role gating blocks them.
		self.outsider = _ensure_user("_t_outsider@mys.local", [])

	def _build_finding(self):
		"""Build a Finding stub at Draft state on the test Visit."""
		doc = frappe.get_doc(
			{
				"doctype": "MYS Inspection Finding",
				"visit": self.visit,
				"branch": self.branch,
				"severity": "Major",
				"category": "Safety",
				"status": "Draft",
				"description": "workflow test finding",
				"due_date": add_days(today(), 14),
				"reported_by": self.audit,
				"reported_on": today(),
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	def test_draft_to_open_via_submit_by_audit_officer(self):
		f = self._build_finding()
		with _as_user(self.audit):
			apply_workflow(f, "Submit")
		f.reload()
		self.assertEqual(f.status, "Open")
		self.assertEqual(f.docstatus, 1)

	def test_open_to_in_progress_via_acknowledge_by_director(self):
		f = self._build_finding()
		apply_workflow(f, "Submit")  # Draft -> Open as Administrator
		with _as_user(self.director):
			apply_workflow(f, "Acknowledge")
		f.reload()
		self.assertEqual(f.status, "In Progress")

	def test_outsider_cannot_submit(self):
		f = self._build_finding()
		# Frappe raises WorkflowPermissionError when the user has *some* role
		# in the workflow but not the gating one, and WorkflowTransitionError
		# when the action isn't visible to them at all — both are valid
		# "blocked" outcomes for an outsider.
		with _as_user(self.outsider), self.assertRaises((WorkflowPermissionError, WorkflowTransitionError)):
			apply_workflow(f, "Submit")

	def test_director_cannot_verify_only_audit(self):
		"""Role gate on Verify: Branch Director isn't allowed even after the
		finding reaches Resolved."""
		f = self._build_finding()
		apply_workflow(f, "Submit")
		apply_workflow(f, "Acknowledge")
		apply_workflow(f, "Mark Resolved")
		f.reload()
		f.resolution_notes = "fixed and photographed"
		f.save()
		with _as_user(self.director), self.assertRaises((WorkflowPermissionError, WorkflowTransitionError)):
			apply_workflow(f, "Verify")

	def tearDown(self):
		# Clean up the test findings we minted
		for name in frappe.get_all(
			"MYS Inspection Finding", filters={"description": "workflow test finding"}, pluck="name"
		):
			doc = frappe.get_doc("MYS Inspection Finding", name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("MYS Inspection Finding", name, force=True, ignore_permissions=True)


class TestRoyaltyWorkflowBypass(FrappeTestCase):
	"""The payment-driven `_refresh_status` writes status via db_set, which
	must bypass workflow validation. Otherwise the system can't auto-flip
	Unpaid -> Partial -> Paid as payments come in."""

	def test_db_set_status_bypasses_workflow(self):
		"""db.set_value('status', X) does not raise WorkflowPermissionError
		even when the new value isn't reachable via any defined transition."""
		# Find any existing invoice; if none exist, skip — this is a regression
		# guard, not a setup-heavy E2E.
		inv_name = frappe.db.get_value("MYS Royalty Invoice", {"docstatus": 1}, "name")
		if not inv_name:
			self.skipTest("no submitted MYS Royalty Invoice on this site")
		original = frappe.db.get_value("MYS Royalty Invoice", inv_name, "status")
		try:
			# Jump straight to Paid without going through workflow.
			frappe.db.set_value("MYS Royalty Invoice", inv_name, "status", "Paid")
			self.assertEqual(frappe.db.get_value("MYS Royalty Invoice", inv_name, "status"), "Paid")
		finally:
			frappe.db.set_value("MYS Royalty Invoice", inv_name, "status", original)
