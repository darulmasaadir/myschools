"""MYS Branch Health Scorecard — one-row-per-branch overview.

Cross-cut summary for each active Branch: campus + student counts, open
findings, outstanding royalty, and last inspection date. The dashboard
view drives the "which branch needs attention this week" decision for
HO Dept Heads and Cluster Directors.

All sub-queries respect branch-scoped `permission_query_conditions`, so
a Cluster Director sees only her cluster's branches.
"""

import frappe
from frappe import _
from frappe.utils import flt

OPEN_FINDING_STATUSES = ("Open", "In Progress")
OPEN_ROYALTY_STATUSES = ("Unpaid", "Partial", "Overdue")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = _columns()
	rows = _build_rows(filters)
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
		{"fieldname": "active_campuses", "label": _("Active Campuses"), "fieldtype": "Int", "width": 110},
		{"fieldname": "active_students", "label": _("Active Students"), "fieldtype": "Int", "width": 110},
		{"fieldname": "open_findings", "label": _("Open Findings"), "fieldtype": "Int", "width": 110},
		{
			"fieldname": "outstanding_royalty",
			"label": _("Outstanding Royalty"),
			"fieldtype": "Currency",
			"width": 150,
		},
		{"fieldname": "last_inspection", "label": _("Last Inspection"), "fieldtype": "Date", "width": 130},
	]


def _build_rows(filters):
	branch_filters = {"is_active": 1}
	if filters.get("branch"):
		branch_filters["name"] = filters["branch"]
	if filters.get("cluster"):
		branch_filters["cluster"] = filters["cluster"]

	branches = frappe.db.get_all(
		"MYS Branch",
		filters=branch_filters,
		fields=["name", "cluster"],
	)
	branch_names = [b.name for b in branches]
	if not branch_names:
		return []

	active_campuses = _count_by_branch("MYS Campus", branch_names, {"is_active": 1})
	active_students = _count_by_branch(
		"Student",
		branch_names,
		{"enabled": 1},
		branch_field="mys_branch",
	)
	open_findings = _count_by_branch(
		"MYS Inspection Finding",
		branch_names,
		{"status": ["in", OPEN_FINDING_STATUSES]},
	)
	outstanding_royalty = _sum_outstanding_royalty(branch_names)
	last_inspection = _last_inspection_per_branch(branch_names)

	return [
		{
			"branch": b.name,
			"cluster": b.cluster,
			"active_campuses": active_campuses.get(b.name, 0),
			"active_students": active_students.get(b.name, 0),
			"open_findings": open_findings.get(b.name, 0),
			"outstanding_royalty": outstanding_royalty.get(b.name, 0.0),
			"last_inspection": last_inspection.get(b.name),
		}
		for b in sorted(branches, key=lambda x: x.name or "")
	]


def _count_by_branch(doctype, branch_names, extra_filters, branch_field="branch"):
	filters = {branch_field: ["in", branch_names], **extra_filters}
	rows = frappe.db.get_all(
		doctype, filters=filters, fields=[branch_field, "count(*) as ct"], group_by=branch_field
	)
	return {r[branch_field]: r.ct for r in rows}


def _sum_outstanding_royalty(branch_names):
	rows = frappe.db.get_all(
		"MYS Royalty Invoice",
		filters={"branch": ["in", branch_names], "status": ["in", OPEN_ROYALTY_STATUSES]},
		fields=["branch", "sum(outstanding_amount) as outstanding"],
		group_by="branch",
	)
	return {r.branch: flt(r.outstanding) for r in rows}


def _last_inspection_per_branch(branch_names):
	rows = frappe.db.get_all(
		"MYS Inspection Visit",
		filters={"branch": ["in", branch_names]},
		fields=["branch", "max(visit_date) as last_visit"],
		group_by="branch",
	)
	return {r.branch: r.last_visit for r in rows}
