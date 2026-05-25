"""Generate royalty invoices for May 2026 using REAL submitted Fees data.

Reads `tabFees` (Frappe Education) joined on `Student.mys_branch` /
`Student.mys_campus`, runs the rate-resolution logic, and creates a
draft `MYS Royalty Invoice` per active agreement.

Pre-requisite: run `seed_education.run` first so there are submitted
Fees to roll up.

Run via:
  bench --site myschools.localhost execute myschools.scripts.demo_royalty_invoice.run
"""

import frappe

from myschools.api.royalty import generate_monthly_royalty_invoices

PERIOD_YEAR = 2026
PERIOD_MONTH = 5


def run():
	results = generate_monthly_royalty_invoices(year=PERIOD_YEAR, month=PERIOD_MONTH)
	if not results:
		print("No active agreements found. Run seed_demo.run first.")
		return

	print(f"\nRoyalty run for {PERIOD_YEAR}-{PERIOD_MONTH:02d}:")
	for r in results:
		if r.get("skipped"):
			existing = r.get("invoice")
			tag = f" (existing: {existing})" if existing else ""
			print(f"  {r['agreement']:20s}  SKIPPED ({r['skipped']}){tag}")
			if existing:
				_print_invoice(existing)
			continue
		print(
			f"  {r['agreement']:20s}  invoice={r['invoice']}  "
			f"royalty=PKR {r['royalty_amount']:,.2f}  "
			f"weighted_rate={r['effective_rate']:.4f}%"
		)
		_print_invoice(r["invoice"])

	frappe.db.commit()


def _print_invoice(name):
	inv = frappe.get_doc("MYS Royalty Invoice", name)
	print(f"\n  Invoice: {inv.name}")
	print(f"    Branch:           {inv.branch}")
	print(f"    Period:           {inv.period_year}-{inv.period_month}")
	print(f"    Total collection: PKR {inv.total_collection:,.2f}")
	print(f"    Royalty amount:   PKR {inv.royalty_amount:,.2f}")
	print(f"    Effective rate:   {inv.applicable_rate:.4f}%  (weighted across campuses)")
	print(f"    Status:           {inv.status}  (docstatus={inv.docstatus})")
	print("    Per-campus breakdown:")
	for line in inv.campus_lines:
		print(
			f"      {line.campus:20s}  "
			f"collect={line.collection_amount:>12,.0f}  "
			f"rate={line.rate_percent:5.2f}%  "
			f"royalty={line.royalty_amount:>10,.2f}  "
			f"src={line.rate_source}"
		)
