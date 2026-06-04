"""Idempotent seed for Playwright e2e tests.

Creates (or reuses):
- Test users with predictable passwords for each MYS role we exercise.
- The minimum franchise tree (one Cluster + Branch + Employee inspector)
  that the inspection workflow needs, by chaining `seed_demo.run` when
  the site has only the bare `ci_bootstrap` Company.
- One submitted MYS Royalty Invoice (via `demo_royalty_invoice.run`,
  which pulls in `seed_education.run` for Students + submitted Fees).
- One submitted MYS Inspection Finding at status "Resolved" with
  resolution_notes filled in — that's the state where the role gating
  on Verify is most visible (Audit Officer sees it, Director does not).
- One Overdue MYS Royalty Invoice (status forced via `db.set_value`) so
  the "Send Reminder" button shows up.

Stash returned IDs into /tmp/mys_e2e_state.json so the Playwright spec
can read them without re-discovering through the API.

Run via:
    bench --site myschools.localhost execute myschools.scripts.seed_e2e.main
"""

import json

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, today

STATE_FILE = "/tmp/mys_e2e_state.json"

USERS = {
	"e2e_audit@mys.local": {
		"first_name": "E2E Audit",
		"roles": ["Audit Officer"],
		"password": "mys-e2e-audit",
	},
	"e2e_director@mys.local": {
		"first_name": "E2E Director",
		"roles": ["Branch Director"],
		"password": "mys-e2e-director",
	},
	"e2e_monitor@mys.local": {
		"first_name": "E2E Monitor",
		"roles": ["Academic Monitor"],
		"password": "mys-e2e-monitor",
	},
	"e2e_accountant@mys.local": {
		"first_name": "E2E Accountant",
		"roles": ["Branch Accountant"],
		"password": "mys-e2e-accountant",
	},
}

E2E_BULK_FEE_GROUP = "E2E Bulk Fee BR014"
# Distinct from seed_education.POSTING_DATE so Generate Fees creates rows (not skip).
E2E_BULK_POSTING_DATE = "2026-06-04"
E2E_BULK_DUE_DATE = "2026-06-18"
# Second date for the "new run from blank" spec so it bills fresh Fees instead of
# skipping rows the seeded-draft spec already billed on E2E_BULK_POSTING_DATE.
E2E_BULK_POSTING_DATE_2 = "2026-06-11"
E2E_BULK_DUE_DATE_2 = "2026-06-25"

E2E_CHECKLIST_TAG = "e2e portal checklist"


def _ensure_user(email, spec):
	if not frappe.db.exists("User", email):
		u = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": spec["first_name"],
				"send_welcome_email": 0,
				"enabled": 1,
				"new_password": spec["password"],
			}
		)
		u.insert(ignore_permissions=True)
	u = frappe.get_doc("User", email)
	# Always reset the password so the spec can rely on it.
	from frappe.utils.password import update_password

	update_password(email, spec["password"])
	have = {r.role for r in u.roles}
	for role in spec["roles"]:
		if role not in have:
			u.append("roles", {"role": role})
	u.save(ignore_permissions=True)
	return email


def _ensure_franchise_tree():
	"""Run seed_demo if there's no branch yet. Returns the first branch."""
	branch = frappe.db.get_value("MYS Branch", {}, "name")
	if branch:
		return branch
	# ci_bootstrap creates "MY School Head Office" via ERPNext's setup_complete
	# as a non-group Company. seed_demo creates cluster Companies parented to
	# HO, which requires HO to be a group. Flip it before chaining seed_demo.
	from myschools.scripts import seed_demo

	if frappe.db.exists("Company", seed_demo.HEAD_OFFICE_COMPANY):
		frappe.db.set_value("Company", seed_demo.HEAD_OFFICE_COMPANY, "is_group", 1)
	seed_demo.run()
	return frappe.db.get_value("MYS Branch", {}, "name")


