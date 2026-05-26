"""Idempotent seed for Playwright e2e tests.

Creates (or reuses):
- Test users with predictable passwords for each MYS role we exercise.
- One submitted MYS Inspection Visit + one MYS Inspection Finding at status
  "Resolved" with resolution_notes filled in — that's the state where the
  role gating on Verify is most visible (Audit Officer sees it, Director
  does not).
- One overdue MYS Royalty Invoice (status forced via db.set_value) so the
  "Send Reminder" button shows up.

Stash returned IDs into /tmp/mys_e2e_state.json so the Playwright spec can
read them without re-discovering through the API.

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
}


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


def _ensure_resolved_finding():
	branch = frappe.db.get_value("MYS Branch", {}, "name")
	if not branch:
		return None, None
	inspector = frappe.db.get_value("Employee", {}, "name")
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


def _ensure_overdue_invoice():
	inv = frappe.db.get_value("MYS Royalty Invoice", {"docstatus": 1}, "name")
	if not inv:
		return None
	frappe.db.set_value("MYS Royalty Invoice", inv, "status", "Overdue")
	frappe.db.set_value("MYS Royalty Invoice", inv, "due_date", add_days(today(), -30))
	d = frappe.get_doc("MYS Royalty Invoice", inv)
	if not frappe.db.get_value("MYS Franchise Owner", d.franchisee, "email"):
		frappe.db.set_value("MYS Franchise Owner", d.franchisee, "email", "e2e@mys.local")
	return inv


def main():
	for email, spec in USERS.items():
		_ensure_user(email, spec)
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
	}
	with open(STATE_FILE, "w") as f:
		json.dump(state, f, indent=2)
	print(json.dumps(state, indent=2))
