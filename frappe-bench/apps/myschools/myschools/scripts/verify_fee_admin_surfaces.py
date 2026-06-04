"""Role x surface verification for Phase 8a fee-admin doctypes (run via bench execute).

  bench --site SITE execute myschools.scripts.verify_fee_admin_surfaces.run

Asserts that the permission matrix encoded in the doctype JSON actually holds at
runtime for every seeded franchise test user — the same "enumerate the matrix,
don't trust one user" discipline as verify_branch_desk_cards. Covers:

  * MYS Fee Structure Override  (Director writes, Accountant read-only, Monitor none)
  * MYS Late Fee Policy         (Director + Accountant write, Monitor none)
  * MYS Bulk Fee Run            (Director/Admin/Accountant write, Principal none)

Run seed_test_users first so the users exist.
"""

from __future__ import annotations

import frappe
from frappe.permissions import has_permission

# email -> expected {doctype: set(allowed ptypes)} for the franchise/HO roles.
# Anything not listed for a doctype is expected to be DENIED.
OVERRIDE = "MYS Fee Structure Override"
POLICY = "MYS Late Fee Policy"
BULK = "MYS Bulk Fee Run"

PTYPES = ("read", "create", "write")

EXPECTED: dict[str, dict[str, set[str]]] = {
	"ceo@mys.local": {
		OVERRIDE: {"read", "create", "write"},
		POLICY: {"read", "create", "write"},
		BULK: {"read", "create", "write"},
	},
	"ho.head@mys.local": {
		OVERRIDE: {"read"},
		POLICY: {"read"},
		BULK: {"read"},
	},
	"branch.dir@mys.local": {
		OVERRIDE: {"read", "create", "write"},
		POLICY: {"read", "create", "write"},
		BULK: {"read", "create", "write"},
	},
	"accountant@mys.local": {
		OVERRIDE: {"read"},  # read-only: only Director changes overrides
		POLICY: {"read", "create", "write"},
		BULK: {"read", "create", "write"},
	},
	"branch.admin@mys.local": {
		# Read on override/policy via FRANCHISE_ROLE_READS (admin runs bulk fees,
		# so reads the config that drives them) — but cannot change them.
		OVERRIDE: {"read"},
		POLICY: {"read"},
		BULK: {"read", "create", "write"},
	},
	"principal@mys.local": {
		OVERRIDE: set(),
		POLICY: set(),
		BULK: set(),
	},
	"monitor@mys.local": {
		OVERRIDE: set(),
		POLICY: set(),
		BULK: set(),
	},
}


def run():
	failures: list[str] = []

	for email, matrix in EXPECTED.items():
		if not frappe.db.exists("User", email):
			failures.append(f"user missing: {email} (run seed_test_users)")
			continue
		frappe.set_user(email)
		try:
			for doctype, allowed in matrix.items():
				for ptype in PTYPES:
					got = bool(has_permission(doctype, ptype, user=email))
					want = ptype in allowed
					if got != want:
						verb = "allowed" if got else "denied"
						exp = "allow" if want else "deny"
						failures.append(
							f"{email}: {doctype} {ptype} is {verb}, expected {exp}"
						)
		finally:
			frappe.set_user("Administrator")

	if failures:
		print("FAILED —", len(failures), "issue(s):")
		for f in failures:
			print(f"  x {f}")
		frappe.throw("Fee-admin role x surface verification failed")
	print("OK — fee-admin surfaces verified for", ", ".join(EXPECTED))