def _ensure_cluster_inspector_employee(email: str, branch: str, first_name: str, last_name: str) -> str:
	"""Link a cluster-role user to an Employee on ``branch`` for portal scope."""
	emp = frappe.db.get_value("Employee", {"user_id": email}, "name")
	if emp:
		frappe.db.set_value(
			"Employee",
			emp,
			{"mys_branch": branch, "status": "Active", "user_id": email},
		)
		return emp
	company = frappe.db.get_value("MYS Branch", branch, "company") or frappe.db.get_value(
		"Company", {}, "name"
	)
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": first_name,
			"last_name": last_name,
			"gender": "Male",
			"date_of_birth": "1990-01-01",
			"date_of_joining": today(),
			"status": "Active",
			"company": company,
			"user_id": email,
			"mys_branch": branch,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_monitor_employee(branch: str) -> str:
	return _ensure_cluster_inspector_employee("e2e_monitor@mys.local", branch, "E2E", "Monitor")


def _ensure_e2e_checklist_template() -> str:
	"""Routine template with Critical + Minor rows for portal happy/fail paths."""
	existing = frappe.db.get_value(
		"MYS Inspection Checklist Template",
		{"template_name": E2E_CHECKLIST_TAG, "is_active": 1},
		"name",
	)
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "MYS Inspection Checklist Template",
			"template_name": E2E_CHECKLIST_TAG,
			"visit_type": "Routine",
			"version": 1,
			"is_active": 1,
			"items": [
				{
					"item_text": "E2E fire extinguisher accessible",
					"category": "Safety",
					"severity": "Critical",
					"weight": 1,
					"max_score": 1,
				},
				{
					"item_text": "E2E classrooms clean",
					"category": "Cleanliness",
					"severity": "Minor",
					"weight": 1,
					"max_score": 1,
				},
			],
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_inspector_employee(branch):
	"""Create a minimal Employee linked to the branch if none exists."""
	emp = frappe.db.get_value("Employee", {}, "name")
	if emp:
		return emp
	company = frappe.db.get_value("MYS Branch", branch, "company") or frappe.db.get_value(
		"Company", {}, "name"
	)
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": "E2E",
			"last_name": "Inspector",
			"gender": "Male",
			"date_of_birth": "1990-01-01",
			"date_of_joining": today(),
			"status": "Active",
			"company": company,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_submitted_invoice():
	"""Run demo_royalty_invoice if there is no submitted invoice yet.

	demo_royalty_invoice.run() leaves invoices as Draft (so demos can show
	the approval flow). For e2e we need a *submitted* invoice so the
	"Send Reminder" overdue spec runs instead of being skipped. Submit the
	first Draft if no submitted invoice exists.
	"""
	inv = frappe.db.get_value("MYS Royalty Invoice", {"docstatus": 1}, "name")
	if inv:
		return inv
	from myschools.scripts import demo_royalty_invoice, seed_education

	seed_education.run()
	demo_royalty_invoice.run()
	inv = frappe.db.get_value("MYS Royalty Invoice", {"docstatus": 1}, "name")
	if inv:
		return inv
	draft = frappe.db.get_value("MYS Royalty Invoice", {"docstatus": 0}, "name")
	if not draft:
		return None
	doc = frappe.get_doc("MYS Royalty Invoice", draft)
	doc.submit()
	return doc.name


def _ensure_resolved_finding():
	branch = _ensure_franchise_tree()
	if not branch:
		return None, None
	inspector = _ensure_inspector_employee(branch)
	if not inspector:
		return None, None

	tag = "e2e seed finding"
	existing = frappe.db.get_value(
		"MYS Inspection Finding",
		{"description": tag, "status": "Resolved", "docstatus": 1},
		"name",
	)
	if existing:
		visit = frappe.db.get_value("MYS Inspection Finding", existing, "visit")
		return visit, existing

	v = frappe.get_doc(
		{
			"doctype": "MYS Inspection Visit",
			"branch": branch,
			"visit_date": today(),
			"visit_type": "Routine",
			"inspector": inspector,
		}
	)
	v.insert(ignore_permissions=True)
	v.submit()

	f = frappe.get_doc(
		{
			"doctype": "MYS Inspection Finding",
			"visit": v.name,
			"branch": branch,
			"severity": "Major",
			"category": "Safety",
			"status": "Draft",
			"description": tag,
			"due_date": add_days(today(), 14),
			"reported_by": "Administrator",
			"reported_on": today(),
			"resolution_notes": "e2e: pre-filled so Verify is reachable",
		}
	)
	f.insert(ignore_permissions=True)
	apply_workflow(f, "Submit")
	apply_workflow(f, "Acknowledge")
	apply_workflow(f, "Mark Resolved")
	return v.name, f.name


