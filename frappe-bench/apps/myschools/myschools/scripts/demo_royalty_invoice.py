"""Build one royalty invoice with synthetic per-campus collection numbers,
so we can see the per-campus rate math in a real submitted document.

Run via:
  bench --site myschools.localhost execute myschools.scripts.demo_royalty_invoice.run
"""

import frappe
from frappe.utils import add_days, today

from myschools.api.royalty import resolve_royalty_rate


def run():
	# Find the BR014 agreement (the one with the campus override)
	ag_name = frappe.db.get_value(
		"MYS Franchise Agreement",
		{"branch": "BR014", "status": "Active", "docstatus": 1},
		"name",
	)
	if not ag_name:
		print("No active agreement for BR014. Run seed_demo first.")
		return

	# Synthetic collection: PKR 1.5M Kids, 2.0M Junior, 3.0M Senior
	collections = {
		"BR014-Kids": 1_500_000,
		"BR014-Junior": 2_000_000,
		"BR014-Senior": 3_000_000,
	}

	# Skip if an invoice for this period already exists.
	# Using May 2026 so the override (effective_from = 2026-05-25) is in scope
	# for the billing date (last day of May).
	period_year = "2026"
	period_month = "05"
	existing = frappe.db.exists(
		"MYS Royalty Invoice",
		{
			"agreement": ag_name,
			"period_year": period_year,
			"period_month": period_month,
			"docstatus": ["<", 2],
		},
	)
	if existing:
		print(f"Invoice already exists: {existing}")
		_print_invoice(existing)
		return

	ag = frappe.get_doc("MYS Franchise Agreement", ag_name)
	inv = frappe.new_doc("MYS Royalty Invoice")
	inv.agreement = ag.name
	inv.branch = ag.branch
	inv.company = ag.company
	inv.period_year = period_year
	inv.period_month = period_month
	inv.invoice_date = today()
	inv.due_date = add_days(today(), int(ag.grace_days or 10))
	inv.auto_generated = 0
	inv.generated_by = "demo_royalty_invoice"

	from datetime import date

	billing_date = date(2026, 5, 31)
	for campus_name, amount in collections.items():
		campus_doc = frappe.db.get_value("MYS Campus", campus_name, "campus_type")
		rate, source = resolve_royalty_rate(ag.name, ag.branch, campus_name, on_date=billing_date)
		inv.append(
			"campus_lines",
			{
				"campus": campus_name,
				"campus_type": campus_doc,
				"collection_amount": amount,
				"rate_percent": rate,
				"rate_source": source,
			},
		)

	inv.insert(ignore_permissions=True)
	inv.submit()
	frappe.db.commit()
	print(f"Created and submitted: {inv.name}")
	_print_invoice(inv.name)


def _print_invoice(name):
	inv = frappe.get_doc("MYS Royalty Invoice", name)
	print(f"\nInvoice: {inv.name}")
	print(f"  Branch:           {inv.branch}")
	print(f"  Period:           {inv.period_year}-{inv.period_month}")
	print(f"  Total collection: PKR {inv.total_collection:,.2f}")
	print(f"  Royalty amount:   PKR {inv.royalty_amount:,.2f}")
	print(f"  Effective rate:   {inv.applicable_rate:.4f}%  (weighted across campuses)")
	print(f"  Status:           {inv.status}")
	print("\n  Per-campus breakdown:")
	for line in inv.campus_lines:
		print(
			f"    {line.campus:20s}  "
			f"collect={line.collection_amount:>12,.0f}  "
			f"rate={line.rate_percent:5.2f}%  "
			f"royalty={line.royalty_amount:>10,.2f}  "
			f"src={line.rate_source}"
		)
