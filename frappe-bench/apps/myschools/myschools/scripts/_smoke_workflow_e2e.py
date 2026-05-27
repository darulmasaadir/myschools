"""End-to-end smoke for the Phase-5 workflows.

Walks a synthetic Finding through Draft -> Open -> In Progress -> Resolved ->
Verified using ``apply_workflow``. Confirms each transition lands in the
expected state and ``docstatus`` flips on Submit.
"""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, today


def main():
	branch = frappe.db.get_value("MYS Branch", {}, "name")
	inspector = frappe.db.get_value("Employee", {}, "name")
	assert branch and inspector, "site needs at least one MYS Branch and one Employee"

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
			"description": "smoke e2e",
			"due_date": add_days(today(), 7),
			"reported_by": "Administrator",
			"reported_on": today(),
		}
	)
	f.insert()
	print(f"inserted finding: status={f.status} docstatus={f.docstatus}")

	apply_workflow(f, "Submit")
	f.reload()
	assert (f.status, f.docstatus) == ("Open", 1), f
	print(f"after Submit:        status={f.status} docstatus={f.docstatus}")

	apply_workflow(f, "Acknowledge")
	f.reload()
	assert f.status == "In Progress", f
	print(f"after Acknowledge:   status={f.status}")

	apply_workflow(f, "Mark Resolved")
	f.reload()
	assert f.status == "Resolved", f
	print(f"after Mark Resolved: status={f.status}")

	f.resolution_notes = "smoke resolution"
	f.save()
	apply_workflow(f, "Verify")
	f.reload()
	assert f.status == "Verified", f
	print(f"after Verify:        status={f.status}")

	frappe.delete_doc("MYS Inspection Finding", f.name, force=1, ignore_permissions=True)
	v.cancel()
	frappe.delete_doc("MYS Inspection Visit", v.name, force=1, ignore_permissions=True)
	frappe.db.commit()
	print("OK")