def _ensure_e2e_bulk_fee_prerequisites(branch: str) -> dict | None:
	"""Student group + enrollments for Phase 8a bulk-fee Playwright (no Fees on E2E date)."""
	if not branch:
		return None
	from myschools.scripts import seed_education

	seed_education.run()
	program = seed_education.PROGRAMS["Kids"]
	academic_year = seed_education.ACADEMIC_YEAR
	academic_term = seed_education.ACADEMIC_TERM
	campus = f"{branch}-Kids"

	if not frappe.db.exists("Student Group", E2E_BULK_FEE_GROUP):
		frappe.get_doc(
			{
				"doctype": "Student Group",
				"student_group_name": E2E_BULK_FEE_GROUP,
				"group_based_on": "Batch",
				"program": program,
				"academic_year": academic_year,
				"academic_term": academic_term,
				"max_strength": 50,
			}
		).insert(ignore_permissions=True)

	sg = frappe.get_doc("Student Group", E2E_BULK_FEE_GROUP)
	students = frappe.get_all(
		"Student",
		{"mys_branch": branch, "mys_campus": campus},
		pluck="name",
		limit=3,
	)
	if not students:
		return None
	added = False
	for student in students:
		if not frappe.db.exists("Student Group Student", {"parent": E2E_BULK_FEE_GROUP, "student": student}):
			sg.append("students", {"student": student, "active": 1})
			added = True
	if added:
		sg.save(ignore_permissions=True)

	# Remove any prior e2e bulk fees on both posting dates so Generate Fees is repeatable.
	for student in students:
		for fee_name in frappe.get_all(
			"Fees",
			{"student": student, "posting_date": ["in", [E2E_BULK_POSTING_DATE, E2E_BULK_POSTING_DATE_2]]},
			pluck="name",
		):
			fee = frappe.get_doc("Fees", fee_name)
			if fee.docstatus == 1:
				fee.cancel()
			frappe.delete_doc("Fees", fee_name, force=True, ignore_permissions=True)

	company = frappe.db.get_value("MYS Branch", branch, "company")
	fee_structure = frappe.db.get_value(
		"Fee Structure",
		{"program": program, "academic_year": academic_year, "company": company},
		"name",
	)
	default_fee_structure, override_fee_structure = _ensure_e2e_fee_override_pair(
		branch, program, academic_year, company, fee_structure
	)
	if not frappe.db.exists("Fee Category", "Late Fee"):
		frappe.get_doc({"doctype": "Fee Category", "category_name": "Late Fee"}).insert(
			ignore_permissions=True
		)

	meta = {
		"branch": branch,
		"student_group": E2E_BULK_FEE_GROUP,
		"program": program,
		"academic_year": academic_year,
		"academic_term": academic_term,
		"posting_date": E2E_BULK_POSTING_DATE,
		"due_date": E2E_BULK_DUE_DATE,
		"posting_date_2": E2E_BULK_POSTING_DATE_2,
		"due_date_2": E2E_BULK_DUE_DATE_2,
		"student_count": len(students),
		"fee_structure": override_fee_structure or fee_structure,
		"default_fee_structure": default_fee_structure,
		"sample_student": students[0],
		"company": company,
		"program_enrollment": frappe.db.get_value(
			"Program Enrollment",
			{"student": students[0], "docstatus": 1},
			"name",
		),
		"fee_category": "Late Fee",
	}
	if not company:
		return meta

	for old in frappe.get_all(
		"MYS Bulk Fee Run",
		{"branch": branch, "student_group": E2E_BULK_FEE_GROUP, "posting_date": E2E_BULK_POSTING_DATE},
		pluck="name",
	):
		frappe.delete_doc("MYS Bulk Fee Run", old, force=True, ignore_permissions=True)

	run = frappe.get_doc(
		{
			"doctype": "MYS Bulk Fee Run",
			"branch": branch,
			"company": company,
			"student_group": E2E_BULK_FEE_GROUP,
			"academic_year": academic_year,
			"academic_term": academic_term,
			"posting_date": E2E_BULK_POSTING_DATE,
			"due_date": E2E_BULK_DUE_DATE,
			"submit_fees": 1,
			"status": "Draft",
		}
	)
	run.insert(ignore_permissions=True)
	meta["run"] = run.name
	return meta


