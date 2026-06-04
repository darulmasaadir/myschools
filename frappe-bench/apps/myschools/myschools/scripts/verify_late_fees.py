"""End-to-end verification for Phase 8a late-fee automation (run via bench execute).

Unlike tests/test_fees.py (which calls apply_late_fees() inside a rolled-back
test transaction), this exercises the REAL scheduler entrypoint
`scheduled_apply_late_fees()` against the live site DB, then asserts the late
Fees document was created, linked, and the parent flagged — and that the
branch-scoped permission query resolves. All data is created under a unique
`_VERIFY_LF_` prefix and torn down in a finally block, pass or fail.

    bench --site SITE execute myschools.scripts.verify_late_fees.run
"""

from __future__ import annotations

from datetime import date

import frappe
from frappe.utils import add_days, today

from myschools.api.fees import (
	fee_structure_override_query,
	resolve_fee_structure,
	scheduled_apply_late_fees,
)

P = "_VERIFY_LF_"
CLUSTER = f"{P}CL"
BRANCH = f"{P}BR"
CAMPUS = f"{BRANCH}-Kids"
PROGRAM = f"{P}PROG"
ACADEMIC_YEAR = f"{P}AY"
ACADEMIC_TERM_NAME = f"{P}TERM"
ACADEMIC_TERM = f"{ACADEMIC_YEAR} ({ACADEMIC_TERM_NAME})"
FEE_CATEGORY = f"{P}TUITION"
LATE_CATEGORY = f"{P}LATE"
DEFAULT_FS_AMOUNT = 100_000
OVERRIDE_FS_AMOUNT = 120_000
PARENT_AMOUNT = 10_000
STUDENT_EMAIL = f"{P}late@example.test"

YEAR_START = date(2025, 8, 1)
YEAR_END = date(2026, 7, 31)
TERM_START = date(2025, 9, 1)
TERM_END = date(2026, 6, 30)


def run():
	failures: list[str] = []
	created = {}
	# Pre-clean any leftover from an interrupted prior run so reruns are robust.
	_purge_residual()
	try:
		_setup(created)

		# 1. Fee-structure resolution precedence (campus > branch > default).
		fs, source = resolve_fee_structure(BRANCH, PROGRAM, ACADEMIC_YEAR, created["company"], campus=None)
		if source != "branch_override" or fs != created["override_fs"]:
			failures.append(f"resolve_fee_structure: got ({fs!r}, {source!r}), expected branch_override")

		# 2. Permission query is branch-scoped, not global, for a branch user.
		_check_permission_query(failures)

		# 3. THE REAL SCHEDULER ENTRYPOINT — fire the cron function itself.
		scheduled_apply_late_fees()

		# 4. Assert a linked, submitted late fee exists for our parent + parent flagged.
		parent = created["parent_fee"]
		late = frappe.get_all(
			"Fees",
			filters={"mys_late_fee_for": parent},
			fields=["name", "docstatus", "grand_total"],
		)
		if len(late) != 1:
			failures.append(f"expected exactly 1 late fee for {parent}, found {len(late)}")
		else:
			created["late_fee"] = late[0].name
			if late[0].docstatus != 1:
				failures.append(f"late fee {late[0].name} not submitted (docstatus={late[0].docstatus})")
			# 10% of 10_000 = 1_000, above the 500 minimum.
			if abs((late[0].grand_total or 0) - 1_000) > 0.01:
				failures.append(f"late fee amount {late[0].grand_total}, expected 1000")
		if not frappe.db.get_value("Fees", parent, "mys_late_fee_applied"):
			failures.append(f"parent {parent} mys_late_fee_applied not set")

		# 5. Idempotency — second scheduler run creates no new late fee.
		scheduled_apply_late_fees()
		again = frappe.get_all("Fees", filters={"mys_late_fee_for": parent}, pluck="name")
		if len(again) != 1:
			failures.append(f"idempotency broken: {len(again)} late fees after 2nd run")
	finally:
		_teardown(created)

	if failures:
		print("FAILED —", len(failures), "issue(s):")
		for f in failures:
			print(f"  x {f}")
		frappe.throw("Late-fee e2e verification failed")
	print(
		"OK — scheduled_apply_late_fees created 1 linked late fee (PKR 1000), "
		"flagged parent, was idempotent, and resolution + permission query held."
	)


