"""Role x surface verification for Phase 8b student lifecycle (run via bench execute).

  bench --site SITE execute myschools.scripts.verify_student_lifecycle_surfaces.run

Asserts runtime permissions for MYS Student Transfer and MYS Student Leaving match
the doctype JSON matrix — same discipline as verify_fee_admin_surfaces.py.

Run seed_test_users first so the users exist.
"""

from __future__ import annotations

import frappe
from frappe.permissions import has_permission

TRANSFER = "MYS Student Transfer"
LEAVING = "MYS Student Leaving"

PTYPES = ("read", "create", "write", "submit")

EXPECTED: dict[str, dict[str, set[str]]] = {
	"ceo@mys.local": {
		TRANSFER: {"read", "create", "write", "submit"},
		LEAVING: {"read", "create", "write", "submit"},
	},
	"admin.head@mys.local": {
		TRANSFER: {"read"},
		LEAVING: {"read"},
	},
	"branch.dir@mys.local": {
		TRANSFER: {"read", "create", "write", "submit"},
		LEAVING: {"read", "create", "write", "submit"},
	},
	"principal@mys.local": {
		TRANSFER: {"read", "create", "write", "submit"},
		LEAVING: {"read", "create", "write", "submit"},
	},
	"branch.admin@mys.local": {
		TRANSFER: {"read", "create", "write", "submit"},
		LEAVING: {"read", "create", "write", "submit"},
	},
	"accountant@mys.local": {
		TRANSFER: {"read"},
		LEAVING: {"read"},
	},
	"monitor@mys.local": {
		TRANSFER: set(),
		LEAVING: set(),
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
						failures.append(f"{email}: {doctype} {ptype} is {verb}, expected {exp}")
		finally:
			frappe.set_user("Administrator")

	if failures:
		print("FAILED —", len(failures), "issue(s):")
		for f in failures:
			print(f"  x {f}")
		frappe.throw("Student lifecycle role x surface verification failed")
	print("OK — student lifecycle surfaces verified for", ", ".join(EXPECTED))
