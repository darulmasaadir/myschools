"""Fee structure resolution and late-fee automation.

Fee structure precedence (on a given date):
  1. Campus-level MYS Fee Structure Override
  2. Branch-level MYS Fee Structure Override (campus blank)
  3. Company default Fee Structure for program + academic year

Late fees: daily scheduler finds submitted Fees with outstanding balance past
due_date + policy grace_days, creates a linked late-fee Fees document, and
marks the parent so we do not double-charge.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, today

LATE_FEE_CATEGORY = "Late Fee"


def resolve_fee_structure(
	branch: str,
	program: str,
	academic_year: str,
	company: str,
	campus: str | None = None,
	on_date=None,
) -> tuple[str | None, str]:
	"""Return (fee_structure_name, source).

	source is one of: campus_override | branch_override | default
	"""
	on_date = getdate(on_date or today())

	if campus:
		fs = _lookup_fee_override(branch, campus, program, academic_year, on_date)
		if fs:
			return fs, "campus_override"

	fs = _lookup_fee_override(branch, None, program, academic_year, on_date)
	if fs:
		return fs, "branch_override"

	default = frappe.db.get_value(
		"Fee Structure",
		{"program": program, "academic_year": academic_year, "company": company},
		"name",
	)
	return default, "default"


def _lookup_fee_override(branch, campus, program, academic_year, on_date) -> str | None:
	filters = {
		"branch": branch,
		"program": program,
		"academic_year": academic_year,
		"is_active": 1,
		"effective_from": ["<=", on_date],
	}
	if campus:
		filters["campus"] = campus
	else:
		filters["campus"] = ["in", ["", None]]

	candidates = frappe.get_all(
		"MYS Fee Structure Override",
		filters=filters,
		fields=["name", "fee_structure", "effective_from", "effective_to"],
		order_by="effective_from DESC",
		limit=10,
	)
	for row in candidates:
		if row.effective_to and getdate(row.effective_to) < on_date:
			continue
		return row.fee_structure
	return None


def resolve_late_fee_policy(
	branch: str,
	campus: str | None = None,
	on_date=None,
) -> frappe._dict | None:
	"""Return the active late-fee policy for branch/campus on a date."""
	on_date = getdate(on_date or today())
	if campus:
		policy = _lookup_late_fee_policy(branch, campus, on_date)
		if policy:
			return policy
	return _lookup_late_fee_policy(branch, None, on_date)


def _lookup_late_fee_policy(branch, campus, on_date) -> frappe._dict | None:
	filters = {
		"branch": branch,
		"is_active": 1,
		"effective_from": ["<=", on_date],
	}
	if campus:
		filters["campus"] = campus
	else:
		filters["campus"] = ["in", ["", None]]

	rows = frappe.get_all(
		"MYS Late Fee Policy",
		filters=filters,
		fields=[
			"name",
			"grace_days",
			"late_fee_percent",
			"late_fee_minimum",
			"fees_category",
			"effective_from",
			"effective_to",
		],
		order_by="effective_from DESC",
		limit=5,
	)
	for row in rows:
		if row.effective_to and getdate(row.effective_to) < on_date:
			continue
		return frappe._dict(row)
	return None


def compute_late_fee_amount(outstanding: float, policy: frappe._dict) -> float:
	"""Late fee = max(minimum, outstanding * percent / 100)."""
	percent_amt = flt(outstanding) * flt(policy.late_fee_percent) / 100.0
	return max(flt(policy.late_fee_minimum), percent_amt)


def apply_late_fees(dry_run: bool = False) -> list[dict]:
	"""Create late-fee Fees for overdue parent invoices. Returns summary rows."""
	_run_date = today()
	results: list[dict] = []

	parents = frappe.db.sql(
		"""
		SELECT
			fees.name,
			fees.student,
			fees.program_enrollment,
			fees.fee_structure,
			fees.company,
			fees.receivable_account,
			fees.academic_year,
			fees.academic_term,
			fees.due_date,
			fees.outstanding_amount,
			student.mys_branch AS branch,
			student.mys_campus AS campus
		FROM `tabFees` fees
		INNER JOIN `tabStudent` student ON student.name = fees.student
		WHERE fees.docstatus = 1
			AND fees.outstanding_amount > 0
			AND fees.due_date IS NOT NULL
			AND IFNULL(fees.mys_late_fee_applied, 0) = 0
			AND IFNULL(fees.mys_late_fee_for, '') = ''
		""",
		as_dict=True,
	)

	for row in parents:
		if not row.branch:
			continue
		policy = resolve_late_fee_policy(row.branch, row.campus, _run_date)
		if not policy:
			continue
		threshold = add_days(row.due_date, policy.grace_days)
		if getdate(_run_date) <= getdate(threshold):
			continue

		amount = compute_late_fee_amount(row.outstanding_amount, policy)
		if amount <= 0:
			continue

		entry = {
			"parent_fee": row.name,
			"branch": row.branch,
			"amount": amount,
			"status": "skipped",
		}

		if dry_run:
			entry["status"] = "dry_run"
			results.append(entry)
			continue

		if not frappe.db.exists("Fee Category", policy.fees_category or LATE_FEE_CATEGORY):
			entry["status"] = "no_fee_category"
			results.append(entry)
			continue

		late = frappe.get_doc(
			{
				"doctype": "Fees",
				"student": row.student,
				"program_enrollment": row.program_enrollment,
				"fee_structure": row.fee_structure,
				"company": row.company,
				"receivable_account": row.receivable_account,
				"academic_year": row.academic_year,
				"academic_term": row.academic_term,
				"posting_date": _run_date,
				"due_date": add_days(_run_date, policy.grace_days),
				"components": [
					{
						"fees_category": policy.fees_category or LATE_FEE_CATEGORY,
						"amount": amount,
						"description": _("Late fee for {0}").format(row.name),
					}
				],
				"mys_late_fee_for": row.name,
			}
		)
		late.insert(ignore_permissions=True)
		late.submit()
		frappe.db.set_value("Fees", row.name, "mys_late_fee_applied", 1, update_modified=False)
		entry["status"] = "created"
		entry["late_fee"] = late.name
		results.append(entry)

	if not dry_run:
		frappe.db.commit()
	return results


def scheduled_apply_late_fees():
	"""Daily job — apply late fees for all eligible branches."""
	apply_late_fees(dry_run=False)


def apply_resolved_fee_structure_on_fees(doc, method=None):
	"""Default `Fees.fee_structure` from MYS override resolution (8a-3).

	Skips late-fee rows (they copy the parent's structure). When blank, sets the
	resolved structure. When set but differs from an active campus/branch override,
	shows a non-blocking alert so operators know MY School will not see Sales
	Invoices from Fee Schedule (see billing-model.md).
	"""
	if doc.get("mys_late_fee_for"):
		return
	if not doc.student:
		return

	branch, campus = frappe.db.get_value("Student", doc.student, ["mys_branch", "mys_campus"]) or (None, None)
	if not branch:
		return

	program, academic_year = _fees_program_and_year(doc)
	if not program or not academic_year or not doc.company:
		return

	resolved, source = resolve_fee_structure(
		branch, program, academic_year, doc.company, campus=campus or None
	)
	if not resolved:
		return

	if not doc.fee_structure:
		doc.fee_structure = resolved
		return

	if doc.fee_structure == resolved:
		return

	if source in ("campus_override", "branch_override"):
		frappe.msgprint(
			_(
				"Fee Structure {0} does not match the active {1} override ({2}). "
				"MY School billing uses Fees — not Fee Schedule → Sales Invoice."
			).format(
				frappe.bold(doc.fee_structure),
				source.replace("_", " "),
				frappe.bold(resolved),
			),
			indicator="orange",
			alert=True,
		)


def _fees_program_and_year(doc) -> tuple[str | None, str | None]:
	program = doc.get("program")
	academic_year = doc.get("academic_year")
	if doc.get("program_enrollment"):
		pe = frappe.db.get_value(
			"Program Enrollment",
			doc.program_enrollment,
			["program", "academic_year"],
			as_dict=True,
		)
		if pe:
			program = program or pe.program
			academic_year = academic_year or pe.academic_year
	return program, academic_year


@frappe.whitelist()
def generate_bulk_fees_for_run(run: str) -> dict:
	"""Create submitted `Fees` rows for students in a Student Group (8a-4).

	Uses `resolve_fee_structure` per student (campus/branch override). Skips students
	who already have a submitted Fee for the same enrollment + posting_date.
	"""
	run_doc = frappe.get_doc("MYS Bulk Fee Run", run)
	if run_doc.status == "In Process":
		frappe.throw(_("This run is already in progress"))
	if not run_doc.company:
		frappe.throw(_("Branch has no Company linked"))

	run_doc.status = "In Process"
	run_doc.save(ignore_permissions=True)
	frappe.db.commit()

	receivable = _company_receivable(run_doc.company)
	rows = _students_for_bulk_run(run_doc)
	lines = []
	counts = {"created": 0, "skipped": 0, "failed": 0}

	for row in rows:
		line = {
			"student": row.student,
			"program_enrollment": row.enrollment,
			"status": "Failed",
			"message": "",
		}
		try:
			existing = _existing_submitted_fee_for_enrollment(row.enrollment, run_doc.posting_date)
			if existing:
				line["status"] = "Skipped"
				line["fees"] = existing
				line["message"] = _("Already billed for this enrollment on {0}").format(run_doc.posting_date)
				counts["skipped"] += 1
				lines.append(line)
				continue

			fs, _source = resolve_fee_structure(
				run_doc.branch,
				row.program,
				run_doc.academic_year,
				run_doc.company,
				campus=row.campus or None,
			)
			if not fs:
				line["message"] = _("No Fee Structure for program/year/company")
				counts["failed"] += 1
				lines.append(line)
				continue

			components = _fee_structure_components(fs)
			if not components:
				line["message"] = _("Fee Structure has no components")
				counts["failed"] += 1
				lines.append(line)
				continue

			fee = frappe.get_doc(
				{
					"doctype": "Fees",
					"student": row.student,
					"program_enrollment": row.enrollment,
					"program": row.program,
					"fee_structure": fs,
					"company": run_doc.company,
					"receivable_account": receivable,
					"academic_year": run_doc.academic_year,
					"academic_term": run_doc.academic_term or row.academic_term,
					"posting_date": run_doc.posting_date,
					"due_date": run_doc.due_date,
					"components": components,
				}
			)
			fee.insert(ignore_permissions=True)
			if run_doc.submit_fees:
				fee.submit()

			line["status"] = "Created"
			line["fees"] = fee.name
			line["fee_structure"] = fs
			line["message"] = _("OK")
			counts["created"] += 1
		except Exception as exc:
			line["message"] = str(exc)
			counts["failed"] += 1
		lines.append(line)

	run_doc.lines = []
	for line in lines:
		run_doc.append("lines", line)

	total = len(rows)
	if counts["failed"] == total and total:
		run_doc.status = "Failed"
	elif counts["failed"] or counts["skipped"]:
		run_doc.status = "Partial" if counts["created"] else "Failed"
	else:
		run_doc.status = "Completed"

	run_doc.summary = _("Created: {created}, Skipped: {skipped}, Failed: {failed}").format(**counts)
	run_doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {"status": run_doc.status, "summary": run_doc.summary, **counts}


def _students_for_bulk_run(run) -> list[frappe._dict]:
	"""Active group members with submitted enrollment on this branch."""
	term_clause = ""
	params: list = [run.academic_year, run.student_group, run.branch]
	if run.academic_term:
		term_clause = " AND pe.academic_term = %s"
		params.append(run.academic_term)
	program_clause = ""
	if run.program:
		program_clause = " AND pe.program = %s"
		params.append(run.program)

	return frappe.db.sql(
		f"""
		SELECT
			pe.student AS student,
			pe.name AS enrollment,
			pe.program AS program,
			pe.academic_term AS academic_term,
			stu.mys_campus AS campus
		FROM `tabStudent Group Student` sgs
		INNER JOIN `tabProgram Enrollment` pe
			ON pe.student = sgs.student
			AND pe.docstatus = 1
			AND pe.academic_year = %s
		INNER JOIN `tabStudent` stu ON stu.name = pe.student
		WHERE sgs.parent = %s
			AND IFNULL(sgs.active, 0) = 1
			AND stu.mys_branch = %s
			{term_clause}
			{program_clause}
		""",
		tuple(params),
		as_dict=True,
	)


def _fee_structure_components(fee_structure: str) -> list[dict]:
	fs = frappe.get_doc("Fee Structure", fee_structure)
	return [{"fees_category": row.fees_category, "amount": row.amount} for row in fs.components]


def _existing_submitted_fee_for_enrollment(enrollment: str, posting_date) -> str | None:
	return frappe.db.get_value(
		"Fees",
		{
			"program_enrollment": enrollment,
			"posting_date": posting_date,
			"docstatus": 1,
		},
		"name",
	)


def _company_receivable(company: str) -> str:
	acc = frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Receivable", "is_group": 0},
		"name",
	)
	if not acc:
		frappe.throw(_("No receivable account for company {0}").format(company))
	return acc


def fee_structure_override_query(user):
	from myschools.api.permissions import _user_scope

	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Fee Structure Override`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Fee Structure Override`.branch IN ({in_list})"


def late_fee_policy_query(user):
	from myschools.api.permissions import _user_scope

	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Late Fee Policy`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Late Fee Policy`.branch IN ({in_list})"


def bulk_fee_run_query(user):
	from myschools.api.permissions import _user_scope

	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return "`tabMYS Bulk Fee Run`.branch = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tabMYS Bulk Fee Run`.branch IN ({in_list})"
