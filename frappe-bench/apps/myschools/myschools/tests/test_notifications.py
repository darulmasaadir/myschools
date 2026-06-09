"""Tests for the Phase 4 notification layer.

Covers three things:
- The 6 Email Template + 6 Notification fixtures imported via `bench migrate`.
- `myschools.api.notifications.send_sms` stub creates an MYS Communication
  Log SMS row and returns a stable shape.
- `log_outbound_email` mirrors outbound system emails tied to an MYS
  doctype (or Fees) into MYS Communication Log, and ignores everything
  else (inbound mail, drafts, non-MYS references).

Run via:
    bench --site test_site run-tests --app myschools --module myschools.tests.test_notifications
"""

from typing import ClassVar

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.jinja import render_template

from myschools.api import notifications as notif_api

EXPECTED_NAMES = [
	"MYS - Royalty Invoice Generated",
	"MYS - Royalty Invoice Overdue",
	"MYS - Inspection Finding Assigned",
	"MYS - Inspection Finding Overdue",
	"MYS - Corrective Action Overdue",
	"MYS - Franchise Agreement Expiring",
	"MYS - Branch Document Expiring",
]

EXPECTED_NOTIFICATION_META = {
	"MYS - Royalty Invoice Generated": ("MYS Royalty Invoice", "Submit"),
	"MYS - Royalty Invoice Overdue": ("MYS Royalty Invoice", "Days After"),
	"MYS - Inspection Finding Assigned": ("MYS Inspection Finding", "Submit"),
	"MYS - Inspection Finding Overdue": ("MYS Inspection Finding", "Days After"),
	"MYS - Corrective Action Overdue": ("MYS Corrective Action", "Days After"),
	"MYS - Franchise Agreement Expiring": ("MYS Franchise Agreement", "Days Before"),
	"MYS - Branch Document Expiring": ("MYS Document", "Days Before"),
}


class TestNotificationFixtures(FrappeTestCase):
	def test_all_email_templates_imported(self):
		for name in EXPECTED_NAMES:
			self.assertTrue(frappe.db.exists("Email Template", name), msg=name)

	def test_email_templates_use_html_body(self):
		for name in EXPECTED_NAMES:
			doc = frappe.get_doc("Email Template", name)
			self.assertEqual(doc.use_html, 1, msg=name)
			self.assertIn("MY Schools", doc.response_html, msg=name)

	def test_all_notifications_imported_and_enabled(self):
		for name in EXPECTED_NAMES:
			self.assertTrue(frappe.db.exists("Notification", name), msg=name)
			self.assertEqual(frappe.db.get_value("Notification", name, "enabled"), 1, msg=name)

	def test_notifications_target_correct_doctype_and_event(self):
		for name, (doctype, event) in EXPECTED_NOTIFICATION_META.items():
			row = frappe.db.get_value("Notification", name, ["document_type", "event"], as_dict=True)
			self.assertEqual(row.document_type, doctype, msg=name)
			self.assertEqual(row.event, event, msg=name)

	def test_days_after_notifications_have_date_field(self):
		for name in (
			"MYS - Royalty Invoice Overdue",
			"MYS - Inspection Finding Overdue",
			"MYS - Corrective Action Overdue",
		):
			val = frappe.db.get_value("Notification", name, "date_changed")
			self.assertEqual(val, "due_date", msg=name)

	def test_agreement_expiring_fires_30_days_before(self):
		row = frappe.db.get_value(
			"Notification",
			"MYS - Franchise Agreement Expiring",
			["date_changed", "days_in_advance"],
			as_dict=True,
		)
		self.assertEqual(row.date_changed, "end_date")
		self.assertEqual(row.days_in_advance, 30)

	def test_finding_assigned_has_role_and_doc_field_recipients(self):
		"""Mixed-mode recipients: role-based AND user-field-based on the same notification."""
		rows = frappe.db.get_all(
			"Notification Recipient",
			filters={"parent": "MYS - Inspection Finding Assigned"},
			fields=["receiver_by_role", "receiver_by_document_field"],
		)
		roles = {r.receiver_by_role for r in rows if r.receiver_by_role}
		doc_fields = {r.receiver_by_document_field for r in rows if r.receiver_by_document_field}
		self.assertEqual(roles, {"Branch Director", "Branch Principal", "Audit Officer"})
		self.assertEqual(doc_fields, {"reported_by"})


