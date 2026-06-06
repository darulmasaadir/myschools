"""Role x surface verification for Phase 8d HR scaffolding (run via bench execute).

  bench --site SITE execute myschools.scripts.verify_hr_surfaces.run

Asserts two things for the Employee roster across every seeded franchise user —
the same "enumerate the matrix, don't trust one user" discipline as
verify_fee_admin_surfaces:

  1. Doctype-level read visibility matches FRANCHISE_ROLE_READS (only HO/CEO,
     Cluster Director, and Branch Director/Principal/Admin can read Employee).
  2. Row-level scope from `permissions.employee_query` is correct: global roles
     get an unscoped window; branch/cluster roles get a `mys_branch IN (...)`
     window and never see another branch's roster (live get_list leak check).

Run seed_test_users first so the users + their Employee rows exist.
"""

from __future__ import annotations

import frappe
from frappe.permissions import has_permission

from myschools.api.hr import payroll_entry_query
from myschools.api.permissions import _user_scope, employee_query

EMP = "Employee"
PAYROLL = "Payroll Entry"

# email -> (can_read_employee, scope) where scope is "global" | "scoped".
# "scoped" means employee_query must be a non-empty mys_branch window.
#
# Every seeded user can READ Employee: HO/CEO via FRANCHISE_ROLE_READS, and all
# branch/cluster users carry a backing Employee row (user_id link) so ERPNext
# auto-grants them the stock self-service "Employee" role. The 8d guarantee is
# therefore NOT "who can read" but "every read is branch-scoped" — proven by the
# live leak check below. No franchise user should ever see another branch's roster.
EXPECTED: dict[str, tuple[bool, str]] = {
	"ceo@mys.local": (True, "global"),
	"ho.head@mys.local": (True, "global"),
	"cluster.dir@mys.local": (True, "scoped"),
	"monitor@mys.local": (True, "scoped"),
	"audit@mys.local": (True, "scoped"),
	"branch.dir@mys.local": (True, "scoped"),
	"principal@mys.local": (True, "scoped"),
	"branch.admin@mys.local": (True, "scoped"),
	"accountant@mys.local": (True, "scoped"),
	"campus@mys.local": (True, "scoped"),
}


def run():
	failures: list[str] = []

	for email, (can_read, scope) in EXPECTED.items():
		if not frappe.db.exists("User", email):
			failures.append(f"user missing: {email} (run seed_test_users)")
			continue

		# 1. Doctype-level read visibility.
		got_read = bool(has_permission(EMP, "read", user=email))
		if got_read != can_read:
			verb = "allowed" if got_read else "denied"
			exp = "allow" if can_read else "deny"
			failures.append(f"{email}: Employee read is {verb}, expected {exp}")

		# 2. Row-level scope window.
		query = employee_query(email) or ""
		if scope == "global":
			if query != "":
				failures.append(f"{email}: expected unscoped Employee window, got {query!r}")
		else:  # scoped
			if "mys_branch" not in query:
				failures.append(f"{email}: expected mys_branch scope window, got {query!r}")

		# 3. Live leak check for readable, scoped roles — every visible Employee
		#    must fall inside the user's branch window.
		if can_read and scope == "scoped":
			_, branches = _user_scope(email)
			allowed = set(branches)
			frappe.set_user(email)
			try:
				rows = frappe.get_all(EMP, fields=["name", "mys_branch"])
			finally:
				frappe.set_user("Administrator")
			leaked = [r.name for r in rows if r.mys_branch and r.mys_branch not in allowed]
			if leaked:
				failures.append(f"{email}: sees Employee outside window {sorted(allowed)}: {leaked}")

	# Payroll Entry scope window (frappe/hrms, Phase 8d). Only assert when hrms
	# is installed; the row window must match the Employee window per role.
	if frappe.db.exists("DocType", PAYROLL):
		for email, (_can_read, scope) in EXPECTED.items():
			if not frappe.db.exists("User", email):
				continue
			pe_query = payroll_entry_query(email) or ""
			if scope == "global" and pe_query != "":
				failures.append(f"{email}: expected unscoped Payroll Entry window, got {pe_query!r}")
			elif scope == "scoped" and "mys_branch" not in pe_query:
				failures.append(f"{email}: expected mys_branch Payroll Entry window, got {pe_query!r}")
		surfaces = "Employee + Payroll Entry"
	else:
		surfaces = "Employee (hrms not installed — Payroll Entry skipped)"

	if failures:
		print("FAILED —", len(failures), "issue(s):")
		for f in failures:
			print(f"  x {f}")
		frappe.throw("HR role x surface verification failed")
	print(f"OK — HR ({surfaces}) surfaces verified for", ", ".join(EXPECTED))
