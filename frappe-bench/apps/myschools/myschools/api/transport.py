"""Phase 12 — Transport: routes, vehicles, student assignments + fee billing.

Transport rides on the existing Fees engine: ``generate_transport_fee`` creates a
single submitted ``Fees`` document with a ``Transport Fee`` category component,
rather than introducing a parallel billing ledger. Franchise scoping mirrors the
rest of the app via ``permission_query_conditions`` keyed on ``branch``.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, today

TRANSPORT_FEE_CATEGORY = "Transport Fee"


# ---------------------------------------------------------------------------
# Permission query conditions (desk row scoping)
# ---------------------------------------------------------------------------
def _branch_scope(user: str):
	from myschools.api.permissions import _user_scope

	return _user_scope(user)


def vehicle_query(user):
	scope, branches = _branch_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Vehicle`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Vehicle`.branch IN ({in_list})"


def transport_route_query(user):
	scope, branches = _branch_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Transport Route`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Transport Route`.branch IN ({in_list})"


def student_transport_query(user):
	scope, branches = _branch_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Student Transport`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Student Transport`.branch IN ({in_list})"


# ---------------------------------------------------------------------------
# Validation (called from the MYS Student Transport controller)
# ---------------------------------------------------------------------------
def validate_student_transport(doc) -> None:
	"""Keep assignment branch-consistent and within vehicle capacity."""
	if not doc.student or not doc.route:
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

	route_branch = frappe.db.get_value("MYS Transport Route", doc.route, "branch")
	if route_branch and route_branch != student_branch:
		frappe.throw(
			_("Route {0} (branch {1}) does not serve the student's branch {2}.").format(
				doc.route, route_branch, student_branch
			)
		)

	if doc.fee_amount in (None, ""):
		doc.fee_amount = frappe.db.get_value("MYS Transport Route", doc.route, "fee_amount") or 0

	if (doc.status or "Active") == "Active":
		_assert_capacity(doc)


def _assert_capacity(doc) -> None:
	"""Block a new active assignment that would exceed the vehicle's capacity."""
	vehicle = frappe.db.get_value("MYS Transport Route", doc.route, "vehicle")
	if not vehicle:
		return
	capacity = frappe.db.get_value("MYS Vehicle", vehicle, "capacity")
	if not capacity:
		return

	routes = frappe.get_all("MYS Transport Route", filters={"vehicle": vehicle}, pluck="name")
	if not routes:
		return

	filters = {
		"route": ["in", routes],
		"status": "Active",
	}
	if not doc.is_new():
		filters["name"] = ["!=", doc.name]
	active = frappe.db.count("MYS Student Transport", filters)
	if active + 1 > capacity:
		frappe.throw(
			_("Vehicle {0} is at capacity ({1}). Cannot add another active rider.").format(vehicle, capacity)
		)