def _ensure_e2e_fee_override_pair(
	branch: str, program: str, academic_year: str, company: str, primary_fs: str | None
) -> tuple[str | None, str | None]:
	"""Return (default_fs, override_fs) for Fees desk Playwright (orange alert + auto-default).

	Creates a second Fee Structure when only one exists, and an active branch override
	pointing at the alternate structure so resolve_fee_structure returns override_fs.
	"""
	if not primary_fs or not company:
		return None, None

	alt_filters = {
		"program": program,
		"academic_year": academic_year,
		"company": company,
		"name": ["!=", primary_fs],
	}
	alt_fs = frappe.db.get_value("Fee Structure", alt_filters, "name")
	if not alt_fs:
		base = frappe.get_doc("Fee Structure", primary_fs)
		alt = frappe.get_doc(
			{
				"doctype": "Fee Structure",
				"program": program,
				"academic_year": academic_year,
				"company": company,
				"receivable_account": base.receivable_account,
				"components": [
					{
						"fees_category": row.fees_category,
						"amount": (row.amount or 0) + 1000,
					}
					for row in base.components
				],
			}
		).insert(ignore_permissions=True)
		alt_fs = alt.name

	override_fs = alt_fs
	default_fs = primary_fs

	if not frappe.db.exists(
		"MYS Fee Structure Override",
		{
			"branch": branch,
			"program": program,
			"academic_year": academic_year,
			"is_active": 1,
		},
	):
		frappe.get_doc(
			{
				"doctype": "MYS Fee Structure Override",
				"branch": branch,
				"program": program,
				"academic_year": academic_year,
				"fee_structure": override_fs,
				"effective_from": "2025-01-01",
				"is_active": 1,
				"reason": "E2E fee override for Playwright",
			}
		).insert(ignore_permissions=True)

	return default_fs, override_fs


def _ensure_overdue_invoice():
	inv = _ensure_submitted_invoice()
	if not inv:
		return None
	frappe.db.set_value("MYS Royalty Invoice", inv, "status", "Overdue")
	frappe.db.set_value("MYS Royalty Invoice", inv, "due_date", add_days(today(), -30))
	d = frappe.get_doc("MYS Royalty Invoice", inv)
	if not frappe.db.get_value("MYS Franchise Owner", d.franchisee, "email"):
		frappe.db.set_value("MYS Franchise Owner", d.franchisee, "email", "e2e@mys.local")
	return inv


def main():
	branch = _ensure_franchise_tree()
	for email, spec in USERS.items():
		_ensure_user(email, spec)
	if branch:
		_ensure_monitor_employee(branch)
		_ensure_cluster_inspector_employee("e2e_audit@mys.local", branch, "E2E", "Audit Inspector")
		_ensure_cluster_inspector_employee("e2e_accountant@mys.local", branch, "E2E", "Accountant")
		_ensure_cluster_inspector_employee("e2e_director@mys.local", branch, "E2E", "Director")
	template = _ensure_e2e_checklist_template()
	bulk_fee = _ensure_e2e_bulk_fee_prerequisites(branch)
	visit, finding = _ensure_resolved_finding()
	invoice = _ensure_overdue_invoice()
	frappe.db.commit()
	state = {
		"users": {
			email: {"password": spec["password"], "roles": spec["roles"]} for email, spec in USERS.items()
		},
		"visit": visit,
		"finding": finding,
		"invoice": invoice,
		"branch": branch,
		"checklist_template": template,
		"bulk_fee": bulk_fee,
	}
	with open(STATE_FILE, "w") as f:
		json.dump(state, f, indent=2)
	print(json.dumps(state, indent=2))
