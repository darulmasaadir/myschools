"""Branch portal data access — scoped to the logged-in user's MYS Branch.

Branch staff (Director / Principal / Admin / Accountant / Campus Incharge) have an
``Employee`` row whose ``user_id`` matches their login and whose ``mys_branch`` is set.
Every query here resolves that branch and returns only rows belonging to it.

This module never relies on ``permission_query_conditions`` for the data it
exposes — it uses ``ignore_permissions=True`` after an explicit branch filter, so
the portal page renders consistently regardless of whether a doctype is wired into
the franchise permission scoping.
"""

from __future__ import annotations

from datetime import date

import frappe
from frappe.utils import flt, getdate, nowdate

BRANCH_ROLES = frozenset(
	{
		"Branch Director",
		"Branch Principal",
		"Branch Admin",
		"Branch Accountant",
		"Campus Incharge",
	}
)


def require_branch_role() -> None:
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/branch"
		raise frappe.Redirect
	if not BRANCH_ROLES & set(frappe.get_roles()):
		frappe.throw("You do not have access to the Branch portal.", frappe.PermissionError)


def get_branch_for_user(user: str | None = None) -> str:
	"""Return the MYS Branch name the user is staff at, or throw with a friendly error."""
	user = user or frappe.session.user
	if user == "Guest":
		frappe.throw("Sign in required.", frappe.PermissionError)
	branch = frappe.db.get_value(
		"Employee",
		{"user_id": user, "status": "Active"},
		"mys_branch",
	) or frappe.db.get_value("Employee", {"user_id": user}, "mys_branch")
	if not branch:
		frappe.throw(
			"No active Employee record with a branch is linked to your login. "
			"Please ask Head Office to assign your branch.",
			frappe.PermissionError,
		)
	return branch


def get_branch_detail(branch: str) -> dict:
	row = frappe.db.get_value(
		"MYS Branch",
		branch,
		[
			"name",
			"branch_name",
			"branch_code",
			"cluster",
			"branch_director",
			"branch_principal",
			"branch_admin",
			"branch_accountant",
			"address_line_1",
			"city",
			"province",
			"phone",
			"email",
		],
		as_dict=True,
	) or {"name": branch, "branch_name": branch}
	row["campus_count"] = frappe.db.count("MYS Campus", {"branch": branch})
	row["student_count"] = frappe.db.count("Student", {"mys_branch": branch})
	row["staff_count"] = frappe.db.count("Employee", {"mys_branch": branch, "status": "Active"})
	return row


def get_findings_for_branch(
	branch: str,
	statuses: tuple[str, ...] | None = ("Open", "In Progress"),
	limit: int = 50,
) -> list[dict]:
	filters: dict = {"branch": branch, "docstatus": ["<", 2]}
	if statuses:
		filters["status"] = ["in", list(statuses)]
	rows = frappe.get_all(
		"MYS Inspection Finding",
		filters=filters,
		fields=[
			"name",
			"visit",
			"severity",
			"category",
			"status",
			"description",
			"due_date",
			"reported_on",
		],
		order_by="due_date asc, modified desc",
		limit=limit,
		ignore_permissions=True,
	)
	today = getdate(nowdate())
	for row in rows:
		row["is_overdue"] = bool(row.due_date and getdate(row.due_date) < today)
	return rows


def get_findings_summary(branch: str) -> dict:
	open_rows = get_findings_for_branch(branch, statuses=("Open", "In Progress"), limit=500)
	overdue = sum(1 for r in open_rows if r.get("is_overdue"))
	by_severity = {"Critical": 0, "Major": 0, "Minor": 0}
	for row in open_rows:
		sev = row.get("severity")
		if sev in by_severity:
			by_severity[sev] += 1
	return {
		"open_total": len(open_rows),
		"overdue_total": overdue,
		"by_severity": by_severity,
	}