# ---------------------------------------------------------------------------
# Fee Category bootstrap (idempotent — called from install)
# ---------------------------------------------------------------------------
def ensure_transport_fee_category() -> None:
	"""Idempotent — safe to call from after_migrate or before billing."""
	if not frappe.db.exists("DocType", "Fee Category"):
		return
	if frappe.db.exists("Fee Category", TRANSPORT_FEE_CATEGORY):
		return
	# Education's after_insert creates an ERPNext Item (needs stock UOM).
	if not frappe.db.get_all("UOM", limit=1):
		return
	try:
		frappe.get_doc(
			{
				"doctype": "Fee Category",
				"category_name": TRANSPORT_FEE_CATEGORY,
				"description": "Monthly student transport charges (Phase 12).",
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
	"""Latest submitted Program Enrollment for the student (Fees requires one)."""
	return frappe.db.get_value(
		"Program Enrollment",
		{"student": student, "docstatus": 1},
		"name",
		order_by="enrollment_date desc",
	)


def _enrollment_billing_context(student: str, branch: str, enrollment: str) -> dict | None:
	"""Program/year/term + resolved Fee Structure for a transport invoice."""
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


def generate_transport_fee(student_transport: str, posting_date: str | None = None) -> dict:
	"""Create one submitted ``Fees`` doc for a student's monthly transport charge.

	Returns ``{"status", "fees"?, "message"?}``. Skips when an unbilled assignment
	is stopped, the amount is zero, the branch has no company, or a transport Fee
	already exists for this assignment + posting_date.
	"""
	from myschools.api.fees import _company_receivable

	posting_date = posting_date or today()
	st = frappe.get_doc("MYS Student Transport", student_transport)

	if (st.status or "Active") != "Active":
		return {"status": "skipped", "message": _("Assignment is not active")}

	amount = flt(st.fee_amount)
	if amount <= 0:
		return {"status": "skipped", "message": _("No transport fee amount set")}

	if not frappe.db.exists("Fee Category", TRANSPORT_FEE_CATEGORY):
		ensure_transport_fee_category()
		if not frappe.db.exists("Fee Category", TRANSPORT_FEE_CATEGORY):
			return {"status": "no_fee_category", "message": _("Transport Fee category missing")}

	company = _branch_company(st.branch)
	if not company:
		return {"status": "skipped", "message": _("Branch {0} has no Company linked").format(st.branch)}

	enrollment = _student_enrollment(st.student)
	if not enrollment:
		return {"status": "skipped", "message": _("Student has no submitted Program Enrollment")}

	billing = _enrollment_billing_context(st.student, st.branch, enrollment)
	if not billing:
		return {"status": "skipped", "message": _("No Fee Structure for student program/year")}

	if _existing_transport_fee(st.name, posting_date):
		return {"status": "skipped", "message": _("Already billed for {0}").format(posting_date)}

	fee = frappe.get_doc(
		{
			"doctype": "Fees",
			"student": st.student,
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
					"fees_category": TRANSPORT_FEE_CATEGORY,
					"amount": amount,
					"description": _("Transport — route {0}").format(st.route),
				}
			],
			"mys_transport_for": st.name,
		}
	)
	fee.insert(ignore_permissions=True)
	fee.submit()
	return {"status": "created", "fees": fee.name}


def _existing_transport_fee(student_transport: str, posting_date: str) -> str | None:
	return frappe.db.get_value(
		"Fees",
		{
			"mys_transport_for": student_transport,
			"posting_date": posting_date,
			"docstatus": ["<", 2],
		},
		"name",
	)


@frappe.whitelist()
def generate_transport_fees_for_branch(branch: str, posting_date: str | None = None) -> dict:
	"""Bill every active transport assignment in a branch for one posting date."""
	posting_date = posting_date or today()
	names = frappe.get_all(
		"MYS Student Transport",
		filters={"branch": branch, "status": "Active"},
		pluck="name",
	)
	counts = {"created": 0, "skipped": 0, "failed": 0}
	lines = []
	for name in names:
		try:
			result = generate_transport_fee(name, posting_date)
			status = "created" if result.get("status") == "created" else "skipped"
			counts["created" if status == "created" else "skipped"] += 1
			lines.append({"student_transport": name, **result})
		except Exception as exc:  # surface per-row failures, keep billing the rest
			counts["failed"] += 1
			lines.append({"student_transport": name, "status": "failed", "message": str(exc)})
	return {"counts": counts, "lines": lines}


# ---------------------------------------------------------------------------
# Guardian portal read access
# ---------------------------------------------------------------------------
def get_transport_for_guardian(guardian: frappe.Document) -> list[dict]:
	"""Active + stopped transport assignments for the guardian's linked students."""
	from myschools.api.guardian_portal import get_linked_student_ids

	student_ids = get_linked_student_ids(guardian)
	if not student_ids:
		return []
	rows = frappe.get_all(
		"MYS Student Transport",
		filters={"student": ["in", student_ids]},
		fields=[
			"name",
			"student",
			"student_name",
			"route",
			"pickup_point",
			"fee_amount",
			"status",
			"start_date",
		],
		order_by="status asc, student_name asc",
		ignore_permissions=True,
	)
	route_ids = {r["route"] for r in rows if r.get("route")}
	route_names: dict[str, str] = {}
	if route_ids:
		for r in frappe.get_all(
			"MYS Transport Route",
			filters={"name": ["in", list(route_ids)]},
			fields=["name", "route_name"],
		):
			route_names[r["name"]] = r.get("route_name") or r["name"]
	for row in rows:
		row["route_name"] = route_names.get(row.get("route"), row.get("route"))
	return rows
