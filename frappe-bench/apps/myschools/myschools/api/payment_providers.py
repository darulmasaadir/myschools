"""Phase 8e — pluggable fee-payment gateways (Pakistani providers).

Providers are selected via the ``MYS Payment Settings`` single.
``initiate_fee_payment`` in ``api/payments.py`` calls :func:`dispatch_payment`
so callers keep a stable signature when gateways change.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils.password import get_decrypted_password


@dataclass(frozen=True)
class PaymentDispatchResult:
	ok: bool
	gateway: str
	provider_reference: str | None = None
	payment_url: str | None = None
	error: str | None = None


def get_payment_settings() -> frappe.Document:
	if frappe.db.exists("DocType", "MYS Payment Settings"):
		return frappe.get_single("MYS Payment Settings")
	return frappe._dict({"payment_provider": "Stub"})


def dispatch_payment(
	*,
	amount: float,
	currency: str,
	reference: str,
	description: str,
	return_url: str | None = None,
) -> PaymentDispatchResult:
	"""Route a fee payment initiation through the configured provider."""
	settings = get_payment_settings()
	provider = (settings.payment_provider or "Stub").strip()

	if provider == "JazzCash":
		return _send_jazzcash(settings, amount, currency, reference, description, return_url)
	if provider == "Easypaisa":
		return _send_easypaisa(settings, amount, currency, reference, description, return_url)
	if provider == "HBL":
		return _send_hbl(settings, amount, currency, reference, description, return_url)
	return _send_stub(reference, amount, currency)


def _send_stub(reference: str, amount: float, currency: str) -> PaymentDispatchResult:
	ref = f"STUB-PAY-{uuid.uuid4().hex[:12].upper()}"
	return PaymentDispatchResult(
		ok=True,
		gateway="stub",
		provider_reference=ref,
		payment_url=f"/api/method/myschools.api.payments.stub_payment_complete?reference={ref}&order={reference}",
	)


def _gateway_post(url: str, payload: dict) -> PaymentDispatchResult:
	import requests

	try:
		response = requests.post(url, json=payload, timeout=30)
	except requests.RequestException as exc:
		return PaymentDispatchResult(ok=False, gateway="http", error=str(exc))
	if response.status_code >= 400:
		return PaymentDispatchResult(
			ok=False,
			gateway="http",
			error=response.text[:500] or f"HTTP {response.status_code}",
		)
	try:
		data = response.json()
	except ValueError:
		data = {}
	ref = data.get("transaction_id") or data.get("pp_TxnRefNo") or data.get("reference")
	payment_url = data.get("payment_url") or data.get("redirect_url") or data.get("checkout_url")
	return PaymentDispatchResult(
		ok=True,
		gateway="http",
		provider_reference=str(ref) if ref else None,
		payment_url=payment_url,
	)


def _send_jazzcash(
	settings,
	amount: float,
	currency: str,
	reference: str,
	description: str,
	return_url: str | None,
) -> PaymentDispatchResult:
	merchant_id = (settings.jazzcash_merchant_id or "").strip()
	callback = (return_url or settings.jazzcash_return_url or "").strip()
	password = ""
	if merchant_id:
		try:
			password = get_decrypted_password(
				"MYS Payment Settings", "MYS Payment Settings", "jazzcash_password"
			)
		except frappe.ValidationError:
			password = ""
	if not all([merchant_id, password]):
		return PaymentDispatchResult(
			ok=False,
			gateway="jazzcash",
			error=_("JazzCash is selected but Merchant ID or Password is missing."),
		)
	pp_ref = f"MYS-{reference}-{uuid.uuid4().hex[:8]}"
	payload = {
		"pp_MerchantID": merchant_id,
		"pp_Amount": int(amount * 100),
		"pp_TxnCurrency": currency,
		"pp_TxnRefNo": pp_ref,
		"pp_Description": description[:200],
		"pp_ReturnURL": callback,
	}
	# Production URL is configured per deployment; tests mock requests.post.
	url = frappe.conf.get("mys_jazzcash_api_url") or "https://sandbox.jazzcash.com.pk/ApplicationAPI/API/2.0/Purchase/DoMWalletTransaction"
	result = _gateway_post(url, payload)
	if not result.ok:
		return PaymentDispatchResult(ok=False, gateway="jazzcash", error=result.error)
	return PaymentDispatchResult(
		ok=True,
		gateway="jazzcash",
		provider_reference=result.provider_reference or pp_ref,
		payment_url=result.payment_url,
	)


def _send_easypaisa(
	settings,
	amount: float,
	currency: str,
	reference: str,
	description: str,
	return_url: str | None,
) -> PaymentDispatchResult:
	store_id = (settings.easypaisa_store_id or "").strip()
	callback = (return_url or settings.easypaisa_return_url or "").strip()
	hash_key = ""
	if store_id:
		try:
			hash_key = get_decrypted_password(
				"MYS Payment Settings", "MYS Payment Settings", "easypaisa_hash_key"
			)
		except frappe.ValidationError:
			hash_key = ""
	if not all([store_id, hash_key]):
		return PaymentDispatchResult(
			ok=False,
			gateway="easypaisa",
			error=_("Easypaisa is selected but Store ID or Hash Key is missing."),
		)
	order_ref = f"MYS-{reference}-{uuid.uuid4().hex[:8]}"
	signature = hashlib.sha256(f"{store_id}{order_ref}{amount}{hash_key}".encode()).hexdigest()
	payload = {
		"storeId": store_id,
		"orderRefNum": order_ref,
		"amount": amount,
		"currency": currency,
		"description": description[:200],
		"returnUrl": callback,
		"signature": signature,
	}
	url = frappe.conf.get("mys_easypaisa_api_url") or "https://easypay.easypaisa.com.pk/easypay/Index.jsf"
	result = _gateway_post(url, payload)
	if not result.ok:
		return PaymentDispatchResult(ok=False, gateway="easypaisa", error=result.error)
	return PaymentDispatchResult(
		ok=True,
		gateway="easypaisa",
		provider_reference=result.provider_reference or order_ref,
		payment_url=result.payment_url,
	)


def _send_hbl(
	settings,
	amount: float,
	currency: str,
	reference: str,
	description: str,
	return_url: str | None,
) -> PaymentDispatchResult:
	merchant_id = (settings.hbl_merchant_id or "").strip()
	callback = (return_url or settings.hbl_return_url or "").strip()
	secret = ""
	if merchant_id:
		try:
			secret = get_decrypted_password("MYS Payment Settings", "MYS Payment Settings", "hbl_secret_key")
		except frappe.ValidationError:
			secret = ""
	if not all([merchant_id, secret]):
		return PaymentDispatchResult(
			ok=False,
			gateway="hbl",
			error=_("HBL is selected but Merchant ID or Secret Key is missing."),
		)
	order_ref = f"MYS-{reference}-{uuid.uuid4().hex[:8]}"
	payload = {
		"merchant_id": merchant_id,
		"order_reference": order_ref,
		"amount": amount,
		"currency": currency,
		"description": description[:200],
		"return_url": callback,
	}
	url = frappe.conf.get("mys_hbl_api_url") or "https://sandbox.hbl.com/payment/v1/initiate"
	result = _gateway_post(url, payload)
	if not result.ok:
		return PaymentDispatchResult(ok=False, gateway="hbl", error=result.error)
	return PaymentDispatchResult(
		ok=True,
		gateway="hbl",
		provider_reference=result.provider_reference or order_ref,
		payment_url=result.payment_url,
	)