def _check_permission_query(failures: list[str]) -> None:
	"""Assert the override permission query is branch-scoped, not global.

	Reuses an already-seeded branch user (seed_test_users) when present so we
	don't create/delete a throwaway User on a live DB. Administrator must get
	the unrestricted ("") query; a branch user must get a non-empty, non-"__none__"
	branch-scoped condition.
	"""
	if fee_structure_override_query("Administrator") != "":
		failures.append("permission query should be unrestricted ('') for Administrator")

	branch_user = "accountant@mys.local"
	if not frappe.db.exists("User", branch_user):
		print(f"  (skip) branch-user permission check — {branch_user} not seeded on this site")
		return
	cond = fee_structure_override_query(branch_user)
	if cond == "" or "__none__" in cond:
		failures.append(f"permission query for branch user too broad/narrow: {cond!r}")
	elif "`tabMYS Fee Structure Override`.branch IN" not in cond:
		failures.append(f"permission query not branch-scoped: {cond!r}")


def _setup(created: dict) -> None:
	company = frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw("No Company on site for late-fee verification")
	created["company"] = company
	receivable = frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Receivable", "is_group": 0},
		"name",
	)
	if not receivable:
		frappe.throw("No receivable account for late-fee verification")
	created["receivable"] = receivable

	_ensure("Fee Category", FEE_CATEGORY, {"category_name": FEE_CATEGORY})
	_ensure("Fee Category", LATE_CATEGORY, {"category_name": LATE_CATEGORY})
	_ensure(
		"Academic Year",
		ACADEMIC_YEAR,
		{"academic_year_name": ACADEMIC_YEAR, "year_start_date": YEAR_START, "year_end_date": YEAR_END},
	)
	_ensure(
		"Academic Term",
		ACADEMIC_TERM,
		{
			"academic_year": ACADEMIC_YEAR,
			"term_name": ACADEMIC_TERM_NAME,
			"term_start_date": TERM_START,
			"term_end_date": TERM_END,
		},
	)
	_ensure("Program", PROGRAM, {"program_name": PROGRAM, "program_code": PROGRAM})
	_ensure("MYS Cluster", CLUSTER, {"cluster_code": CLUSTER, "cluster_name": CLUSTER, "region": "Test"})
	_ensure(
		"MYS Branch",
		BRANCH,
		{
			"branch_code": BRANCH,
			"branch_name": BRANCH,
			"cluster": CLUSTER,
			"city": "Test",
			"province": "Test",
			"is_active": 1,
			"company": company,
		},
	)
	if not frappe.db.exists("MYS Campus", CAMPUS):
		frappe.get_doc(
			{"doctype": "MYS Campus", "branch": BRANCH, "campus_type": "Kids", "is_active": 1}
		).insert(ignore_permissions=True)

	default_fs = frappe.get_doc(
		{
			"doctype": "Fee Structure",
			"program": PROGRAM,
			"academic_year": ACADEMIC_YEAR,
			"company": company,
			"receivable_account": receivable,
			"components": [{"fees_category": FEE_CATEGORY, "amount": DEFAULT_FS_AMOUNT}],
		}
	).insert(ignore_permissions=True)
	created["default_fs"] = default_fs.name
	override_fs = frappe.get_doc(
		{
			"doctype": "Fee Structure",
			"program": PROGRAM,
			"academic_year": ACADEMIC_YEAR,
			"company": company,
			"receivable_account": receivable,
			"components": [{"fees_category": FEE_CATEGORY, "amount": OVERRIDE_FS_AMOUNT}],
		}
	).insert(ignore_permissions=True)
	created["override_fs"] = override_fs.name

	frappe.get_doc(
		{
			"doctype": "MYS Fee Structure Override",
			"branch": BRANCH,
			"program": PROGRAM,
			"academic_year": ACADEMIC_YEAR,
			"fee_structure": override_fs.name,
			"effective_from": "2025-01-01",
			"is_active": 1,
		}
	).insert(ignore_permissions=True)
	frappe.get_doc(
		{
			"doctype": "MYS Late Fee Policy",
			"branch": BRANCH,
			"grace_days": 7,
			"late_fee_percent": 10,
			"late_fee_minimum": 500,
			"fees_category": LATE_CATEGORY,
			"effective_from": "2025-01-01",
			"is_active": 1,
		}
	).insert(ignore_permissions=True)

	student = frappe.get_doc(
		{
			"doctype": "Student",
			"first_name": "VerifyLF",
			"last_name": "Student",
			"student_email_id": STUDENT_EMAIL,
			"mys_cluster": CLUSTER,
			"mys_branch": BRANCH,
			"mys_campus": CAMPUS,
		}
	).insert(ignore_permissions=True)
	created["student"] = student.name

	pe = frappe.get_doc(
		{
			"doctype": "Program Enrollment",
			"student": student.name,
			"program": PROGRAM,
			"academic_year": ACADEMIC_YEAR,
			"academic_term": ACADEMIC_TERM,
			"enrollment_date": today(),
		}
	)
	pe.insert(ignore_permissions=True)
	pe.submit()
	created["enrollment"] = pe.name

	parent = frappe.get_doc(
		{
			"doctype": "Fees",
			"student": student.name,
			"program_enrollment": pe.name,
			"fee_structure": default_fs.name,
			"company": company,
			"receivable_account": receivable,
			"academic_year": ACADEMIC_YEAR,
			"academic_term": ACADEMIC_TERM,
			"posting_date": add_days(today(), -30),
			"due_date": add_days(today(), -20),
			"components": [{"fees_category": FEE_CATEGORY, "amount": PARENT_AMOUNT}],
		}
	)
	parent.insert(ignore_permissions=True)
	parent.submit()
	created["parent_fee"] = parent.name
	frappe.db.commit()


