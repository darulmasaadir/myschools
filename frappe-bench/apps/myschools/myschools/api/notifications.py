"""Notifications + Communication Log helpers.

Phase 4 wires three things:

1. ``send_sms`` — routes through :mod:`myschools.api.sms_providers` (Phase 8c).
   Default provider is Stub (log-only). Twilio, HTTP Gateway (Jazz / Easypaisa),
   and Frappe SMS Settings are selectable on ``MYS SMS Settings``.

2. ``log_outbound_email`` — fired from ``Communication.after_insert``.
   Mirrors every outbound email tied to a MYS-namespaced doctype into
   MYS Communication Log, so HO admins can audit "what did the system tell
   the franchisee" without trawling Frappe's Communication doctype.

3. ``log_communication`` / ``send_email_message`` — public helpers for any code
   path that wants to record an outbound message but isn't going through the
   Communication hook (SMS adapters, programmatic email, future WhatsApp).
"""

from __future__ import annotations

import frappe
from frappe.utils import now

from myschools.api.sms_providers import dispatch_sms

MYS_DOCTYPE_PREFIX = "MYS "


def log_communication(
	*,
	channel: str,
	status: str,
	subject: str,
	body: str,
	scope: str = "Individual",
	branch: str | None = None,
	campus: str | None = None,
	recipient_user: str | None = None,
	recipient_role: str | None = None,
	recipient_phone: str | None = None,
	sender: str | None = None,
	gateway: str | None = None,
	provider_reference: str | None = None,
) -> str:
	"""Create an MYS Communication Log row and return its name."""
	log = frappe.get_doc(
		{
			"doctype": "MYS Communication Log",
			"channel": channel,
			"status": status,
			"sent_at": now(),
			"sender": sender or frappe.session.user,
			"scope": scope,
			"branch": branch,
			"campus": campus,
			"recipient_user": recipient_user,
			"recipient_role": recipient_role,
			"recipient_phone": recipient_phone,
			"gateway": gateway,
			"provider_reference": provider_reference,
			"subject": subject[:140] if subject else "",
			"body": body or "",
		}
	)
	log.insert(ignore_permissions=True)
	return log.name


def _resolve_mys_reference(doctype: str | None, name: str | None) -> tuple[str | None, str | None]:
	if not doctype or not name or not doctype.startswith(MYS_DOCTYPE_PREFIX):
		return None, None
	try:
		ref = frappe.get_cached_doc(doctype, name)
		return getattr(ref, "branch", None), getattr(ref, "campus", None)
	except Exception:
		return None, None


@frappe.whitelist()
def send_sms(
	recipient: str,
	message: str,
	doctype: str | None = None,
	name: str | None = None,
) -> dict:
	"""Send an SMS via the configured provider and audit-log the attempt."""
	if not recipient or not message:
		frappe.throw("send_sms requires both recipient and message")

	branch, campus = _resolve_mys_reference(doctype, name)
	phone = recipient.strip()
	recipient_user = phone if "@" in phone else None
	recipient_phone = phone if "@" not in phone else None

	result = dispatch_sms(phone, message)
	status = "Sent" if result.ok else "Failed"
	log_name = log_communication(
		channel="SMS",
		status=status,
		subject=f"SMS to {phone}",
		body=message if result.ok else f"{message}\n\n---\nGateway error: {result.error or 'unknown'}",
		scope="Individual",
		branch=branch,
		campus=campus,
		recipient_user=recipient_user,
		recipient_phone=recipient_phone,
		gateway=result.gateway,
		provider_reference=result.provider_reference,
	)

	if not result.ok:
		frappe.db.commit()
		frappe.throw(result.error or "SMS dispatch failed")

	return {"ok": True, "log": log_name, "gateway": result.gateway, "reference": result.provider_reference}


@frappe.whitelist()
def send_email_message(
	recipient: str,
	subject: str,
	message: str,
	doctype: str | None = None,
	name: str | None = None,
) -> dict:
	"""Send email via Frappe mail + write MYS Communication Log (Phase 8c)."""
	if not recipient or not subject or not message:
		frappe.throw("send_email_message requires recipient, subject, and message")

	branch, campus = _resolve_mys_reference(doctype, name)
	try:
		frappe.sendmail(recipients=[recipient], subject=subject, message=message, now=True)
	except Exception as exc:
		log_communication(
			channel="Email",
			status="Failed",
			subject=subject,
			body=f"{message}\n\n---\nMail error: {exc}",
			scope="Branch" if branch else "Individual",
			branch=branch,
			campus=campus,
			recipient_user=recipient if "@" in recipient else None,
			gateway="frappe-email",
		)
		frappe.db.commit()
		raise

	log_name = log_communication(
		channel="Email",
		status="Sent",
		subject=subject,
		body=message,
		scope="Branch" if branch else "Individual",
		branch=branch,
		campus=campus,
		recipient_user=recipient,
		gateway="frappe-email",
	)
	return {"ok": True, "log": log_name, "gateway": "frappe-email"}


def log_outbound_email(doc, method=None) -> None:
	"""``Communication.after_insert`` hook.

	Mirrors outbound system-generated emails tied to an MYS doctype into
	MYS Communication Log so admins have a single audit view across email
	+ SMS + future channels. Bails out for inbound mail, draft comms, and
	non-MYS references — Frappe's own Communication doctype already
	captures those.

	Both manual emails (``communication_type='Communication'``) and
	Notification-fired emails (``communication_type='Automated Message'``)
	get mirrored. Skipping `Automated Message` was the bug that silently
	dropped every alert-generated email out of the audit log.
	"""
	if getattr(doc, "communication_type", None) not in ("Communication", "Automated Message"):
		return
	if getattr(doc, "sent_or_received", None) != "Sent":
		return
	ref_dt = getattr(doc, "reference_doctype", None) or ""
	if not ref_dt.startswith(MYS_DOCTYPE_PREFIX) and ref_dt != "Fees":
		return

	branch = None
	campus = None
	if doc.reference_doctype and doc.reference_name:
		try:
			ref = frappe.get_cached_doc(doc.reference_doctype, doc.reference_name)
			branch = getattr(ref, "branch", None)
			campus = getattr(ref, "campus", None)
		except Exception:
			pass

	recipients = doc.recipients or ""
	first_recipient = recipients.split(",")[0].strip() if recipients else None

	log_communication(
		channel="Email",
		status="Sent",
		subject=doc.subject or "",
		body=doc.content or "",
		scope="Branch" if branch else "Individual",
		branch=branch,
		campus=campus,
		recipient_user=first_recipient,
		sender=doc.sender,
		gateway="frappe-email",
	)
