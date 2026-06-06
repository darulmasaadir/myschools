"""Phase 8e — payment adapter smoke on the live site (run via bench execute).

    bench --site SITE execute myschools.scripts.verify_payment_adapters.run
"""

from __future__ import annotations

import frappe

from myschools.api.payment_providers import dispatch_payment

VERIFY_REF = "VERIFY-PAY-8E-001"


def run():
	failures: list[str] = []

	if not frappe.db.exists("DocType", "MYS Payment Settings"):
		failures.append("MYS Payment Settings DocType missing — run bench migrate")
	else:
		frappe.db.set_value("MYS Payment Settings", "MYS Payment Settings", "payment_provider", "Stub")

	meta = frappe.get_meta("MYS Communication Log")
	if "Payment" not in (meta.get_field("channel").options or ""):
		failures.append("MYS Communication Log channel missing Payment option")
	for field in ("gateway", "provider_reference"):
		if not meta.has_field(field):
			failures.append(f"MYS Communication Log missing field: {field}")

	frappe.db.delete("MYS Communication Log", {"provider_reference": ["like", "STUB-PAY-%"]})
	frappe.db.commit()

	result = dispatch_payment(
		amount=100.0,
		currency="PKR",
		reference=VERIFY_REF,
		description="verify payment adapter smoke",
	)
	if not result.ok or result.gateway != "stub":
		failures.append(f"dispatch_payment stub failed: ok={result.ok} gateway={result.gateway}")

	if failures:
		print("FAILED —", len(failures), "issue(s):")
		for f in failures:
			print(f"  x {f}")
		frappe.throw("Payment adapter verification failed")
	print("OK — payment adapters verified (stub dispatch)")