def _purge_residual() -> None:
	"""Delete any leftover _VERIFY_LF_ data from an interrupted prior run."""
	for stu in frappe.get_all("Student", {"student_email_id": STUDENT_EMAIL}, pluck="name"):
		for fee in frappe.get_all("Fees", {"student": stu}, pluck="name"):
			doc = frappe.get_doc("Fees", fee)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Fees", fee, force=True, ignore_permissions=True)
		for pe in frappe.get_all("Program Enrollment", {"student": stu}, pluck="name"):
			doc = frappe.get_doc("Program Enrollment", pe)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Program Enrollment", pe, force=True, ignore_permissions=True)
		frappe.delete_doc("Student", stu, force=True, ignore_permissions=True)
	_teardown({})
	frappe.db.commit()


def _ensure(doctype: str, name: str, values: dict) -> None:
	if not frappe.db.exists(doctype, name):
		frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)


def _teardown(created: dict) -> None:
	def _del_fee(name):
		if name and frappe.db.exists("Fees", name):
			doc = frappe.get_doc("Fees", name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Fees", name, force=True, ignore_permissions=True)

	_del_fee(created.get("late_fee"))
	for late in frappe.get_all(
		"Fees", {"mys_late_fee_for": created.get("parent_fee") or "__x__"}, pluck="name"
	):
		_del_fee(late)
	_del_fee(created.get("parent_fee"))

	if created.get("enrollment") and frappe.db.exists("Program Enrollment", created["enrollment"]):
		pe = frappe.get_doc("Program Enrollment", created["enrollment"])
		if pe.docstatus == 1:
			pe.cancel()
		frappe.delete_doc("Program Enrollment", created["enrollment"], force=True, ignore_permissions=True)
	if created.get("student") and frappe.db.exists("Student", created["student"]):
		frappe.delete_doc("Student", created["student"], force=True, ignore_permissions=True)

	frappe.db.delete("MYS Fee Structure Override", {"branch": BRANCH})
	frappe.db.delete("MYS Late Fee Policy", {"branch": BRANCH})
	for fs in (created.get("default_fs"), created.get("override_fs")):
		if fs and frappe.db.exists("Fee Structure", fs):
			frappe.delete_doc("Fee Structure", fs, force=True, ignore_permissions=True)

	if frappe.db.exists("MYS Campus", CAMPUS):
		frappe.delete_doc("MYS Campus", CAMPUS, force=True, ignore_permissions=True)
	if frappe.db.exists("MYS Branch", BRANCH):
		frappe.delete_doc("MYS Branch", BRANCH, force=True, ignore_permissions=True)
	if frappe.db.exists("MYS Cluster", CLUSTER):
		frappe.delete_doc("MYS Cluster", CLUSTER, force=True, ignore_permissions=True)
	if frappe.db.exists("Program", PROGRAM):
		frappe.delete_doc("Program", PROGRAM, force=True, ignore_permissions=True)
	if frappe.db.exists("Academic Term", ACADEMIC_TERM):
		frappe.delete_doc("Academic Term", ACADEMIC_TERM, force=True, ignore_permissions=True)
	if frappe.db.exists("Academic Year", ACADEMIC_YEAR):
		frappe.delete_doc("Academic Year", ACADEMIC_YEAR, force=True, ignore_permissions=True)
	for cat in (FEE_CATEGORY, LATE_CATEGORY):
		if frappe.db.exists("Fee Category", cat):
			frappe.delete_doc("Fee Category", cat, force=True, ignore_permissions=True)
	frappe.db.commit()
