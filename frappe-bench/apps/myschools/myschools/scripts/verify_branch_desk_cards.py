"""One-shot verification for MYS Branch desk number cards (run via bench execute).

bench --site SITE execute myschools.scripts.verify_branch_desk_cards.run
"""

from __future__ import annotations

import json

import frappe
from frappe.desk.doctype.number_card.number_card import has_permission as number_card_has_permission
from frappe.permissions import has_permission

BRANCH_USERS = [
	"branch.dir@mys.local",
	"principal@mys.local",
	"branch.admin@mys.local",
	"accountant@mys.local",
]

WORKSPACE = "mys-branch"
CARDS = [
	("Active Students", "MYS - Active Students", "Student"),
	("This Month Royalty Invoiced", "MYS - This Month Royalty Invoiced", "MYS Royalty Invoice"),
	("This Month Fees Collected", "MYS - This Month Fees Collected", "Fees"),
	("Overdue Findings", "MYS - Overdue Findings", "MYS Inspection Finding"),
]


def run():
	failures: list[str] = []

	_check_custom_card_document_types(failures)
	_check_workspace_content_labels(failures)

	for email in BRANCH_USERS:
		if frappe.db.exists("User", email):
			_check_user(email, failures)
		else:
			failures.append(f"user missing: {email}")

	if failures:
		print("FAILED —", len(failures), "issue(s):")
		for f in failures:
			print(f"  ✗ {f}")
		frappe.throw("Branch desk card verification failed")
	print("OK — branch desk number cards verified for", ", ".join(BRANCH_USERS))


def _check_custom_card_document_types(failures: list[str]) -> None:
	from myschools.setup.install import CUSTOM_NUMBER_CARD_DOCUMENT_TYPES

	for card_name, expected_dt in CUSTOM_NUMBER_CARD_DOCUMENT_TYPES.items():
		actual = frappe.db.get_value("Number Card", card_name, "document_type")
		if actual != expected_dt:
			failures.append(f"{card_name}: document_type={actual!r}, expected {expected_dt!r}")


def _check_workspace_content_labels(failures: list[str]) -> None:
	ws = frappe.get_doc("Workspace", WORKSPACE)
	name_to_label = {r.number_card_name: (r.label or r.number_card_name) for r in ws.number_cards}
	for block in json.loads(ws.content or "[]"):
		if block.get("type") != "number_card":
			continue
		val = block.get("data", {}).get("number_card_name")
		if val in name_to_label and val != name_to_label[val]:
			failures.append(
				f"workspace content still uses doc name {val!r}; expected label {name_to_label[val]!r}"
			)
		if val not in name_to_label.values() and val not in name_to_label:
			failures.append(f"workspace content unknown number_card_name {val!r}")


def _check_user(email: str, failures: list[str]) -> None:
	emp = frappe.db.get_value("Employee", {"user_id": email}, ["name", "mys_branch"], as_dict=True)
	if not emp or not emp.mys_branch:
		failures.append(f"{email}: no Employee.mys_branch (run seed_test_users)")
		return

	frappe.set_user(email)
	try:
		for _label, doc_name, doctype in CARDS:
			if not has_permission(doctype, "read", user=email):
				failures.append(f"{email}: no read on {doctype}")
			nc = frappe.get_doc("Number Card", doc_name)
			if not number_card_has_permission(nc, "read", email):
				failures.append(f"{email}: Number Card {doc_name} has_permission=False")

		from frappe.desk.desktop import get_desktop_page

		page = get_desktop_page(page=json.dumps({"name": WORKSPACE}))
		visible = page.get("number_cards", {}).get("items", [])
		visible_labels = {r.get("label") for r in visible}
		for label, _, _ in CARDS:
			if label not in visible_labels:
				failures.append(f"{email}: {label!r} not in get_desktop_page number_cards")

		# Desk JS matches content block value to row.label (not doc name).
		for block in json.loads(frappe.db.get_value("Workspace", WORKSPACE, "content") or "[]"):
			if block.get("type") != "number_card":
				continue
			block_val = block.get("data", {}).get("number_card_name")
			if block_val not in visible_labels:
				failures.append(
					f"{email}: content block {block_val!r} would not mount (no matching label in page_data)"
				)
	finally:
		frappe.set_user("Administrator")
