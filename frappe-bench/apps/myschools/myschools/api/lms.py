"""Phase 15 — LMS integration: branch-scoped ``LMS Course`` rows over frappe/lms.

We do not fork LMS. Franchise scoping uses Custom Fields on ``LMS Course``
(``mys_branch``, ``mys_program``) plus ``permission_query_conditions`` /
``has_permission`` in this module — the same pattern as library/transport.
SSO is native: LMS uses the shared Frappe ``User`` table.
"""

from __future__ import annotations

import frappe
from frappe import _

from myschools.api.permissions import _user_scope


def lms_course_query(user):
	"""Row scoping for LMS Course — branch staff see their branch only."""
	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabLMS Course`.mys_branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabLMS Course`.mys_branch IN ({in_list})"


def lms_course_has_permission(doc, ptype="read", user=None):
	"""Per-document permission check for LMS Course."""
	user = user or frappe.session.user
	scope, branches = _user_scope(user)
	if scope == "global":
		return True
	if not branches:
		return False
	branch = doc.get("mys_branch")
	if not branch:
		return False
	return branch in branches


def validate_mys_lms_course(doc, method=None) -> None:
	"""Every franchise course must declare its owning branch."""
	if not doc.get("mys_branch"):
		frappe.throw(_("MYS Branch is required for franchise-scoped LMS courses."))


_LMS_COURSE_WRITE_ROLES = ("Branch Director", "Branch Principal", "Branch Admin")

# Users that must land on the ERP desk (/app), not the /apps picker, in CI/e2e.
_DEFAULT_DESK_APP_USERS = (
	"Administrator",
	"e2e_teacher@mys.local",
	"e2e_guardian@mys.local",
	"e2e_director@mys.local",
	"ceo@mys.local",
	"ho.head@mys.local",
	"cluster.dir@mys.local",
	"monitor@mys.local",
	"audit@mys.local",
	"branch.dir@mys.local",
	"principal@mys.local",
	"branch.admin@mys.local",
	"accountant@mys.local",
	"campus@mys.local",
)


def ensure_default_desk_app() -> None:
	"""Pin MY School ERP as the post-login app when frappe/lms is installed.

	LMS registers route ``/lms``, so Frappe's default-path logic sends users to
	``/apps`` unless ``User.default_app`` is set. Idempotent.
	"""
	if "lms" not in frappe.get_installed_apps():
		return
	for email in _DEFAULT_DESK_APP_USERS:
		if frappe.db.exists("User", email):
			frappe.db.set_value("User", email, "default_app", "myschools", update_modified=False)


def ensure_lms_course_permissions() -> None:
	"""Grant franchise roles desk access to LMS Course (idempotent).

	Stock LMS perms only cover System Manager / Course Creator / Moderator.
	Branch management roles need create/write on franchise-scoped courses.
	"""
	if not frappe.db.exists("DocType", "LMS Course"):
		return
	from frappe.permissions import add_permission, update_permission_property

	for role in _LMS_COURSE_WRITE_ROLES:
		if not frappe.db.exists("Role", role):
			continue
		add_permission("LMS Course", role, 0)
		for perm in ("read", "create", "write"):
			update_permission_property("LMS Course", role, 0, perm, 1)
