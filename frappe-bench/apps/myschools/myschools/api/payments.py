"""Phase 8e — fee payment initiation with audit logging."""

from __future__ import annotations

import frappe
from frappe import _

from myschools.api.notifications import log_communication
from myschools.api.payment_providers import dispatch_payment


def _resolve_fees_context(fees_name: str) -> dict:
	if not frappe.db.exists("Fees", fees_name):
		frappe.throw(_("Fees {0} not found").format(fees_name))
	fee = frappe.get_cached_doc("Fees", fees_name)
	student = fee.student
	branch = frappe.db.get_value("Student", student, "mys_branch") if student else None
	campus = frappe.db.get_value("Student", student, "mys_campus") if student else None
	currency = frappe.db.get_value("Company", fee.company, "default_currency") if fee.company else "PKR"
	return {
		"fee": fee,
		"branch": branch,
		"campus": campus,
		"currency": currency or "PKR",
	}


@frappe.whitelist()
def initiate_fee_payment(fees: str, amount: float | None = None) -> dict:
	"""Start an online fee payment for a submitted Fees document.

	Returns gateway metadata and an optional ``payment_url`` for the payer redirect.
	All attempts are mirrored into ``MYS Communication Log`` (channel=Payment).
	"""
	ctx = _resolve_fees_context(fees)
	fee = ctx["fee"]
	if fee.docstatus != 1:
		frappe.throw(_("Fees must be submitted before initiating payment"))

	pay_amount = float(amount if amount is not None else fee.outstanding_amount or fee.grand_total or 0)
	if pay_amount <= 0:
		frappe.throw(_("Payment amount must be greater than zero"))

	description = _("Fee payment for {0}").format(fee.name)
	result = dispatch_payment(
		amount=pay_amount,
		currency=ctx["currency"],
		reference=fees,
		description=description,
	)

	status = "Sent" if result.ok else "Failed"
	body = description
	if result.payment_url:
		body = f"{description}\n\nPayment URL: {result.payment_url}"
	if not result.ok:
		body = f"{description}\n\n---\nGateway error: {result.error or 'unknown'}"

	log_name = log_communication(
		channel="Payment",
		status=status,
		subject=f"Payment for {fees}",
		body=body,
		scope="Branch" if ctx["branch"] else "Individual",
		branch=ctx["branch"],
		campus=ctx["campus"],
		gateway=result.gateway,
		provider_reference=result.provider_reference,
	)

	if not result.ok:
		frappe.db.commit()
		frappe.throw(result.error or "Payment dispatch failed")

	return {
		"ok": True,
		"log": log_name,
		"gateway": result.gateway,
		"reference": result.provider_reference,
		"payment_url": result.payment_url,
	}


@frappe.whitelist(allow_guest=True)
def stub_payment_complete(reference: str | None = None, order: str | None = None):
	"""Guest callback used by the Stub provider in dev — confirms the redirect path."""
	frappe.respond_as_web_page(
		_("Payment stub"),
		_("Reference {0} received for order {1}. No funds were collected.").format(
			reference or "-", order or "-"
		),
		indicator_color="green",
	)
