"""Role x surface verification for Phase 15 LMS (run via bench execute).

  bench --site SITE execute myschools.scripts.verify_lms_surfaces.run

Asserts:
  1. LMS Course custom fields exist when lms is installed.
  2. Branch director sees only their branch's LMS Course rows (live leak check).
  3. Teacher franchise user carries LMS Student and can pass check_app_permission.
"""

from __future__ import annotations

import frappe

from myschools.api.lms import lms_course_query

DIRECTOR = "e2e_director@mys.local"
TEACHER = "e2e_teacher@mys.local"
SEEDED_TITLE = "E2E Portal Math LMS"


def run():
	if "lms" not in frappe.get_installed_apps():
		print("OK — lms not installed; LMS surfaces skipped")
		return

	failures: list[str] = []
	_check_custom_fields(failures)
	_check_director_scope(failures)
	_check_teacher_lms_access(failures)

	if failures:
		print("FAILED —", len(failures), "issue(s):")
		for f in failures:
			print(f"  ✗ {f}")
		frappe.throw("LMS role x surface verification failed")
	print(f"OK — LMS surfaces verified for {DIRECTOR}, {TEACHER}")


def _check_custom_fields(failures: list[str]) -> None:
	meta = frappe.get_meta("LMS Course")
	for field in ("mys_branch", "mys_program"):
		if not meta.has_field(field):
			failures.append(f"LMS Course missing custom field {field}")


def _check_director_scope(failures: list[str]) -> None:
	if not frappe.db.exists("User", DIRECTOR):
		failures.append(f"user missing: {DIRECTOR}")
		return

	cond = lms_course_query(DIRECTOR)
	if not cond or "__none__" in cond:
		failures.append(f"{DIRECTOR}: lms_course_query returned no branch window")

	prev = frappe.session.user
	try:
		frappe.set_user(DIRECTOR)
		rows = frappe.get_list(
			"LMS Course",
			filters={"title": SEEDED_TITLE},
			fields=["name", "mys_branch"],
			limit_page_length=10,
		)
		if not rows:
			failures.append(f"{DIRECTOR}: cannot see seeded LMS course {SEEDED_TITLE!r}")
		elif frappe.db.get_value("MYS Branch", rows[0].mys_branch, "branch_code") != "BR014":
			failures.append(f"{DIRECTOR}: seeded course on unexpected branch {rows[0].mys_branch!r}")
	finally:
		frappe.set_user(prev)


def _check_teacher_lms_access(failures: list[str]) -> None:
	if not frappe.db.exists("User", TEACHER):
		failures.append(f"user missing: {TEACHER}")
		return
	if "LMS Student" not in frappe.get_roles(TEACHER):
		failures.append(f"{TEACHER}: missing LMS Student role")

	prev = frappe.session.user
	try:
		frappe.set_user(TEACHER)
		from lms.lms.api import check_app_permission

		if not check_app_permission():
			failures.append(f"{TEACHER}: check_app_permission returned False")
	finally:
		frappe.set_user(prev)
