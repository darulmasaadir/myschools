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


def employee_query(user):
	"""Row scoping for Employee — branch staff only see their own branch's
	roster; cluster roles see their cluster; HO/CEO/System Manager see all.

	Employees with no `mys_branch` (HO/back-office staff created upstream) stay
	visible only to global roles — branch/cluster users get the franchise window.
	"""
	return _branch_filter("mys_branch", user) or ""


def _groups_for_branches_sql(branches: list[str]) -> str:
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"""
		SELECT DISTINCT sgs.parent
		FROM `tabStudent Group Student` sgs
		INNER JOIN `tabStudent` st ON st.name = sgs.student
		WHERE sgs.parenttype = 'Student Group' AND sgs.active = 1
			AND st.mys_branch IN ({in_list})
	"""


def student_group_query(user):
	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabStudent Group`.name = '__none__'"
	return f"`tabStudent Group`.name IN ({_groups_for_branches_sql(branches)})"


def course_schedule_query(user):
	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabCourse Schedule`.name = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	group_subquery = _groups_for_branches_sql(branches)
	return f"""(
		`tabCourse Schedule`.student_group IN ({group_subquery})
		OR `tabCourse Schedule`.instructor IN (
			SELECT inst.name
			FROM `tabInstructor` inst
			INNER JOIN `tabEmployee` emp ON emp.name = inst.employee
			WHERE emp.mys_branch IN ({in_list})
		)
	)"""


def employee_has_permission(doc, ptype="read", user=None):
	"""Per-document permission check for Employee records, mirroring Student."""
	user = user or frappe.session.user
	roles = _user_roles(user)
	if roles & GLOBAL_ROLES:
		return True
	scope, branches = _user_scope(user)
	if scope == "global":
		return True
	if not branches:
		return False
	# An employee can always see their own record even across the branch window.
	if doc.get("user_id") and doc.get("user_id") == user:
		return True
	return doc.get("mys_branch") in branches
