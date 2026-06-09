"""Phase 14 — Document management: branch-scoped registry wrapping Frappe File.

``MYS Document`` is a lightweight catalogue row (title, branch, category, expiry)
with an optional ``Attach`` field — Frappe's native ``File`` record holds the
bytes. Franchise scoping uses ``permission_query_conditions`` keyed on ``branch``.
Expiry alerts reuse the Phase 4 Notification fixture pattern.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, today


# ---------------------------------------------------------------------------
# Permission query conditions (desk row scoping)
# ---------------------------------------------------------------------------
def _branch_scope(user: str):
	from myschools.api.permissions import _user_scope

	return _user_scope(user)


def document_query(user):
	scope, branches = _branch_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Document`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Document`.branch IN ({in_list})"


# ---------------------------------------------------------------------------
# Validation + expiry status
# ---------------------------------------------------------------------------
def validate_mys_document(doc) -> None:
	"""Keep expiry status in sync when a row is saved."""
	if not doc.title:
		frappe.throw(_("Title is required."))
	refresh_document_expiry_status(doc)


def refresh_document_expiry_status(doc) -> None:
	"""Promote Active → Expired when past expiry_date."""
	if doc.status == "Archived" or not doc.expiry_date:
		return
	if getdate(doc.expiry_date) < getdate(today()) and doc.status == "Active":
		doc.status = "Expired"


def scheduled_mark_documents_expired() -> None:
	"""Daily — mark Active documents past expiry_date as Expired."""
	if not frappe.db.exists("DocType", "MYS Document"):
		return
	frappe.db.sql(
		"""
		UPDATE `tabMYS Document`
		SET status = 'Expired'
		WHERE status = 'Active'
			AND expiry_date IS NOT NULL
			AND expiry_date < %(today)s
		""",
		{"today": today()},
	)
	frappe.db.commit()


def documents_expiring_within(days: int, branch: str | None = None) -> list[dict]:
	"""Desk helper — active documents expiring in the next ``days`` (inclusive)."""
	from frappe.utils import add_days

	upper = add_days(today(), days)
	filters = {
		"status": "Active",
		"expiry_date": ["between", [today(), upper]],
	}
	if branch:
		filters["branch"] = branch
	return frappe.get_all(
		"MYS Document",
		filters=filters,
		fields=["name", "title", "branch", "category", "expiry_date", "file"],
		order_by="expiry_date asc",
	)
