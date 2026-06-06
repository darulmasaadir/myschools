"""Phase 8c — SMS adapter smoke on the live site (run via bench execute).

Exercises the real ``send_sms`` stub path (not mocks) and asserts
``MYS Communication Log`` records ``gateway`` + ``recipient_phone``.

    bench --site SITE execute myschools.scripts.verify_sms_adapters.run
"""

from __future__ import annotations

import frappe

from myschools.api.notifications import send_sms
from myschools.api.sms_providers import dispatch_sms

VERIFY_PHONE = "+9230088c0001"


def run():
	failures: list[str] = []

	if not frappe.db.exists("DocType", "MYS SMS Settings"):
		failures.append("MYS SMS Settings DocType missing — run bench migrate")
	else:
		frappe.db.set_value("MYS SMS Settings", "MYS SMS Settings", "sms_provider", "Stub")

	if not frappe.db.exists("DocType", "MYS Communication Log"):
		failures.append("MYS Communication Log missing")
		meta = frappe.get_meta("MYS Communication Log")
		for field in ("gateway", "recipient_phone", "provider_reference"):
			if not meta.has_field(field):
				failures.append(f"MYS Communication Log missing field: {field}")

	frappe.db.delete("MYS Communication Log", {"recipient_phone": VERIFY_PHONE})
	frappe.db.commit()

	stub = dispatch_sms(VERIFY_PHONE, "verify stub dispatch")
	if not stub.ok or stub.gateway != "stub":
		failures.append(f"dispatch_sms stub failed: ok={stub.ok} gateway={stub.gateway}")

	try:
		out = send_sms(VERIFY_PHONE, "verify sms adapter smoke")
	except Exception as exc:
		failures.append(f"send_sms raised: {exc}")
	else:
		if not out.get("ok"):
			failures.append(f"send_sms returned not ok: {out}")
		if out.get("gateway") != "stub":
			failures.append(f"send_sms gateway={out.get('gateway')}, expected stub")
		row = frappe.db.get_value(
			"MYS Communication Log",
			out.get("log"),
			["status", "gateway", "recipient_phone"],
			as_dict=True,
		)
		if not row:
			failures.append("send_sms log row missing")
		else:
			if row.status != "Sent":
				failures.append(f"log status={row.status}, expected Sent")
			if row.gateway != "stub":
				failures.append(f"log gateway={row.gateway}, expected stub")
			if row.recipient_phone != VERIFY_PHONE:
				failures.append(f"log recipient_phone={row.recipient_phone}")

	if failures:
		print("FAILED —", len(failures), "issue(s):")
		for f in failures:
			print(f"  x {f}")
		frappe.throw("SMS adapter verification failed")
	print("OK — SMS adapters verified (stub dispatch + send_sms audit log)")
