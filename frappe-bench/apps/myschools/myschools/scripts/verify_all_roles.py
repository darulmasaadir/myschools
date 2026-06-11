"""Master role x surface audit — every franchise + portal role, no role skipped.

  bench --site SITE execute myschools.scripts.verify_all_roles.run

This is the umbrella matrix that guarantees the per-feature verify_* scripts
never silently drop a role. For EVERY role MY School defines
(``FRANCHISE_ROLES`` + the ``Guardian`` portal role) it asserts:

  1. A login user exists, is enabled, and actually carries the role
     (so "no role is skipped" is mechanically true, not a hope).
  2. The role's landing page (``role_home_page`` hook) is configured.
  3. The role can READ every doctype granted in ``FRANCHISE_ROLE_READS``
     (positive coverage — the feature surfaces are actually reachable).
  4. The role is DENIED a representative ungranted doctype (negative check —
     scoping isn't accidentally wide open).
  5. Branch/cluster/campus-scoped roles get a non-empty row window on
     ``Student`` and never leak another branch's rows (live get_list check).
  6. Portal roles (Teacher, Guardian) pass their api permission gate.

Run the seeds first so every role has a backing user:
  bench --site SITE execute myschools.scripts.seed_e2e.main
"""

from __future__ import annotations

import frappe
from frappe.permissions import has_permission

from myschools.api.permissions import _user_scope, student_query
from myschools.setup.install import FRANCHISE_ROLE_READS, FRANCHISE_ROLES

# Canonical login per role (seed_test_users + seed_portal_teacher).
ROLE_USER: dict[str, str] = {
	"Chief Executive": "ceo@mys.local",
	"HO Dept Head": "ho.head@mys.local",
	"Cluster Director": "cluster.dir@mys.local",
	"Academic Monitor": "monitor@mys.local",
	"Audit Officer": "audit@mys.local",
	"Branch Director": "branch.dir@mys.local",
	"Branch Principal": "principal@mys.local",
	"Branch Admin": "branch.admin@mys.local",
	"Branch Accountant": "accountant@mys.local",
	"Campus Incharge": "campus@mys.local",
	"Teacher": "e2e_teacher@mys.local",
	"Guardian": "e2e_guardian@mys.local",
}

# Roles whose data is branch/cluster/campus-scoped (expect a row window + no leak).
SCOPED_ROLES = {
	"Cluster Director",
	"Academic Monitor",
	"Audit Officer",
	"Branch Director",
	"Branch Principal",
	"Branch Admin",
	"Branch Accountant",
	"Campus Incharge",
}

# Global desk roles see an unscoped window.
GLOBAL_ROLES = {"Chief Executive", "HO Dept Head"}

# Representative doctype each role must be DENIED (clearest separation-of-duty
# cases). Finance docs for non-finance roles; Fees for inspection-only roles.
NEGATIVE_DENY: dict[str, str] = {
	"Academic Monitor": "Fees",
	"Audit Officer": "Fees",
	"Campus Incharge": "MYS Royalty Invoice",
	"Teacher": "MYS Royalty Invoice",
	"Guardian": "MYS Royalty Invoice",
	"Branch Accountant": "MYS Inspection Checklist Template",
	"Branch Admin": "MYS Corrective Action",
}


def run():
	failures: list[str] = []
	roles = [*FRANCHISE_ROLES, "Guardian"]

	for role in roles:
		email = ROLE_USER.get(role)
		if not email:
			failures.append(f"{role}: no canonical seed user mapped in ROLE_USER")
			continue

		# 1. Login user exists, enabled, carries the role.
		if not frappe.db.exists("User", email):
			failures.append(f"{role}: login user missing ({email}) — run the seeds")
			continue
		if not frappe.db.get_value("User", email, "enabled"):
			failures.append(f"{role}: login user {email} is disabled")
		if role not in frappe.get_roles(email):
			failures.append(f"{role}: user {email} does not carry role {role!r}")
			continue

		# 2. Landing page configured.
		home = (frappe.get_hooks("role_home_page") or {}).get(role)
		if not home:
			failures.append(f"{role}: no role_home_page mapping")

		# 3. Positive — can read every granted doctype.
		for dt in FRANCHISE_ROLE_READS.get(role, []):
			if not frappe.db.exists("DocType", dt):
				continue  # optional upstream app not installed
			if not has_permission(dt, "read", user=email):
				failures.append(f"{role}: cannot read granted doctype {dt!r}")

		# 4. Negative — denied a representative ungranted doctype.
		deny_dt = NEGATIVE_DENY.get(role)
		if deny_dt and frappe.db.exists("DocType", deny_dt):
			if has_permission(deny_dt, "read", user=email):
				failures.append(f"{role}: should NOT read {deny_dt!r} but can")

		# 5. Row-scope window + leak check on Student (most roles read it).
		if "Student" in FRANCHISE_ROLE_READS.get(role, []):
			window = student_query(email) or ""
			if role in GLOBAL_ROLES and window != "":
				failures.append(f"{role}: expected unscoped Student window, got {window!r}")
			if role in SCOPED_ROLES:
				if "mys_branch" not in window and "mys_campus" not in window:
					failures.append(f"{role}: expected scoped Student window, got {window!r}")
				else:
					_scope, branches = _user_scope(email)
					allowed = set(branches)
					frappe.set_user(email)
					try:
						rows = frappe.get_list("Student", fields=["name", "mys_branch"], limit_page_length=0)
					finally:
						frappe.set_user("Administrator")
					leaked = [r.name for r in rows if r.mys_branch and r.mys_branch not in allowed]
					if leaked:
						failures.append(
							f"{role}: sees Student outside window {sorted(allowed)}: {leaked[:5]}"
						)

	# 6. Portal gates.
	_check_portal_gates(failures)

	roster = ", ".join(f"{r}={ROLE_USER[r]}" for r in roles if r in ROLE_USER)
	if failures:
		print(f"FAILED — {len(failures)} issue(s) across {len(roles)} roles:")
		for f in failures:
			print(f"  x {f}")
		frappe.throw("verify_all_roles: role x surface audit failed")
	print(f"OK — all {len(roles)} roles verified (login, landing, reads, scope, portals).")
	print(f"     roster: {roster}")


def _check_portal_gates(failures: list[str]) -> None:
	"""Teacher + Guardian must pass their portal api permission gate."""
	teacher = ROLE_USER["Teacher"]
	guardian = ROLE_USER["Guardian"]

	if frappe.db.exists("User", teacher):
		from myschools.api.teacher_portal import TEACHER_ROLES

		if not (set(frappe.get_roles(teacher)) & set(TEACHER_ROLES)):
			failures.append(f"Teacher: {teacher} fails teacher_portal role gate")

	if frappe.db.exists("User", guardian):
		# Guardian portal scopes by Guardian.user; assert the link exists.
		linked = frappe.db.get_value("Guardian", {"user": guardian}, "name")
		if not linked:
			failures.append(f"Guardian: no Guardian record linked to {guardian}")