class TestNotificationJinjaRenders(FrappeTestCase):
	"""Render every notification's subject + body against an in-memory doc of
	the right type. Catches typos like `doc.total_royalty` (the real field is
	`royalty_amount`) — which a fixture-import-only test will silently miss
	because Frappe defers Jinja evaluation until the alert actually fires.

	We use `frappe.get_doc(dict)` to build unsaved doc instances so this test
	doesn't depend on inspection fixtures or seeded data."""

	SAMPLE_DOCS: ClassVar[dict] = {
		"MYS Royalty Invoice": {
			"doctype": "MYS Royalty Invoice",
			"name": "MYS-RI-TEST-0001",
			"branch": "BR-TEST",
			"period_month": 5,
			"period_year": 2026,
			"due_date": "2026-06-15",
			"royalty_amount": 12345.67,
			"outstanding_amount": 12345.67,
			"currency": "PKR",
			"status": "Unpaid",
		},
		"MYS Inspection Finding": {
			"doctype": "MYS Inspection Finding",
			"name": "MYS-FND-TEST-0001",
			"branch": "BR-TEST",
			"severity": "Major",
			"category": "Safety",
			"status": "Open",
			"description": "Test description",
			"due_date": "2026-06-15",
			"reported_by": "Administrator",
		},
		"MYS Corrective Action": {
			"doctype": "MYS Corrective Action",
			"name": "MYS-CA-TEST-0001",
			"finding": "MYS-FND-TEST-0001",
			"branch": "BR-TEST",
			"status": "Planned",
			"due_date": "2026-06-15",
			"action_description": "Fix it",
			"assigned_to": "Administrator",
		},
		"MYS Franchise Agreement": {
			"doctype": "MYS Franchise Agreement",
			"name": "MYS-FA-TEST-0001",
			"branch": "BR-TEST",
			"franchisee": "Test Franchisee",
			"status": "Active",
			"end_date": "2026-12-31",
		},
		"MYS Document": {
			"doctype": "MYS Document",
			"name": "DOC-TEST-0001",
			"title": "Fire Safety Certificate",
			"branch": "BR-TEST",
			"category": "Certificate",
			"status": "Active",
			"expiry_date": "2026-12-31",
		},
	}

	def _stub_doc(self, doctype):
		"""Build an unsaved doc instance carrying the sample field values."""
		return frappe.get_doc(self.SAMPLE_DOCS[doctype])

	def test_every_notification_renders_subject_and_message(self):
		notifs = frappe.get_all(
			"Notification",
			filters={"name": ["like", "MYS - %"]},
			fields=["name", "document_type", "subject", "message"],
		)
		self.assertEqual(len(notifs), 7, "expected 7 MYS notifications")
		for n in notifs:
			with self.subTest(notification=n["name"]):
				doc = self._stub_doc(n["document_type"])
				rendered_subject = render_template(n["subject"], {"doc": doc})
				rendered_body = render_template(n["message"], {"doc": doc})
				# No unrendered Jinja markers left behind.
				self.assertNotIn("{{", rendered_subject, msg=n["name"])
				self.assertNotIn("{{", rendered_body, msg=n["name"])
				# Smoke-check that the rendered output actually contains the
				# branch (or the doc name) — proves we hit at least one real
				# attribute and didn't just emit a static string.
				self.assertTrue(
					"BR-TEST" in rendered_subject + rendered_body
					or "MYS-" in rendered_subject + rendered_body,
					msg=f"{n['name']}: rendered output missing doc context",
				)


