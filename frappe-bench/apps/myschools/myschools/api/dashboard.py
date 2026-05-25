"""Whitelisted Number Card endpoints feeding the MYS Central Monitoring Dashboard.

Each function returns the shape Frappe's Number Card system expects when the
card's `type` is `Custom`:

    {"value": <number>, "fieldtype": "Currency"|"Int", ["currency": "PKR"]}

Branch scoping:
- Number Cards backed by `type="Document Type"` (Active Branches, Active Students,
  Outstanding Royalty, Overdue Invoices, Open Findings) are automatically scoped
  through Frappe's `permission_query_conditions` registered in [`hooks.py`](../hooks.py).
- The custom-method endpoints below apply `_branch_scope_sql` directly so the
  same dashboard works for a Branch Admin (single branch) and the CE (national).
"""

import frappe
from frappe.utils import flt, get_first_day, get_last_day, getdate, today

CURRENCY = "PKR"


@frappe.whitelist()
def current_month_royalty_invoiced():
	"""Sum of `royalty_amount` on submitted royalty invoices for the current period."""
	period_year, period_month = _current_period()
	branch_clause, branch_params = _branch_scope_sql("branch")
	if branch_clause == "DENY":
		return {"value": 0, "fieldtype": "Currency", "currency": CURRENCY}
	value = frappe.db.sql(
		f"""
		SELECT COALESCE(SUM(royalty_amount), 0)
		FROM `tabMYS Royalty Invoice`
		WHERE period_year = %s AND period_month = %s AND docstatus = 1
		  {branch_clause}
		""",
		(period_year, period_month, *branch_params),
	)[0][0]
	return {"value": flt(value), "fieldtype": "Currency", "currency": CURRENCY}


@frappe.whitelist()
def current_month_fees_collected():
	"""Sum of `grand_total` on submitted `Fees` whose posting_date falls in the current month.

	Joins through `Student.mys_branch` and applies the user's branch scope so
	the card means "fees collected in **my** branches this month".
	"""
	first = get_first_day(today())
	last = get_last_day(today())
	if not frappe.db.table_exists("Fees"):
		return {"value": 0, "fieldtype": "Currency", "currency": CURRENCY}

	branch_clause, branch_params = _branch_scope_sql("s.mys_branch")
	if branch_clause == "DENY":
		return {"value": 0, "fieldtype": "Currency", "currency": CURRENCY}

	value = frappe.db.sql(
		f"""
		SELECT COALESCE(SUM(f.grand_total), 0)
		FROM `tabFees` f
		LEFT JOIN `tabStudent` s ON s.name = f.student
		WHERE f.docstatus = 1
		  AND f.posting_date BETWEEN %s AND %s
		  {branch_clause}
		""",
		(first, last, *branch_params),
	)[0][0]
	return {"value": flt(value), "fieldtype": "Currency", "currency": CURRENCY}


@frappe.whitelist()
def overdue_findings_count():
	"""Inspection findings past their due_date that aren't yet Resolved/Verified.

	Uses `frappe.db.count` so Frappe applies the `MYS Inspection Finding`
	permission query automatically.
	"""
	count = frappe.db.count(
		"MYS Inspection Finding",
		filters={
			"due_date": ["<", today()],
			"status": ["not in", ["Resolved", "Verified"]],
		},
	)
	return {"value": int(count), "fieldtype": "Int"}


def _current_period() -> tuple[str, str]:
	d = getdate(today())
	return str(d.year), f"{d.month:02d}"


def _branch_scope_sql(column: str) -> tuple[str, list]:
	"""SQL fragment + params restricting `column` to the user's visible branches.

	Returns:
	  ("", []) for global users (no extra filter).
	  ("AND <column> IN (%s, ...)", [branch, ...]) for cluster/branch users.
	  ("DENY", []) for users with no franchise scope (sentinel: caller short-circuits).
	"""
	from myschools.api.permissions import _user_scope

	scope, branches = _user_scope(frappe.session.user)
	if scope == "global":
		return "", []
	if scope == "none" or not branches:
		return "DENY", []
	placeholders = ", ".join(["%s"] * len(branches))
	return f"AND {column} IN ({placeholders})", list(branches)
