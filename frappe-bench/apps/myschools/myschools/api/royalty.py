"""Royalty calculation and invoice generation.

Rate resolution order (highest priority first):
  1. Campus-level Rate Override (effective on the billing date)
  2. Branch-level Rate Override   (effective on the billing date)
  3. Agreement default_royalty_rate

This implements the user's requirement: "seven percent should not be fixed.
It should be configurable, and it can vary from campus to campus or maybe
from branch to branch. It should be fully customizable."
"""

import calendar
from datetime import date

import frappe
from frappe.utils import add_days, flt, get_first_day, get_last_day, getdate, today


def resolve_royalty_rate(
	agreement: str, branch: str, campus: str | None = None, on_date=None
) -> tuple[float, str]:
	"""Returns (rate_percent, source) where source is one of:
	'campus_override' | 'branch_override' | 'agreement_default'.

	Rate precedence: campus override > branch override > agreement default.
	"""
	on_date = getdate(on_date or today())

	if campus:
		campus_rate = _lookup_override(agreement=agreement, branch=branch, campus=campus, on_date=on_date)
		if campus_rate is not None:
			return campus_rate, "campus_override"

	branch_rate = _lookup_override(agreement=agreement, branch=branch, campus=None, on_date=on_date)
	if branch_rate is not None:
		return branch_rate, "branch_override"

	default_rate = frappe.db.get_value("MYS Franchise Agreement", agreement, "default_royalty_rate")
	return flt(default_rate or 0), "agreement_default"


def _lookup_override(agreement, branch, campus, on_date):
	filters = {
		"agreement": agreement,
		"branch": branch,
		"is_active": 1,
		"effective_from": ["<=", on_date],
	}
	if campus:
		filters["campus"] = campus
	else:
		filters["campus"] = ["in", ["", None]]

	candidates = frappe.get_all(
		"MYS Royalty Rate Override",
		filters=filters,
		fields=["name", "rate_percent", "effective_from", "effective_to"],
		order_by="effective_from DESC",
		limit=10,
	)
	for c in candidates:
		if c.effective_to and getdate(c.effective_to) < on_date:
			continue
		return flt(c.rate_percent)
	return None


def get_branch_collection_for_period(branch: str, year: int, month: int) -> dict:
	"""Returns {campus: collection_amount} for the given branch/period.

	Currently sums submitted Fees (Frappe Education) by student.mys_campus
	for posting_date within the month. If the Fees DocType is absent (fresh
	install before any fee records exist), returns an empty dict.
	"""
	year = int(year)
	month = int(month)
	first = date(year, month, 1)
	last = date(year, month, calendar.monthrange(year, month)[1])

	if not frappe.db.table_exists("Fees"):
		return {}

	rows = frappe.db.sql(
		"""
		SELECT s.mys_campus AS campus, COALESCE(SUM(f.grand_total), 0) AS amount
		FROM `tabFees` f
		LEFT JOIN `tabStudent` s ON s.name = f.student
		WHERE s.mys_branch = %s
		  AND f.docstatus = 1
		  AND f.posting_date BETWEEN %s AND %s
		GROUP BY s.mys_campus
		""",
		(branch, first, last),
		as_dict=True,
	)
	return {(r.campus or ""): flt(r.amount) for r in rows}


def generate_monthly_royalty_invoices(
	year: int | None = None, month: int | None = None, dry_run: bool = False
):
	"""Generate (or preview) royalty invoices for every Active agreement.

	Defaults to the previous month so it can be safely scheduled on day 1.
	"""
	today_d = getdate(today())
	if not year or not month:
		# previous month
		first_of_this_month = get_first_day(today_d)
		prev = add_days(first_of_this_month, -1)
		year = year or prev.year
		month = month or prev.month

	year = int(year)
	month = int(month)
	period_year = str(year)
	period_month = f"{month:02d}"

	agreements = frappe.get_all(
		"MYS Franchise Agreement",
		filters={"status": "Active", "docstatus": 1},
		fields=[
			"name",
			"franchisee",
			"branch",
			"company",
			"billing_day",
			"grace_days",
			"default_royalty_rate",
		],
	)

	results = []
	billing_date = date(year, month, calendar.monthrange(year, month)[1])

	for ag in agreements:
		existing = frappe.db.exists(
			"MYS Royalty Invoice",
			{
				"agreement": ag.name,
				"period_year": period_year,
				"period_month": period_month,
				"docstatus": ["<", 2],
			},
		)
		if existing:
			results.append({"agreement": ag.name, "skipped": "already_exists", "invoice": existing})
			continue

		collections = get_branch_collection_for_period(ag.branch, year, month)
		campuses = frappe.get_all(
			"MYS Campus",
			filters={"branch": ag.branch},
			fields=["name", "campus_type"],
		)
		if not campuses:
			results.append({"agreement": ag.name, "skipped": "no_campuses"})
			continue

		invoice = frappe.new_doc("MYS Royalty Invoice")
		invoice.agreement = ag.name
		invoice.franchisee = ag.franchisee
		invoice.branch = ag.branch
		invoice.company = ag.company
		invoice.period_year = period_year
		invoice.period_month = period_month
		invoice.invoice_date = today()
		invoice.due_date = add_days(today(), int(ag.grace_days or 10))
		invoice.auto_generated = 1
		invoice.generated_by = frappe.session.user

		for c in campuses:
			rate, source = resolve_royalty_rate(
				agreement=ag.name, branch=ag.branch, campus=c.name, on_date=billing_date
			)
			collection = flt(collections.get(c.name, 0))
			invoice.append(
				"campus_lines",
				{
					"campus": c.name,
					"campus_type": c.campus_type,
					"collection_amount": collection,
					"rate_percent": rate,
					"rate_source": source,
				},
			)

		if dry_run:
			invoice.run_method("validate")
			results.append(
				{
					"agreement": ag.name,
					"branch": ag.branch,
					"total_collection": invoice.total_collection,
					"royalty_amount": invoice.royalty_amount,
					"effective_rate": invoice.applicable_rate,
					"would_create": True,
				}
			)
			continue

		invoice.insert(ignore_permissions=True)
		results.append(
			{
				"agreement": ag.name,
				"branch": ag.branch,
				"invoice": invoice.name,
				"royalty_amount": invoice.royalty_amount,
				"effective_rate": invoice.applicable_rate,
			}
		)

	frappe.db.commit()
	return results


def scheduled_monthly_royalty_run():
	"""Hook: monthly job. Generates invoices for the previous month."""
	try:
		results = generate_monthly_royalty_invoices()
		frappe.logger().info(f"[myschools.royalty] Generated {len(results)} royalty invoices: {results}")
	except Exception:
		frappe.log_error(frappe.get_traceback(), "myschools.royalty.scheduled_monthly_royalty_run")
		raise


def royalty_invoice_query(user):
	"""permission_query_conditions for MYS Royalty Invoice — branch-scoped."""
	from myschools.api.permissions import _user_scope

	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Royalty Invoice`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Royalty Invoice`.branch IN ({in_list})"


def royalty_payment_query(user):
	from myschools.api.permissions import _user_scope

	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Royalty Payment`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Royalty Payment`.branch IN ({in_list})"


def franchise_agreement_query(user):
	from myschools.api.permissions import _user_scope

	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Franchise Agreement`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Franchise Agreement`.branch IN ({in_list})"


def rate_override_query(user):
	from myschools.api.permissions import _user_scope

	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Royalty Rate Override`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Royalty Rate Override`.branch IN ({in_list})"
