"""Notifications + Communication Log helpers.

Phase 4 wires three things:

1. ``send_sms`` — provider-agnostic stub. Today it logs to MYS Communication
   Log only; Phase 8 will route to a real gateway (JazzCash / Easypaisa /
   Twilio) keyed off Frappe's SMS Settings. The signature is stable so
   callers don't have to change when the gateway lands.

2. ``log_outbound_email`` — fired from ``Communication.after_insert``.
   Mirrors every outbound email tied to a MYS-namespaced doctype into
   MYS Communication Log, so HO admins can audit "what did the system tell
   the franchisee" without trawling Frappe's Communication doctype.

3. ``log_communication`` — public helper for any code path that wants to
   record an outbound message but isn't going through ``frappe.sendmail``
   (e.g. the SMS stub above, or a future WhatsApp adapter).
"""

from __future__ import annotations

import frappe
from frappe.utils import now

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
	sender: str | None = None,
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
			"subject": subject[:140] if subject else "",
			"body": body or "",
		}
	)
	log.insert(ignore_permissions=True)
	return log.name


@frappe.whitelist()
def send_sms(
	recipient: str,
	message: str,
	doctype: str | None = None,
	name: str | None = None,
) -> dict:
	"""Provider-agnostic SMS stub.

	Today: writes a Sent row to MYS Communication Log and returns success.
	Tomorrow (Phase 8): if Frappe's "SMS Settings" is configured, route the
	message through it; otherwise fall back to the stub.

	The stable signature ``send_sms(recipient, message, doctype, name)``
	lets callers (Notifications using channel=SMS, scheduled jobs, future
	WhatsApp adapter, etc.) stay unchanged when the real gateway lands.
	"""
	if not recipient or not message:
		frappe.throw("send_sms requires both recipient and message")

	branch = None
	campus = None
	if doctype and name and doctype.startswith(MYS_DOCTYPE_PREFIX):
		try:
			ref = frappe.get_cached_doc(doctype, name)
			branch = getattr(ref, "branch", None)
			campus = getattr(ref, "campus", None)
		except Exception:
			pass

	log_name = log_communication(
		channel="SMS",
		status="Sent",
		subject=f"SMS to {recipient}",
		body=message,
		scope="Individual",
		branch=branch,
		campus=campus,
		recipient_user=recipient if "@" in recipient else None,
	)
	return {"ok": True, "log": log_name, "gateway": "stub"}


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
	)
