"""Permission query conditions that scope upstream and custom DocTypes to
the user's branch/cluster, enforcing the franchise hierarchy.

These hooks are wired in `myschools/hooks.py` under
`permission_query_conditions`. They return SQL `WHERE` fragments that
Frappe appends to every list/report query for a given DocType.

Tier rules:
  * System Manager / Chief Executive / HO Dept Head — no scoping (see all)
  * Cluster Director / Academic Monitor / Audit Officer — scoped to their cluster
  * Branch Director / Principal / Admin / Accountant / Campus Incharge — scoped to their branch(es)
  * All other users (Student, Guardian) — handled by upstream education app
"""

import frappe

GLOBAL_ROLES = {"System Manager", "Administrator", "Chief Executive", "HO Dept Head"}
CLUSTER_ROLES = {"Cluster Director", "Academic Monitor", "Audit Officer"}
BRANCH_ROLES = {
	"Branch Director",
	"Branch Principal",
	"Branch Admin",
	"Branch Accountant",
	"Campus Incharge",
}


def _user_roles(user):
	return set(frappe.get_roles(user))


def _user_employee(user):
	return frappe.db.get_value(
		"Employee", {"user_id": user}, ["name", "mys_branch", "mys_role_tier"], as_dict=True
	)


def _user_scope(user):
	"""Returns (scope, value_list) describing the user's data window.

	scope is one of: 'global', 'cluster', 'branch', 'none'.
	"""
	roles = _user_roles(user)
	if roles & GLOBAL_ROLES:
		return "global", []

	emp = _user_employee(user)
	if not emp or not emp.get("mys_branch"):
		return "none", []

	if roles & CLUSTER_ROLES:
		cluster = frappe.db.get_value("MYS Branch", emp.mys_branch, "cluster")
		branches = frappe.get_all("MYS Branch", filters={"cluster": cluster}, pluck="name")
		return "cluster", branches

	if roles & BRANCH_ROLES:
		return "branch", [emp.mys_branch]

	return "none", []


def _branch_filter(field: str, user: str) -> str:
	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return f"`{field}` = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`{field}` IN ({in_list})"


def student_query(user):
	return _branch_filter("mys_branch", user) or ""


def branch_query(user):
	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Branch`.name = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Branch`.name IN ({in_list})"


def campus_query(user):
	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Campus`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Campus`.branch IN ({in_list})"


def inspection_query(user):
	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Inspection Visit`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Inspection Visit`.branch IN ({in_list})"


def student_has_permission(doc, ptype="read", user=None):
	"""Per-document permission check for Student records."""
	user = user or frappe.session.user
	roles = _user_roles(user)
	if roles & GLOBAL_ROLES:
		return True
	scope, branches = _user_scope(user)
	if scope == "global":
		return True
	if not branches:
		return False
	return doc.get("mys_branch") in branches
