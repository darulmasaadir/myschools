"""Phase 13 — Library: catalog, loans, overdue fines on the Fees engine.

Library fines ride on the existing ``Fees`` document (``Library Fine`` category +
``mys_library_loan_for`` link), mirroring Phase 12 transport billing — no parallel
ledger. Franchise scoping uses ``permission_query_conditions`` keyed on ``branch``.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

LIBRARY_FINE_CATEGORY = "Library Fine"


# ---------------------------------------------------------------------------
# Permission query conditions (desk row scoping)
# ---------------------------------------------------------------------------
def _branch_scope(user: str):
	from myschools.api.permissions import _user_scope

	return _user_scope(user)


def library_item_query(user):
	scope, branches = _branch_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Library Item`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Library Item`.branch IN ({in_list})"


def library_loan_query(user):
	scope, branches = _branch_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Library Loan`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Library Loan`.branch IN ({in_list})"


# ---------------------------------------------------------------------------
# Validation + copy tracking
# ---------------------------------------------------------------------------
def validate_library_loan(doc) -> None:
	"""Branch consistency, due-date guard, copy availability, fine recalculation."""
	if not doc.student or not doc.library_item:
		return

	student_branch = frappe.db.get_value("Student", doc.student, "mys_branch")
	if not student_branch:
		frappe.throw(
			_("Student {0} has no MYS Branch. Set franchise links on the Student record first.").format(
				frappe.bold(doc.student)
			)
		)
	if not doc.branch:
		doc.branch = student_branch

	item_branch = frappe.db.get_value("MYS Library Item", doc.library_item, "branch")
	if item_branch and item_branch != student_branch:
		frappe.throw(
			_("Library item {0} (branch {1}) is not at the student's branch {2}.").format(
				doc.library_item, item_branch, student_branch
			)
		)

	if doc.fine_per_day in (None, ""):
		doc.fine_per_day = frappe.db.get_value("MYS Library Item", doc.library_item, "fine_per_day") or 0

	if doc.loan_date and doc.due_date and getdate(doc.due_date) < getdate(doc.loan_date):
		frappe.throw(_("Due date cannot be before the loan date."))

	if doc.status == "Returned" and not doc.return_date:
		doc.return_date = today()

	if doc.is_new() and doc.status in ("On Loan", "Overdue"):
		_assert_copy_available(doc.library_item)

	_refresh_overdue_status(doc)
	recalc_library_fine(doc)


def _assert_copy_available(library_item: str) -> None:
	available = frappe.db.get_value("MYS Library Item", library_item, "available_copies") or 0
	if int(available) < 1:
		frappe.throw(_("No copies of {0} are available to loan.").format(library_item))


def adjust_available_copies(library_item: str, delta: int) -> None:
	"""Atomically adjust available copy count (negative delta = loan issued)."""
	current = int(frappe.db.get_value("MYS Library Item", library_item, "available_copies") or 0)
	new_val = current + delta
	total = int(frappe.db.get_value("MYS Library Item", library_item, "total_copies") or 0)
	if new_val < 0:
		frappe.throw(_("Cannot adjust copies below zero for {0}.").format(library_item))
	if new_val > total:
		frappe.throw(_("Available copies cannot exceed total copies for {0}.").format(library_item))
	frappe.db.set_value("MYS Library Item", library_item, "available_copies", new_val, update_modified=False)


def on_loan_inserted(doc) -> None:
	"""Called from controller after_insert — reserve a copy."""
	if doc.status in ("On Loan", "Overdue"):
		adjust_available_copies(doc.library_item, -1)


def _refresh_overdue_status(doc) -> None:
	"""Promote On Loan → Overdue when past due (desk save or scheduler)."""
	if doc.status != "On Loan" or not doc.due_date:
		return
	if getdate(doc.due_date) < getdate(today()):
		doc.status = "Overdue"


def recalc_library_fine(doc) -> None:
	"""Compute days_overdue and fine_amount from dates and fine_per_day."""
	if doc.status not in ("On Loan", "Overdue", "Returned") or not doc.due_date:
		doc.days_overdue = 0
		doc.fine_amount = 0
		return

	end = getdate(doc.return_date) if doc.status == "Returned" and doc.return_date else getdate(today())
	due = getdate(doc.due_date)
	days = max(0, (end - due).days)
	doc.days_overdue = days
	doc.fine_amount = flt(days) * flt(doc.fine_per_day)


def handle_loan_return(doc) -> None:
	"""After a loan is marked Returned — bill any overdue fine once."""
	recalc_library_fine(doc)
	if flt(doc.fine_amount) <= 0 or doc.fine_billed:
		return
	result = generate_library_fine(doc.name)
	if result.get("status") == "created":
		doc.fine_billed = 1


# ---------------------------------------------------------------------------
# Fee Category bootstrap (idempotent — called from after_migrate)
# ---------------------------------------------------------------------------
def ensure_library_fine_category() -> None:
	"""Idempotent — safe to call from after_migrate or before billing."""
	if not frappe.db.exists("DocType", "Fee Category"):
		return
	if frappe.db.exists("Fee Category", LIBRARY_FINE_CATEGORY):
		return
	if not frappe.db.get_all("UOM", limit=1):
		return
	try:
		frappe.get_doc(
			{
				"doctype": "Fee Category",
				"category_name": LIBRARY_FINE_CATEGORY,
				"description": "Overdue library book fines (Phase 13).",
			}
		).insert(ignore_permissions=True)
	except frappe.MandatoryError:
		return


# ---------------------------------------------------------------------------
# Billing — ride the existing Fees engine
# ---------------------------------------------------------------------------
def _branch_company(branch: str) -> str | None:
	return frappe.db.get_value("MYS Branch", branch, "company")


def _student_enrollment(student: str) -> str | None:
	return frappe.db.get_value(
		"Program Enrollment",
		{"student": student, "docstatus": 1},
		"name",
		order_by="enrollment_date desc",
	)


def _enrollment_billing_context(student: str, branch: str, enrollment: str) -> dict | None:
	from myschools.api.fees import resolve_fee_structure

	pe = frappe.db.get_value(
		"Program Enrollment",
		enrollment,
		["program", "academic_year", "academic_term"],
		as_dict=True,
	)
	if not pe:
		return None
	company = _branch_company(branch)
	if not company:
		return None
	campus = frappe.db.get_value("Student", student, "mys_campus")
	fs, _source = resolve_fee_structure(branch, pe.program, pe.academic_year, company, campus=campus or None)
	if not fs:
		return None
	return {**pe, "fee_structure": fs, "company": company}


def generate_library_fine(library_loan: str, posting_date: str | None = None) -> dict:
	"""Create one submitted ``Fees`` doc for an overdue library loan fine.

	Returns ``{"status", "fees"?, "message"?}``. Skips when fine is zero, already
	billed, or billing prerequisites are missing.
	"""
	from myschools.api.fees import _company_receivable

	posting_date = posting_date or today()
	loan = frappe.get_doc("MYS Library Loan", library_loan)

	if loan.fine_billed:
		return {"status": "skipped", "message": _("Fine already billed")}

	recalc_library_fine(loan)
	amount = flt(loan.fine_amount)
	if amount <= 0:
		return {"status": "skipped", "message": _("No fine due")}

	if _existing_library_fine(loan.name):
		frappe.db.set_value("MYS Library Loan", loan.name, "fine_billed", 1, update_modified=False)
		return {"status": "skipped", "message": _("Fine already billed")}

	if not frappe.db.exists("Fee Category", LIBRARY_FINE_CATEGORY):
		ensure_library_fine_category()
		if not frappe.db.exists("Fee Category", LIBRARY_FINE_CATEGORY):
			return {"status": "no_fee_category", "message": _("Library Fine category missing")}

	company = _branch_company(loan.branch)
	if not company:
		return {"status": "skipped", "message": _("Branch {0} has no Company linked").format(loan.branch)}

	enrollment = _student_enrollment(loan.student)
	if not enrollment:
		return {"status": "skipped", "message": _("Student has no submitted Program Enrollment")}

	billing = _enrollment_billing_context(loan.student, loan.branch, enrollment)
	if not billing:
		return {"status": "skipped", "message": _("No Fee Structure for student program/year")}

	item_title = loan.item_title or loan.library_item
	fee = frappe.get_doc(
		{
			"doctype": "Fees",
			"student": loan.student,
			"program_enrollment": enrollment,
			"program": billing["program"],
			"fee_structure": billing["fee_structure"],
			"company": billing["company"],
			"receivable_account": _company_receivable(billing["company"]),
			"academic_year": billing.get("academic_year"),
			"academic_term": billing.get("academic_term"),
			"posting_date": posting_date,
			"due_date": posting_date,
			"components": [
				{
					"fees_category": LIBRARY_FINE_CATEGORY,
					"amount": amount,
					"description": _("Library fine — {0} ({1} days overdue)").format(
						item_title, loan.days_overdue
					),
				}
			],
			"mys_library_loan_for": loan.name,
		}
	)
	fee.insert(ignore_permissions=True)
	fee.submit()
	frappe.db.set_value("MYS Library Loan", loan.name, "fine_billed", 1, update_modified=False)
	return {"status": "created", "fees": fee.name}


def _existing_library_fine(library_loan: str) -> str | None:
	return frappe.db.get_value(
		"Fees",
		{
			"mys_library_loan_for": library_loan,
			"docstatus": ["<", 2],
		},
		"name",
	)


@frappe.whitelist()
def return_library_loan(library_loan: str, return_date: str | None = None) -> dict:
	"""Mark a loan Returned, restore the copy, and bill any overdue fine."""
	loan = frappe.get_doc("MYS Library Loan", library_loan)
	if loan.status == "Returned":
		return {"status": "skipped", "message": _("Already returned")}
	loan.status = "Returned"
	loan.return_date = return_date or today()
	loan.save()
	return {"status": "returned", "loan": loan.name, "fine_billed": bool(loan.fine_billed)}


@frappe.whitelist()
def apply_library_fines_for_branch(branch: str, posting_date: str | None = None) -> dict:
	"""Bill overdue fines for all unbilled Overdue loans in a branch."""
	posting_date = posting_date or today()
	names = frappe.get_all(
		"MYS Library Loan",
		filters={"branch": branch, "status": "Overdue", "fine_billed": 0},
		pluck="name",
	)
	counts = {"created": 0, "skipped": 0, "failed": 0}
	lines = []
	for name in names:
		try:
			result = generate_library_fine(name, posting_date)
			status = "created" if result.get("status") == "created" else "skipped"
			counts["created" if status == "created" else "skipped"] += 1
			lines.append({"library_loan": name, **result})
		except Exception as exc:
			counts["failed"] += 1
			lines.append({"library_loan": name, "status": "failed", "message": str(exc)})
	return {"counts": counts, "lines": lines}


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------
def scheduled_mark_library_overdue() -> None:
	"""Daily — promote On Loan rows past due_date to Overdue."""
	frappe.db.sql(
		"""
		UPDATE `tabMYS Library Loan`
		SET status = 'Overdue'
		WHERE status = 'On Loan' AND due_date < %(today)s
		""",
		{"today": today()},
	)
	frappe.db.commit()


# ---------------------------------------------------------------------------
# Guardian portal read access
# ---------------------------------------------------------------------------
def get_loans_for_guardian(guardian: frappe.Document) -> list[dict]:
	"""Open and recent loans for the guardian's linked students."""
	from myschools.api.guardian_portal import get_linked_student_ids

	student_ids = get_linked_student_ids(guardian)
	if not student_ids:
		return []
	return frappe.get_all(
		"MYS Library Loan",
		filters={"student": ["in", student_ids]},
		fields=[
			"name",
			"student",
			"student_name",
			"library_item",
			"item_title",
			"loan_date",
			"due_date",
			"return_date",
			"status",
			"days_overdue",
			"fine_amount",
			"fine_billed",
		],
		order_by="status asc, due_date desc",
		ignore_permissions=True,
	)
