"""Inspection portal — cluster-scoped visits and mobile checklist runner.

Academic Monitor and Audit Officer users resolve allowed branches via
``permissions._user_scope`` (Employee ``mys_branch`` → cluster branches).
Data queries use explicit branch filters with ``ignore_permissions=True``
after the scope check, matching the branch portal pattern.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from myschools.api.inspection import apply_template_to_visit
from myschools.api.notifications import log_communication
from myschools.api.permissions import _user_scope

INSPECTION_ROLES = frozenset({"Academic Monitor", "Audit Officer"})


def require_inspection_role() -> None:
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/inspection"
		raise frappe.Redirect
	if not INSPECTION_ROLES & set(frappe.get_roles()):
		frappe.throw("You do not have access to the Inspection portal.", frappe.PermissionError)


def get_allowed_branches(user: str | None = None) -> list[str]:
	"""Branch names the user may see in the inspection portal."""
	user = user or frappe.session.user
	scope, branches = _user_scope(user)
	if scope == "global":
		return frappe.get_all("MYS Branch", pluck="name", order_by="branch_name")
	if not branches:
		return []
	return list(branches)


def assert_visit_access(visit: str, user: str | None = None) -> None:
	branch = frappe.db.get_value("MYS Inspection Visit", visit, "branch")
	if not branch:
		frappe.throw(_("Visit {0} not found").format(visit), frappe.DoesNotExistError)
	allowed = get_allowed_branches(user)
	if branch not in allowed:
		frappe.throw(_("You do not have access to this visit."), frappe.PermissionError)


def populate_inspection_context(context) -> list[str]:
	"""Shared context for authenticated /inspection/* pages."""
	require_inspection_role()
	branches = get_allowed_branches()
	context.no_cache = 1
	context.show_sidebar = 0
	context.allowed_branches = branches
	context.nav_items = [
		{"label": "Dashboard", "route": "/inspection"},
		{"label": "Visits", "route": "/inspection/visits"},
		{"label": "Admission enquiry", "route": "/admission-enquiry"},
	]
	return branches


def get_dashboard_summary(branches: list[str]) -> dict:
	if not branches:
		return {
			"open_findings": 0,
			"overdue_findings": 0,
			"draft_visits": 0,
			"recent_visits": [],
		}
	open_findings = frappe.db.count(
		"MYS Inspection Finding",
		{"branch": ["in", branches], "status": ["in", ["Open", "In Progress"]], "docstatus": 1},
	)
	overdue_findings = frappe.db.count(
		"MYS Inspection Finding",
		{
			"branch": ["in", branches],
			"status": ["in", ["Open", "In Progress"]],
			"due_date": ["<", nowdate()],
			"docstatus": 1,
		},
	)
	draft_visits = frappe.db.count(
		"MYS Inspection Visit",
		{"branch": ["in", branches], "docstatus": 0},
	)
	recent_visits = frappe.get_all(
		"MYS Inspection Visit",
		filters={"branch": ["in", branches]},
		fields=[
			"name",
			"branch",
			"visit_date",
			"visit_type",
			"docstatus",
			"score_percent",
			"items_failed",
		],
		order_by="visit_date desc, modified desc",
		limit=8,
	)
	for row in recent_visits:
		row["branch_label"] = frappe.db.get_value("MYS Branch", row.branch, "branch_name") or row.branch
	return {
		"open_findings": open_findings,
		"overdue_findings": overdue_findings,
		"draft_visits": draft_visits,
		"recent_visits": recent_visits,
	}


def list_visits(branches: list[str], limit: int = 50) -> list[dict]:
	if not branches:
		return []
	rows = frappe.get_all(
		"MYS Inspection Visit",
		filters={"branch": ["in", branches]},
		fields=[
			"name",
			"branch",
			"campus",
			"visit_date",
			"visit_type",
			"docstatus",
			"score_percent",
			"items_failed",
			"checklist_template",
		],
		order_by="visit_date desc, modified desc",
		limit=limit,
	)
	for row in rows:
		row["branch_label"] = frappe.db.get_value("MYS Branch", row.branch, "branch_name") or row.branch
		row["status_label"] = "Submitted" if row.docstatus == 1 else "Draft"
	return rows


def get_visit_detail(visit: str) -> dict:
	assert_visit_access(visit)
	doc = frappe.get_doc("MYS Inspection Visit", visit)
	branch_label = frappe.db.get_value("MYS Branch", doc.branch, "branch_name") or doc.branch
	rows = []
	for idx, row in enumerate(doc.checklist_results or []):
		rows.append(
			frappe._dict(
				{
					"idx": idx,
					"item_text": row.item_text,
					"category": row.category,
					"severity": row.severity,
					"result": row.result or "",
					"score": row.score,
					"max_score": row.max_score,
					"notes": row.notes or "",
				}
			)
		)
	return frappe._dict(
		{
			"name": doc.name,
			"branch": doc.branch,
			"branch_label": branch_label,
			"campus": doc.campus,
			"visit_date": doc.visit_date,
			"visit_type": doc.visit_type,
			"docstatus": doc.docstatus,
			"checklist_template": doc.checklist_template,
			"total_items": doc.total_items,
			"items_passed": doc.items_passed,
			"items_failed": doc.items_failed,
			"score_percent": doc.score_percent,
			"checklist_rows": rows,
		}
	)


def get_active_templates(visit_type: str | None = None) -> list[dict]:
	filters = {"is_active": 1}
	if visit_type:
		filters["visit_type"] = visit_type
	return frappe.get_all(
		"MYS Inspection Checklist Template",
		filters=filters,
		fields=["name", "template_name", "visit_type", "version"],
		order_by="template_name",
	)


def get_branches_for_form(branches: list[str]) -> list[dict]:
	if not branches:
		return []
	return frappe.get_all(
		"MYS Branch",
		filters={"name": ["in", branches]},
		fields=["name", "branch_name", "branch_code"],
		order_by="branch_name",
	)


def get_campuses_for_branch(branch: str) -> list[dict]:
	return frappe.get_all(
		"MYS Campus",
		filters={"branch": branch},
		fields=["name", "campus_name", "campus_type"],
		order_by="campus_type",
	)


@frappe.whitelist()
def apply_template(visit: str, template: str) -> dict:
	require_inspection_role()
	assert_visit_access(visit)
	count = apply_template_to_visit(visit, template)
	return {"ok": True, "rows": count}


@frappe.whitelist()
def save_checklist(visit: str, rows: str) -> dict:
	"""Persist checklist result/notes/score for a draft visit."""
	require_inspection_role()
	assert_visit_access(visit)
	doc = frappe.get_doc("MYS Inspection Visit", visit)
	if doc.docstatus != 0:
		frappe.throw(_("Only draft visits can be edited in the portal."))
	try:
		payload = json.loads(rows) if isinstance(rows, str) else rows
	except json.JSONDecodeError as exc:
		frappe.throw(_("Invalid checklist payload: {0}").format(exc))
	if not isinstance(payload, list):
		frappe.throw(_("Checklist payload must be a list."))
	for item in payload:
		idx = int(item.get("idx", -1))
		if idx < 0 or idx >= len(doc.checklist_results or []):
			continue
		row = doc.checklist_results[idx]
		result = (item.get("result") or "").strip()
		if result in ("Pass", "Fail", "N/A"):
			row.result = result
		if result == "Pass":
			row.score = row.max_score or 1
		elif result == "Fail":
			row.score = 0
		elif result == "N/A":
			row.score = 0
		if "notes" in item:
			row.notes = item.get("notes") or ""
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True, "score_percent": doc.score_percent, "items_failed": doc.items_failed}


@frappe.whitelist()
def submit_visit(visit: str) -> dict:
	require_inspection_role()
	assert_visit_access(visit)
	doc = frappe.get_doc("MYS Inspection Visit", visit)
	if doc.docstatus != 0:
		frappe.throw(_("Visit is already submitted."))
	if not doc.checklist_results:
		frappe.throw(_("Add checklist items before submitting."))
	incomplete = [r for r in doc.checklist_results if not r.result]
	if incomplete:
		frappe.throw(_("Every checklist item needs a result (Pass / Fail / N/A)."))
	doc.submit()
	frappe.db.commit()
	return {"ok": True, "name": doc.name}


@frappe.whitelist(allow_guest=True)
def submit_admission_enquiry(
	parent_name: str,
	phone: str,
	branch: str = "",
	email: str = "",
	child_grade: str = "",
	message: str = "",
) -> dict:
	"""Public admission enquiry → MYS Communication Log."""
	parent_name = (parent_name or "").strip()
	phone = (phone or "").strip()
	if not parent_name or not phone:
		frappe.throw(_("Parent name and phone are required."))
	if branch and not frappe.db.exists("MYS Branch", branch):
		frappe.throw(_("Branch not found."))
	body_lines = [
		f"Parent: {parent_name}",
		f"Phone: {phone}",
	]
	if email:
		body_lines.append(f"Email: {email.strip()}")
	if child_grade:
		body_lines.append(f"Child grade / age: {child_grade.strip()}")
	if message:
		body_lines.append("")
		body_lines.append(message.strip())
	body = "\n".join(body_lines)
	subject = f"Admission enquiry — {parent_name}"
	sender = frappe.session.user if frappe.session.user != "Guest" else "Administrator"
	name = log_communication(
		channel="In-App",
		status="Sent",
		subject=subject,
		body=body,
		scope="Branch" if branch else "Global",
		branch=branch or None,
		sender=sender,
	)
	return {"ok": True, "name": name}


def create_draft_visit(
	branch: str,
	visit_type: str,
	visit_date: str | None = None,
	campus: str | None = None,
	inspector: str | None = None,
) -> str:
	"""Create a draft visit for the logged-in inspector."""
	require_inspection_role()
	allowed = get_allowed_branches()
	if branch not in allowed:
		frappe.throw(_("You cannot create a visit for this branch."), frappe.PermissionError)
	if not inspector:
		inspector = frappe.db.get_value(
			"Employee",
			{"user_id": frappe.session.user, "status": "Active"},
			"name",
		) or frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not inspector:
		frappe.throw(
			_("No Employee record is linked to your login. Ask Head Office to create one."),
			frappe.PermissionError,
		)
	doc = frappe.get_doc(
		{
			"doctype": "MYS Inspection Visit",
			"branch": branch,
			"campus": campus,
			"visit_type": visit_type,
			"visit_date": visit_date or nowdate(),
			"inspector": inspector,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


@frappe.whitelist()
def create_visit(
	branch: str,
	visit_type: str,
	visit_date: str | None = None,
	campus: str | None = None,
) -> dict:
	"""Whitelist wrapper for portal POST. Returns {ok, name}."""
	name = create_draft_visit(branch, visit_type, visit_date or None, campus or None)
	return {"ok": True, "name": name}
