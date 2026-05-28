"""MYS Royalty Aging — aged outstanding by branch.

Reads `MYS Royalty Invoice` rows whose status is one of (Unpaid, Partial,
Overdue), buckets the outstanding amount into 0-30 / 31-60 / 61-90 / 90+
day windows measured against `as_on` (defaults to today), and aggregates
per branch.

Branch-scoped permission_query_conditions on `MYS Royalty Invoice` apply
automatically because we go through `frappe.db.get_all`.
"""

from collections import defaultdict
from datetime import date

import frappe
from frappe import _
from frappe.utils import flt, getdate

OPEN_STATUSES = ("Unpaid", "Partial", "Overdue")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	as_on = getdate(filters.get("as_on") or date.today())

	columns = _columns()
	rows = _aggregate(as_on, filters)
	return columns, rows


def _columns():
	return [
		{
			"fieldname": "branch",
			"label": _("Branch"),
			"fieldtype": "Link",
			"options": "MYS Branch",
			"width": 180,
		},
		{
			"fieldname": "cluster",
			"label": _("Cluster"),
			"fieldtype": "Link",
			"options": "MYS Cluster",
			"width": 140,
		},
		{"fieldname": "outstanding", "label": _("Outstanding"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "b_0_30", "label": _("0-30 days"), "fieldtype": "Currency", "width": 110},
		{"fieldname": "b_31_60", "label": _("31-60 days"), "fieldtype": "Currency", "width": 110},
		{"fieldname": "b_61_90", "label": _("61-90 days"), "fieldtype": "Currency", "width": 110},
		{"fieldname": "b_over_90", "label": _("90+ days"), "fieldtype": "Currency", "width": 110},
		{"fieldname": "oldest_due", "label": _("Oldest Due Date"), "fieldtype": "Date", "width": 120},
		{"fieldname": "invoice_count", "label": _("# Open Invoices"), "fieldtype": "Int", "width": 110},
	]


def _aggregate(as_on, filters):
	invoice_filters = {"status": ["in", OPEN_STATUSES]}
	if filters.get("branch"):
		invoice_filters["branch"] = filters["branch"]
	if filters.get("cluster"):
		invoice_filters["cluster"] = filters["cluster"]

	invoices = frappe.db.get_all(
		"MYS Royalty Invoice",
		filters=invoice_filters,
		fields=["name", "branch", "cluster", "due_date", "outstanding_amount"],
	)

	per_branch = defaultdict(
		lambda: {
			"branch": None,
			"cluster": None,
			"outstanding": 0.0,
			"b_0_30": 0.0,
			"b_31_60": 0.0,
			"b_61_90": 0.0,
			"b_over_90": 0.0,
			"oldest_due": None,
			"invoice_count": 0,
		}
	)

	for inv in invoices:
		amount = flt(inv.outstanding_amount)
		if not amount:
			continue
		row = per_branch[inv.branch]
		row["branch"] = inv.branch
		row["cluster"] = inv.cluster
		row["outstanding"] += amount
		row["invoice_count"] += 1
		if inv.due_date and (row["oldest_due"] is None or inv.due_date < row["oldest_due"]):
			row["oldest_due"] = inv.due_date

		days_overdue = (as_on - getdate(inv.due_date)).days if inv.due_date else 0
		bucket = _bucket_for(days_overdue)
		row[f"b_{bucket}"] += amount

	# Stable order: branch code.
	return sorted(per_branch.values(), key=lambda r: r["branch"] or "")


def _bucket_for(days_overdue):
	if days_overdue <= 30:
		return "0_30"
	if days_overdue <= 60:
		return "31_60"
	if days_overdue <= 90:
		return "61_90"
	return "over_90"
