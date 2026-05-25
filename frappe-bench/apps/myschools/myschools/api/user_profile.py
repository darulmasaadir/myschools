"""Auto-attach the right MYS Module Profile to a User based on the
franchise role they have. Highest tier wins when multiple roles overlap.

Wired via the `User.validate` doc_event (so the attribute change is persisted
as part of the same save) and called during `after_migrate` to back-fill
profiles for existing users created before this app was installed.
"""

import frappe

# Highest tier first — first role match wins.
TIER_PROFILE_ORDER = [
	("MYS HO", {"Chief Executive", "HO Dept Head"}),
	("MYS Cluster", {"Cluster Director"}),
	("MYS Branch", {"Branch Director", "Branch Principal", "Branch Admin", "Branch Accountant"}),
	("MYS Campus", {"Campus Incharge"}),
	("MYS Inspection", {"Academic Monitor", "Audit Officer"}),
]


def resolve_profile_for_roles(role_names: set[str]) -> str | None:
	for profile, tier_roles in TIER_PROFILE_ORDER:
		if role_names & tier_roles:
			return profile
	return None


def attach_module_profile_to_user(doc, method=None):
	"""Set User.module_profile based on the highest-tier MYS role present.

	Skips Administrator and Guest. Does nothing if the user has no MYS role
	(they keep whatever profile they were given manually, or none)."""
	if doc.name in ("Administrator", "Guest"):
		return
	role_names = {r.role for r in (doc.roles or [])}
	profile = resolve_profile_for_roles(role_names)
	if not profile:
		return
	if not frappe.db.exists("Module Profile", profile):
		return
	if doc.module_profile != profile:
		doc.module_profile = profile


def backfill_existing_users():
	"""Apply the right MYS Module Profile to every existing User.
	Called from `after_migrate` so a fresh install picks up the new profiles
	without admins manually editing each user."""
	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User"},
		pluck="name",
	)
	for name in users:
		if name in ("Administrator", "Guest"):
			continue
		doc = frappe.get_doc("User", name)
		before = doc.module_profile
		attach_module_profile_to_user(doc)
		if doc.module_profile != before:
			doc.db_set("module_profile", doc.module_profile, update_modified=False)