class TestSmsStub(FrappeTestCase):
	"""`send_sms` is provider-agnostic. Today it just logs; phase 8 plugs in
	a real gateway. The signature and return shape must stay stable so callers
	don't change."""

	TEST_RECIPIENT = "+923001234567"

	def setUp(self):
		# Burn any leftover SMS logs from prior runs so we count cleanly.
		frappe.db.delete(
			"MYS Communication Log",
			{"channel": "SMS", "recipient_user": ["like", "+923001234%"]},
		)
		frappe.db.commit()

	def test_send_sms_returns_ok_and_log_name(self):
		result = notif_api.send_sms(self.TEST_RECIPIENT, "Test message")
		self.assertTrue(result["ok"])
		self.assertEqual(result["gateway"], "stub")
		self.assertTrue(result["log"].startswith("COMM-"))

	def test_send_sms_writes_communication_log(self):
		notif_api.send_sms(self.TEST_RECIPIENT, "Body of the SMS")
		row = frappe.db.get_value(
			"MYS Communication Log",
			{"channel": "SMS", "body": "Body of the SMS"},
			["channel", "status", "scope", "body", "gateway", "recipient_phone"],
			as_dict=True,
		)
		self.assertIsNotNone(row)
		self.assertEqual(row.channel, "SMS")
		self.assertEqual(row.status, "Sent")
		self.assertEqual(row.scope, "Individual")
		self.assertEqual(row.gateway, "stub")
		self.assertEqual(row.recipient_phone, self.TEST_RECIPIENT)

	def test_send_sms_rejects_empty_args(self):
		with self.assertRaises(frappe.ValidationError):
			notif_api.send_sms("", "hello")
		with self.assertRaises(frappe.ValidationError):
			notif_api.send_sms(self.TEST_RECIPIENT, "")


class TestLogCommunication(FrappeTestCase):
	def test_log_communication_creates_row_with_all_fields(self):
		name = notif_api.log_communication(
			channel="Email",
			status="Sent",
			subject="hello",
			body="<p>hi</p>",
			scope="Branch",
			branch=None,  # OK to be None — schema doesn't require it
			recipient_role="Branch Director",
		)
		doc = frappe.get_doc("MYS Communication Log", name)
		self.assertEqual(doc.channel, "Email")
		self.assertEqual(doc.status, "Sent")
		self.assertEqual(doc.scope, "Branch")
		self.assertEqual(doc.recipient_role, "Branch Director")
		self.assertEqual(doc.subject, "hello")


class TestLogOutboundEmail(FrappeTestCase):
	"""Hook-level coverage. The mirror has to accept both manual emails
	(``communication_type='Communication'``) AND Notification-fired emails
	(``communication_type='Automated Message'``) — only matching the former
	was the bug that silently dropped every alert out of the audit log."""

	@staticmethod
	def _stub(comm_type, sent_or_received="Sent", ref_dt="MYS Royalty Invoice", ref_name="STUB"):
		# Use Administrator for sender/recipient so the MYS Communication Log
		# row (which has Link fields to User) saves cleanly. The hook never
		# touches the Communication itself — it reads attrs and forwards.
		return frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": comm_type,
				"sent_or_received": sent_or_received,
				"subject": f"stub {comm_type}",
				"content": "body",
				"sender": "Administrator",
				"recipients": "Administrator",
				"reference_doctype": ref_dt,
				"reference_name": ref_name,
			}
		)

	def setUp(self):
		frappe.db.delete("MYS Communication Log", {"subject": ["like", "stub %"]})
		frappe.db.commit()

	def test_automated_message_on_mys_doc_is_mirrored(self):
		"""Notifications create Communication rows with type='Automated Message'.
		The mirror must pick those up — this was the bug that hid every
		Notification-generated email from the audit log."""
		notif_api.log_outbound_email(self._stub("Automated Message"))
		self.assertTrue(frappe.db.exists("MYS Communication Log", {"subject": "stub Automated Message"}))

	def test_manual_communication_on_mys_doc_is_mirrored(self):
		notif_api.log_outbound_email(self._stub("Communication"))
		self.assertTrue(frappe.db.exists("MYS Communication Log", {"subject": "stub Communication"}))

	def test_chat_messages_are_not_mirrored(self):
		"""``Chat`` (or other non-email types) shouldn't land in the audit log."""
		notif_api.log_outbound_email(self._stub("Chat"))
		self.assertFalse(frappe.db.exists("MYS Communication Log", {"subject": "stub Chat"}))

	def test_inbound_communication_is_not_mirrored(self):
		notif_api.log_outbound_email(self._stub("Communication", sent_or_received="Received"))
		self.assertFalse(frappe.db.exists("MYS Communication Log", {"subject": "stub Communication"}))

	def test_non_mys_reference_is_not_mirrored(self):
		notif_api.log_outbound_email(self._stub("Automated Message", ref_dt="User", ref_name="x"))
		self.assertFalse(frappe.db.exists("MYS Communication Log", {"subject": "stub Automated Message"}))
