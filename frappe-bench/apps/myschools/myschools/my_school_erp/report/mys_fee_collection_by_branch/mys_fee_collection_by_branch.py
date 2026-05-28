"""MYS Fee Collection by Branch — billed vs. collected per branch.

Aggregates submitted `Fees` rows by the student's `mys_branch` (a custom
field). Reports billed, paid, outstanding and collection rate per branch.
Filters: `from_date`, `to_date`, optional `branch` / `cluster`.

The join is Fees.student -> Student.mys_branch -> MYS Branch.cluster, so
unsubmitted (draft) Fees and Fees against students without a branch link
are excluded — the reader sees only invoiced, posted revenue.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	to_date = getdate(filters.get("to_date") or nowdate())
	from_date = getdate(filters.get("from_date") or to_date.replace(month=1, day=1))

	columns = _columns()
	rows = _aggregate(from_date, to_date, filters)
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
		{"fieldname": "fee_count", "label": _("# Fee Invoices"), "fieldtype": "Int", "width": 110},
		{"fieldname": "billed", "label": _("Billed"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "paid", "label": _("Paid"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "outstanding", "label": _("Outstanding"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "collection_rate", "label": _("Collection %"), "fieldtype": "Percent", "width": 110},
	]


def _aggregate(from_date, to_date, filters):
	conditions = ["fees.docstatus = 1", "fees.posting_date BETWEEN %(from_date)s AND %(to_date)s"]
	params = {"from_date": from_date, "to_date": to_date}

	if filters.get("branch"):
		conditions.append("student.mys_branch = %(branch)s")
		params["branch"] = filters["branch"]
	if filters.get("cluster"):
		conditions.append("student.mys_cluster = %(cluster)s")
		params["cluster"] = filters["cluster"]

	where = " AND ".join(conditions)

	# Inner join — fees with a NULL student or branch get dropped (rare:
	# manually-entered Fees with no student picker).
	# `Fees` doesn't track a paid_amount column — derive it from
	# grand_total - outstanding_amount.
	sql = f"""
		SELECT
			student.mys_branch  AS branch,
			student.mys_cluster AS cluster,
			fees.grand_total    AS billed,
			(fees.grand_total - fees.outstanding_amount) AS paid,
			fees.outstanding_amount AS outstanding
		FROM `tabFees` fees
		INNER JOIN `tabStudent` student ON student.name = fees.student
		WHERE {where} AND student.mys_branch IS NOT NULL AND student.mys_branch != ''
	"""

	per_branch = defaultdict(
		lambda: {
			"branch": None,
			"cluster": None,
			"fee_count": 0,
			"billed": 0.0,
			"paid": 0.0,
			"outstanding": 0.0,
			"collection_rate": 0.0,
		}
	)

	for r in frappe.db.sql(sql, params, as_dict=True):
		row = per_branch[r.branch]
		row["branch"] = r.branch
		row["cluster"] = r.cluster
		row["fee_count"] += 1
		row["billed"] += flt(r.billed)
		row["paid"] += flt(r.paid)
		row["outstanding"] += flt(r.outstanding)

	for row in per_branch.values():
		row["collection_rate"] = (row["paid"] / row["billed"] * 100.0) if row["billed"] else 0.0

	return sorted(per_branch.values(), key=lambda r: r["branch"] or "")
