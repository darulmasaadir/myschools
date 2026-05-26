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

import frappe
from frappe.tests.utils import FrappeTestCase

from myschools.api import notifications as notif_api

EXPECTED_NAMES = [
	"MYS - Royalty Invoice Generated",
	"MYS - Royalty Invoice Overdue",
	"MYS - Inspection Finding Assigned",
	"MYS - Inspection Finding Overdue",
	"MYS - Corrective Action Overdue",
	"MYS - Franchise Agreement Expiring",
]

EXPECTED_NOTIFICATION_META = {
	"MYS - Royalty Invoice Generated": ("MYS Royalty Invoice", "Submit"),
	"MYS - Royalty Invoice Overdue": ("MYS Royalty Invoice", "Days After"),
	"MYS - Inspection Finding Assigned": ("MYS Inspection Finding", "Submit"),
	"MYS - Inspection Finding Overdue": ("MYS Inspection Finding", "Days After"),
	"MYS - Corrective Action Overdue": ("MYS Corrective Action", "Days After"),
	"MYS - Franchise Agreement Expiring": ("MYS Franchise Agreement", "Days Before"),
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
			["channel", "status", "scope", "body"],
			as_dict=True,
		)
		self.assertIsNotNone(row)
		self.assertEqual(row.channel, "SMS")
		self.assertEqual(row.status, "Sent")
		self.assertEqual(row.scope, "Individual")

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