def get_royalty_for_branch(branch: str, limit: int = 24) -> list[dict]:
	rows = frappe.get_all(
		"MYS Royalty Invoice",
		filters={"branch": branch, "docstatus": ["<", 2]},
		fields=[
			"name",
			"period_year",
			"period_month",
			"invoice_date",
			"due_date",
			"status",
			"royalty_amount",
			"paid_amount",
			"outstanding_amount",
			"currency",
		],
		order_by="period_year desc, period_month desc",
		limit=limit,
		ignore_permissions=True,
	)
	today = getdate(nowdate())
	for row in rows:
		row["is_overdue"] = bool(
			row.due_date and getdate(row.due_date) < today and flt(row.outstanding_amount) > 0
		)
		row["period_label"] = _format_period(row.get("period_year"), row.get("period_month"))
	return rows


def _format_period(year, month) -> str:
	"""Render '2026-04' from string/int year + month inputs (defensive)."""
	try:
		month_int = int(str(month)) if month not in (None, "") else 0
	except (TypeError, ValueError):
		month_int = 0
	year_str = str(year or "").strip() or "—"
	if month_int:
		return f"{year_str}-{month_int:02d}"
	return year_str


def get_royalty_summary(branch: str) -> dict:
	rows = get_royalty_for_branch(branch, limit=500)
	outstanding = sum(flt(r.outstanding_amount) for r in rows)
	overdue = sum(flt(r.outstanding_amount) for r in rows if r.get("is_overdue"))
	currency = next((r.currency for r in rows if r.currency), None)
	return {
		"outstanding": outstanding,
		"overdue": overdue,
		"currency": currency,
		"invoice_count": len(rows),
	}


def get_fees_for_branch(branch: str, days: int = 90, limit: int = 100) -> list[dict]:
	student_ids = frappe.get_all("Student", filters={"mys_branch": branch}, pluck="name")
	if not student_ids:
		return []
	from frappe.utils import add_days

	from_date = add_days(nowdate(), -days)
	rows = frappe.get_all(
		"Fees",
		filters={
			"student": ["in", student_ids],
			"docstatus": 1,
			"posting_date": [">=", from_date],
		},
		fields=[
			"name",
			"student",
			"student_name",
			"posting_date",
			"due_date",
			"grand_total",
			"outstanding_amount",
		],
		order_by="posting_date desc",
		limit=limit,
		ignore_permissions=True,
	)
	for row in rows:
		row["paid_amount"] = flt(row.grand_total) - flt(row.outstanding_amount)
	return rows


def get_fees_summary(branch: str) -> dict:
	student_ids = frappe.get_all("Student", filters={"mys_branch": branch}, pluck="name")
	if not student_ids:
		return {
			"collected_mtd": 0,
			"outstanding_total": 0,
			"invoice_count": 0,
			"student_count": 0,
		}
	month_start = date.today().replace(day=1).isoformat()
	collected_mtd = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(grand_total - outstanding_amount), 0)
		FROM `tabFees`
		WHERE student IN %(students)s AND docstatus = 1 AND posting_date >= %(month_start)s
		""",
		{"students": tuple(student_ids), "month_start": month_start},
	)[0][0]
	outstanding_total = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(outstanding_amount), 0)
		FROM `tabFees`
		WHERE student IN %(students)s AND docstatus = 1
		""",
		{"students": tuple(student_ids)},
	)[0][0]
	invoice_count = frappe.db.count("Fees", {"student": ["in", student_ids], "docstatus": 1})
	return {
		"collected_mtd": flt(collected_mtd),
		"outstanding_total": flt(outstanding_total),
		"invoice_count": invoice_count,
		"student_count": len(student_ids),
	}


def populate_branch_context(context) -> str:
	"""Shared context for all /branch/* pages. Returns the resolved branch name."""
	require_branch_role()
	branch = get_branch_for_user()
	context.no_cache = 1
	context.show_sidebar = 0
	context.branch_name = branch
	context.branch = get_branch_detail(branch)
	context.nav_items = [
		{"label": "Dashboard", "route": "/branch"},
		{"label": "Findings", "route": "/branch/findings"},
		{"label": "Royalty", "route": "/branch/royalty"},
		{"label": "Fees", "route": "/branch/fees"},
		{"label": "Timetable", "route": "/branch/timetable"},
	]
	return branch
