"""One-command staging seed for a CEO / stakeholder review environment.

Builds a believable MY School demo on a fresh site by chaining the existing
*demo* seeds (not the e2e fixtures), then prints a clean access guide so a
reviewer can log in and walk every surface.

Run on the staging site:

    bench --site staging.myschools.pk execute \\
        myschools.scripts.seed_staging_review.run

Optionally set a shared review password (default ``myschool-review``):

    bench --site staging.myschools.pk execute \\
        myschools.scripts.seed_staging_review.run \\
        --kwargs '{"password": "Demo@2026"}'

What it creates (all idempotent — safe to re-run):
  - Franchise tree + ERPNext Companies + a sample royalty agreement
    with campus/branch rate overrides (``seed_demo``).
  - Academic year/term, programs, students, and submitted ``Fees``
    (``seed_education``).
  - Draft royalty invoices rolled up from the real ``Fees`` for May 2026
    (``demo_royalty_invoice``).
  - One System User per franchise role with a shared review password
    (``seed_test_users`` + password reset).
  - A rich Teacher/Guardian slice: instructor, class, schedule, assessment
    plan, transport assignment, library loan, compliance document, and an
    LMS course (``seed_portal_teacher``).

NOT for production: this seeds demo data with a shared password and no real
PII. Use a fresh staging site; never point it at a live database.
"""

from __future__ import annotations

import frappe
from frappe.utils.password import update_password

DEFAULT_PASSWORD = "myschool-review"

# (login URL, role label, email, what to click) — built once, reused for the
# printed guide and the unit test. Passwords are filled in at print time.
REVIEW_LOGINS: tuple[tuple[str, str, str, str], ...] = (
	("/app", "Chief Executive", "ceo@mys.local", "Central dashboard, royalty, all branches"),
	("/app", "Cluster Director", "cluster.dir@mys.local", "Cluster workspace + scoped branches"),
	("/app", "Branch Director", "branch.dir@mys.local", "Branch desk: students, fees, royalty cards"),
	("/app", "Branch Accountant", "accountant@mys.local", "Fees, bulk fee run, payment settings"),
	("/app", "Academic Monitor", "monitor@mys.local", "Inspection desk + monitoring dashboard"),
	("/teacher", "Teacher", "e2e_teacher@mys.local", "Teacher portal: classes, attendance, marks"),
	("/guardian", "Guardian", "e2e_guardian@mys.local", "Parent portal: fees, timetable, transport, library"),
	("/student", "Student", "e2e-student@mys.local", "Student portal: profile, fees, attendance, timetable"),
	("/lms", "Teacher (LMS)", "e2e_teacher@mys.local", "Learning portal: seeded course"),
)

# Portal users get role-specific passwords in their own seeds; we reset the
# two portal logins to the shared review password for a single hand-out.
PORTAL_LOGINS = ("e2e_teacher@mys.local", "e2e_guardian@mys.local", "e2e-student@mys.local")


def build_access_guide(password: str) -> list[dict]:
	"""Return the reviewer credential rows (pure — unit-testable, no DB)."""
	return [
		{"url": url, "role": role, "email": email, "password": password, "walk": walk}
		for url, role, email, walk in REVIEW_LOGINS
	]


def run(password: str = DEFAULT_PASSWORD):
	from myschools.scripts import (
		demo_royalty_invoice,
		seed_demo,
		seed_education,
		seed_test_users,
	)
	from myschools.scripts.seed_portal_teacher import main as seed_teacher_portal
	from myschools.scripts.verify_all_roles import run as verify_all_roles
	from myschools.scripts.verify_sidebar_surfaces import run as verify_sidebar_surfaces

	# 1. Franchise tree + companies + royalty agreement/overrides.
	seed_demo.run()
	# 2. Academic year/term, programs, students, submitted Fees.
	seed_education.run()
	# 3. Royalty invoices rolled up from real Fees (draft).
	demo_royalty_invoice.run()
	# 4. One System User per franchise role (shared review password below).
	seed_test_users.run()
	# 5. Rich teacher/guardian slice (transport, library, document, LMS).
	teacher = seed_teacher_portal()

	_apply_review_password(password, teacher)
	frappe.db.commit()
	verify_all_roles()
	verify_sidebar_surfaces()
	_print_guide(password)
	return {"password": password, "logins": [row["email"] for row in build_access_guide(password)]}


def _apply_review_password(password: str, teacher: dict) -> None:
	"""Reset every reviewer login to the shared review password."""
	emails = {row["email"] for row in build_access_guide(password)}
	emails.update(PORTAL_LOGINS)
	if teacher and teacher.get("guardian"):
		emails.add(teacher["guardian"]["user"])
	for email in emails:
		if frappe.db.exists("User", email):
			update_password(email, password)


def _print_guide(password: str) -> None:
	print("\n" + "=" * 78)
	print("  MY School — staging review access guide")
	print("=" * 78)
	print(f"  Shared password for all logins below:  {password}")
	print(f"  {'Login URL':<12}  {'Role':<20}  {'Email':<26}  What to review")
	print("  " + "-" * 90)
	for row in build_access_guide(password):
		print(f"  {row['url']:<12}  {row['role']:<20}  {row['email']:<26}  {row['walk']}")
	print("  " + "-" * 90)
	print("  Tip: open /guardian or /teacher on a phone and 'Add to Home Screen'")
	print("       to see the installable PWA (Phase 16).")
	print("=" * 78 + "\n")
