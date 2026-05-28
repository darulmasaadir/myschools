"""MYS Findings by Branch and Severity — pivot of open findings.

Pivots `MYS Inspection Finding` by branch (rows) x severity (cols).
Default `status` filter is "Open"; the operator can switch to In Progress
/ Resolved / Verified to inspect lifecycle progress per branch.

Branch scoping inherits from the doctype's
`permission_query_conditions`, so a Cluster Director only sees branches
under her cluster, a Branch Director only sees his own branch.
"""

from collections import defaultdict

import frappe
from frappe import _

SEVERITIES = ("Critical", "Major", "Minor")
DEFAULT_OPEN_STATUSES = ("Open", "In Progress")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = _columns()
	rows = _aggregate(filters)
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
		{"fieldname": "critical", "label": _("Critical"), "fieldtype": "Int", "width": 90},
		{"fieldname": "major", "label": _("Major"), "fieldtype": "Int", "width": 90},
		{"fieldname": "minor", "label": _("Minor"), "fieldtype": "Int", "width": 90},
		{"fieldname": "total", "label": _("Total"), "fieldtype": "Int", "width": 90},
	]


def _aggregate(filters):
	status_filter = filters.get("status")
	if status_filter:
		finding_filters = {"status": status_filter}
	else:
		finding_filters = {"status": ["in", DEFAULT_OPEN_STATUSES]}

	if filters.get("branch"):
		finding_filters["branch"] = filters["branch"]

	findings = frappe.db.get_all(
		"MYS Inspection Finding",
		filters=finding_filters,
		fields=["branch", "severity"],
	)

	per_branch = defaultdict(lambda: {"branch": None, "critical": 0, "major": 0, "minor": 0, "total": 0})
	for f in findings:
		if not f.branch:
			continue
		row = per_branch[f.branch]
		row["branch"] = f.branch
		col = (f.severity or "").lower()
		if col in ("critical", "major", "minor"):
			row[col] += 1
			row["total"] += 1

	return sorted(per_branch.values(), key=lambda r: r["branch"] or "")
