"""Auto-attach the right MYS Module Profile and default Workspace to a User
based on the franchise role they have. Highest tier wins when multiple roles
overlap.

In Frappe v15 the `role_home_page` hook only applies to portal (Website User)
logins; for System Users the login API resolves the post-login landing from
`User.default_workspace`. So this helper writes both fields together — that's
what gives a Branch Admin `/app/mys-branch` instead of `/app/home` after login.

Wired via the `User.validate` doc_event (so the attribute change is persisted
as part of the same save) and called during `after_migrate` to back-fill
profiles for existing users created before this app was installed.
"""

import frappe

# Highest tier first — first role match wins. Tuple shape:
#   (Module Profile name, default Workspace slug, set of roles in this tier)
from myschools.setup.role_model import CAMPUS_ADMIN_ROLE, HO_DEPT_HEAD_ROLES

TIER_ORDER = [
	("MYS HO", "mys-head-office", {"Chief Executive", *HO_DEPT_HEAD_ROLES}),
	("MYS Cluster", "mys-cluster", {"Cluster Director"}),
	(
		"MYS Branch",
		"mys-branch",
		{"Branch Director", "Branch Principal", "Branch Admin", "Branch Accountant"},
	),
	("MYS Campus", "mys-campus", {"Campus Incharge", CAMPUS_ADMIN_ROLE}),
	("MYS Inspection", "mys-inspection", {"Academic Monitor", "Audit Officer"}),
]


def resolve_profile_for_roles(role_names: set[str]) -> str | None:
	for profile, _workspace, tier_roles in TIER_ORDER:
		if role_names & tier_roles:
			return profile
	return None


def resolve_workspace_for_roles(role_names: set[str]) -> str | None:
	for _profile, workspace, tier_roles in TIER_ORDER:
		if role_names & tier_roles:
			return workspace
	return None


def attach_module_profile_to_user(doc, method=None):
	"""Set User.module_profile + User.default_workspace from the highest-tier
	MYS role present. Skips Administrator and Guest. No-op if no MYS role."""
	if doc.name in ("Administrator", "Guest"):
		return
	role_names = {r.role for r in (doc.roles or [])}
	profile = resolve_profile_for_roles(role_names)
	workspace = resolve_workspace_for_roles(role_names)
	if not profile and not workspace:
		return

	if profile and frappe.db.exists("Module Profile", profile):
		if doc.module_profile != profile:
			doc.module_profile = profile

	if workspace and frappe.db.exists("Workspace", workspace):
		if doc.default_workspace != workspace:
			doc.default_workspace = workspace


def backfill_existing_users():
	"""Apply the right MYS Module Profile + default workspace to every existing
	User. Called from `after_migrate` so a fresh install picks them up for users
	created before this app was installed."""
	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User"},
		pluck="name",
	)
	for name in users:
		if name in ("Administrator", "Guest"):
			continue
		doc = frappe.get_doc("User", name)
		before = (doc.module_profile, doc.default_workspace)
		attach_module_profile_to_user(doc)
		after = (doc.module_profile, doc.default_workspace)
		if before != after:
			if doc.module_profile != before[0]:
				doc.db_set("module_profile", doc.module_profile, update_modified=False)
			if doc.default_workspace != before[1]:
				doc.db_set("default_workspace", doc.default_workspace, update_modified=False)
