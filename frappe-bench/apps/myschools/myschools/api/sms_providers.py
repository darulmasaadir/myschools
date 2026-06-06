"""Phase 8c — pluggable SMS providers for MYS Communication Log.

Providers are selected via the ``MYS SMS Settings`` single. ``send_sms`` in
``api/notifications.py`` calls :func:`dispatch_sms` so callers keep a stable
signature when gateways change.
"""

from __future__ import annotations

from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils.password import get_decrypted_password


@dataclass(frozen=True)
class SmsDispatchResult:
	ok: bool
	gateway: str
	provider_reference: str | None = None
	error: str | None = None


def get_sms_settings() -> frappe.Document:
	if frappe.db.exists("DocType", "MYS SMS Settings"):
		return frappe.get_single("MYS SMS Settings")
	# Before migrate on very old sites — behave like stub.
	return frappe._dict({"sms_provider": "Stub"})


def dispatch_sms(recipient: str, message: str) -> SmsDispatchResult:
	"""Route an SMS through the configured provider."""
	settings = get_sms_settings()
	provider = (settings.sms_provider or "Stub").strip()

	if provider == "Twilio":
		return _send_twilio(settings, recipient, message)
	if provider == "HTTP Gateway":
		return _send_http_gateway(settings, recipient, message)
	if provider == "Frappe SMS Settings":
		return _send_frappe_sms(recipient, message)
	return SmsDispatchResult(ok=True, gateway="stub")


def _normalize_phone(recipient: str) -> str:
	phone = recipient.strip()
	for ch in (" ", "-", "(", ")"):
		phone = phone.replace(ch, "")
	return phone


def _send_twilio(settings, recipient: str, message: str) -> SmsDispatchResult:
	account_sid = (settings.twilio_account_sid or "").strip()
	from_number = (settings.twilio_from_number or "").strip()
	auth_token = ""
	if account_sid:
		try:
			auth_token = get_decrypted_password("MYS SMS Settings", "MYS SMS Settings", "twilio_auth_token")
		except frappe.ValidationError:
			auth_token = ""
	if not all([account_sid, auth_token, from_number]):
		return SmsDispatchResult(
			ok=False,
			gateway="twilio",
			error=_("Twilio is selected but Account SID, Auth Token, or From Number is missing."),
		)

	import requests

	phone = _normalize_phone(recipient)
	url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
	response = requests.post(
		url,
		auth=(account_sid, auth_token),
		data={"To": phone, "From": from_number, "Body": message},
		timeout=30,
	)
	if response.status_code >= 400:
		return SmsDispatchResult(
			ok=False,
			gateway="twilio",
			error=response.text[:500] or f"HTTP {response.status_code}",
		)

	ref = None
	try:
		ref = response.json().get("sid")
	except Exception:
		ref = None
	return SmsDispatchResult(ok=True, gateway="twilio", provider_reference=ref)


def _send_http_gateway(settings, recipient: str, message: str) -> SmsDispatchResult:
	url = (settings.http_gateway_url or "").strip()
	if not url:
		return SmsDispatchResult(
			ok=False,
			gateway="http",
			error=_("HTTP Gateway is selected but Gateway URL is empty."),
		)

	import requests

	msg_param = settings.http_message_param or "message"
	rcv_param = settings.http_receiver_param or "to"
	payload = {msg_param: message, rcv_param: _normalize_phone(recipient)}
	kwargs = {"json": payload, "timeout": 30}
	if settings.http_use_post:
		response = requests.post(url, **kwargs)
	else:
		response = requests.get(url, params=payload, timeout=30)

	if response.status_code >= 400:
		return SmsDispatchResult(
			ok=False,
			gateway="http",
			error=response.text[:500] or f"HTTP {response.status_code}",
		)

	ref = None
	try:
		body = response.json()
		if isinstance(body, dict):
			ref = body.get("id") or body.get("message_id") or body.get("reference")
	except Exception:
		ref = None
	return SmsDispatchResult(ok=True, gateway="http", provider_reference=ref)


def _send_frappe_sms(recipient: str, message: str) -> SmsDispatchResult:
	if not frappe.db.get_single_value("SMS Settings", "sms_gateway_url"):
		return SmsDispatchResult(
			ok=False,
			gateway="frappe-sms",
			error=_("Frappe SMS Settings has no gateway URL configured."),
		)

	from frappe.core.doctype.sms_settings.sms_settings import send_sms as frappe_send_sms

	try:
		frappe_send_sms([_normalize_phone(recipient)], message, success_msg=False)
	except Exception as exc:
		return SmsDispatchResult(ok=False, gateway="frappe-sms", error=str(exc))
	return SmsDispatchResult(ok=True, gateway="frappe-sms")
