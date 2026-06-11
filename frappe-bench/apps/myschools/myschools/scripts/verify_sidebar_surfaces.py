"""Sidebar / module-profile governance audit (Phase 17d).

  bench --site SITE execute myschools.scripts.verify_sidebar_surfaces.run

The desk left sidebar lists every *module* a user's Module Profile does NOT
block. Phase 7c PR #14 and the Academic-Monitor HR/Payroll leak both came from
INCOMPLETE block-lists — a module nobody intended to expose (HR, Payroll, LMS,
Website, Automation, Integrations, Setup) was silently visible because the
profile never named it. This script makes the block-list a mechanical contract:

  1. Every MYS Module Profile blocks the modules its tier MUST hide
     (separation-of-duty: an Academic Monitor never sees Payroll, a Branch
     user never sees LMS authoring, nobody sees Website/Automation/Integrations).
  2. Every MYS Module Profile keeps the modules its tier NEEDS visible
     (a Finance Dept Head must keep Accounts; branch staff keep Education).
  3. Each seeded franchise user resolves to the expected Module Profile
     (so the contract above actually reaches a real login).

Run the seeds first so the users exist:
  bench --site SITE execute myschools.scripts.seed_test_users.run
"""

from __future__ import annotations

import frappe

from myschools.api.user_profile import resolve_profile_for_roles
from myschools.setup.role_model import ROLE_SEED_USER

# Modules that must NEVER appear in any franchise tier's sidebar — these are
# pure-admin / developer surfaces with no school-operations purpose.
GLOBAL_MUST_BLOCK = {"Website", "Automation", "Integrations"}

# Per-profile REQUIRED blocks (sensitive modules that tier must not see).
#
# Note: the Branch tier intentionally keeps HR visible — a Branch Director /
# Principal / Admin manages their own staff roster (Employee is branch-scoped by
# `employee_query`). The genuine separation-of-duty leak this audit guards is the
# Inspection tier (Academic Monitor / Audit Officer) seeing HR / Payroll / LMS /
# Accounts, plus the universal admin surfaces (Website / Automation / Integrations).
REQUIRED_BLOCKS: dict[str, set[str]] = {
	"MYS HO": GLOBAL_MUST_BLOCK,
	"MYS Cluster": GLOBAL_MUST_BLOCK | {"HR", "Payroll", "LMS", "Setup", "CRM", "Selling"},
	"MYS Branch": GLOBAL_MUST_BLOCK | {"LMS", "Setup", "CRM", "Selling"},
	"MYS Campus": GLOBAL_MUST_BLOCK | {"HR", "Payroll", "LMS", "Setup", "Accounts"},
	"MYS Inspection": GLOBAL_MUST_BLOCK | {"HR", "Payroll", "LMS", "Setup", "Accounts", "Education"},
}

# Per-profile REQUIRED allows (modules the tier needs — must NOT be blocked).
REQUIRED_ALLOWS: dict[str, set[str]] = {
	"MYS HO": {"MY School ERP", "Accounts", "Education"},
	"MYS Cluster": {"MY School ERP", "Education"},
	"MYS Branch": {"MY School ERP", "Education"},
	"MYS Campus": {"MY School ERP", "Education"},
	"MYS Inspection": {"MY School ERP"},
}

# Expected Module Profile per seeded role (mirrors user_profile.TIER_ORDER).
ROLE_EXPECTED_PROFILE: dict[str, str] = {
	"Chief Executive": "MYS HO",
	"Finance Dept Head": "MYS HO",
	"Academic Dept Head": "MYS HO",
	"Monitoring Dept Head": "MYS HO",
	"Administration Dept Head": "MYS HO",
	"Training Dept Head": "MYS HO",
	"Cluster Director": "MYS Cluster",
	"Academic Monitor": "MYS Inspection",
	"Audit Officer": "MYS Inspection",
	"Branch Director": "MYS Branch",
	"Branch Principal": "MYS Branch",
	"Branch Admin": "MYS Branch",
	"Branch Accountant": "MYS Branch",
	"Campus Incharge": "MYS Campus",
	"Campus Admin": "MYS Campus",
}


def run():
	failures: list[str] = []

	for profile, must_block in REQUIRED_BLOCKS.items():
		if not frappe.db.exists("Module Profile", profile):
			failures.append(f"Module Profile missing: {profile}")
			continue
		doc = frappe.get_doc("Module Profile", profile)
		blocked = {row.module for row in doc.block_modules}

		missing = must_block - blocked
		if missing:
			failures.append(f"{profile}: must block but does not: {sorted(missing)}")

		over_blocked = REQUIRED_ALLOWS.get(profile, set()) & blocked
		if over_blocked:
			failures.append(f"{profile}: must keep visible but blocks: {sorted(over_blocked)}")

	# 3. Seeded users resolve to the expected profile.
	for role, expected in ROLE_EXPECTED_PROFILE.items():
		got = resolve_profile_for_roles({role})
		if got != expected:
			failures.append(f"{role}: resolves to {got!r}, expected {expected!r}")
		email = ROLE_SEED_USER.get(role)
		if email and frappe.db.exists("User", email):
			user_profile = frappe.db.get_value("User", email, "module_profile")
			if user_profile != expected:
				failures.append(
					f"{role} ({email}): User.module_profile is {user_profile!r}, expected {expected!r}"
				)

	if failures:
		print(f"FAILED — {len(failures)} sidebar/module-profile issue(s):")
		for f in failures:
			print(f"  x {f}")
		frappe.throw("verify_sidebar_surfaces: module-profile governance audit failed")
	print(
		f"OK — {len(REQUIRED_BLOCKS)} module profiles enforce tier block-lists; "
		f"{len(ROLE_EXPECTED_PROFILE)} roles resolve to the right profile."
	)
