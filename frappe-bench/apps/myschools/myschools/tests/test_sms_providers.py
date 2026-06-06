"""Phase 8c — SMS provider adapters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from myschools.api import notifications as notif_api
from myschools.api.sms_providers import dispatch_sms


class TestSmsProviders(FrappeTestCase):
	def setUp(self):
		frappe.db.delete(
			"MYS Communication Log", {"channel": "SMS", "recipient_phone": ["like", "+92300999%"]}
		)
		frappe.db.commit()
		self._orig_provider = frappe.db.get_single_value("MYS SMS Settings", "sms_provider")

	def tearDown(self):
		if frappe.db.exists("DocType", "MYS SMS Settings"):
			frappe.db.set_value(
				"MYS SMS Settings", "MYS SMS Settings", "sms_provider", self._orig_provider or "Stub"
			)
		frappe.db.commit()

	def _set_provider(self, provider: str, **fields):
		if not frappe.db.exists("DocType", "MYS SMS Settings"):
			self.skipTest("MYS SMS Settings not migrated")
		doc = frappe.get_single("MYS SMS Settings")
		doc.sms_provider = provider
		for key, val in fields.items():
			setattr(doc, key, val)
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	def test_stub_provider_logs_only(self):
		self._set_provider("Stub")
		result = dispatch_sms("+923009990001", "hello stub")
		self.assertTrue(result.ok)
		self.assertEqual(result.gateway, "stub")

	def test_send_sms_stub_writes_gateway_on_log(self):
		self._set_provider("Stub")
		out = notif_api.send_sms("+923009990002", "body")
		self.assertEqual(out["gateway"], "stub")
		row = frappe.db.get_value(
			"MYS Communication Log",
			out["log"],
			["gateway", "recipient_phone", "status"],
			as_dict=True,
		)
		self.assertEqual(row.gateway, "stub")
		self.assertEqual(row.recipient_phone, "+923009990002")
		self.assertEqual(row.status, "Sent")

	@patch("requests.post")
	def test_twilio_provider_success(self, mock_post: MagicMock):
		mock_post.return_value = MagicMock(status_code=201, text='{"sid":"SM123"}')
		mock_post.return_value.json.return_value = {"sid": "SM123"}
		doc = frappe.get_single("MYS SMS Settings")
		doc.sms_provider = "Twilio"
		doc.twilio_account_sid = "ACtest"
		doc.twilio_from_number = "+15551234567"
		doc.twilio_auth_token = "secret"
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		result = dispatch_sms("+923009990003", "twilio body")
		self.assertTrue(result.ok)
		self.assertEqual(result.gateway, "twilio")
		self.assertEqual(result.provider_reference, "SM123")
		mock_post.assert_called_once()

	@patch("requests.post")
	def test_http_gateway_failure_surfaces_error(self, mock_post: MagicMock):
		mock_post.return_value = MagicMock(status_code=500, text="gateway down")
		self._set_provider(
			"HTTP Gateway",
			http_gateway_url="https://sms.example.test/send",
			http_use_post=1,
			http_message_param="msg",
			http_receiver_param="msisdn",
		)

		result = dispatch_sms("+923009990004", "fail me")
		self.assertFalse(result.ok)
		self.assertEqual(result.gateway, "http")
		self.assertIn("gateway down", result.error or "")

	def test_twilio_missing_credentials_returns_error(self):
		doc = frappe.get_single("MYS SMS Settings")
		doc.sms_provider = "Twilio"
		doc.twilio_account_sid = ""
		doc.twilio_from_number = ""
		doc.twilio_auth_token = ""
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		result = dispatch_sms("+923009990005", "should fail")
		self.assertFalse(result.ok)
		self.assertEqual(result.gateway, "twilio")
		self.assertIn("missing", (result.error or "").lower())

	def test_send_sms_failed_dispatch_throws(self):
		doc = frappe.get_single("MYS SMS Settings")
		doc.sms_provider = "Twilio"
		doc.twilio_account_sid = ""
		doc.twilio_from_number = ""
		doc.twilio_auth_token = ""
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		with self.assertRaises((frappe.ValidationError, frappe.exceptions.ValidationError)):
			notif_api.send_sms("+923009990006", "should fail")


class TestSendEmailMessage(FrappeTestCase):
	TEST_EMAIL = "ceo@mys.local"

	def setUp(self):
		frappe.db.delete("MYS Communication Log", {"subject": ["like", "8c test %"]})
		frappe.db.commit()

	@patch("myschools.api.notifications.frappe.sendmail")
	def test_send_email_message_success(self, mock_sendmail: MagicMock):
		out = notif_api.send_email_message(self.TEST_EMAIL, "8c test subject", "<p>hello</p>")
		self.assertTrue(out["ok"])
		self.assertEqual(out["gateway"], "frappe-email")
		mock_sendmail.assert_called_once()
		row = frappe.db.get_value(
			"MYS Communication Log",
			out["log"],
			["channel", "status", "gateway"],
			as_dict=True,
		)
		self.assertEqual(row.channel, "Email")
		self.assertEqual(row.status, "Sent")
		self.assertEqual(row.gateway, "frappe-email")

	@patch("myschools.api.notifications.frappe.sendmail", side_effect=Exception("smtp down"))
	def test_send_email_message_failure_logs_failed(self, _mock_sendmail: MagicMock):
		with self.assertRaises(Exception):
			notif_api.send_email_message(self.TEST_EMAIL, "8c test fail", "body")
		self.assertTrue(
			frappe.db.exists(
				"MYS Communication Log",
				{"subject": "8c test fail", "status": "Failed", "gateway": "frappe-email"},
			)
		)
