"""Inspection workflow helpers.

Two main entry points:
    * apply_template_to_visit(visit, template) — snapshot template items into
      the visit's checklist_results table. Snapshot so historical visits are
      stable when templates are revised.
    * auto_create_findings_from_failed_results(visit) — on submit, create one
      Finding per failed Critical/Major item. Minor failures need a manual
      finding; the inspector tells you which warrant follow-up.
"""

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, today

from myschools.api.permissions import _user_scope


@frappe.whitelist()
def apply_template_to_visit(visit: str, template: str) -> int:
	"""Populate visit.checklist_results from the template's items.

	Snapshots item fields (text, category, severity, weight, max_score) so a
	later revision of the template doesn't rewrite historical visit data.

	Returns the number of rows added. Raises if the visit isn't a draft.
	"""
	visit_doc = frappe.get_doc("MYS Inspection Visit", visit)
	if visit_doc.docstatus != 0:
		frappe.throw(_("Cannot apply template to a submitted visit"))

	template_doc = frappe.get_doc("MYS Inspection Checklist Template", template)
	if not template_doc.is_active:
		frappe.throw(_("Template {0} is not active").format(template))

	visit_doc.checklist_results = []
	for item in template_doc.items:
		visit_doc.append(
			"checklist_results",
			{
				"item_text": item.item_text,
				"category": item.category,
				"severity": item.severity,
				"weight": item.weight,
				"max_score": item.max_score,
				"result": None,
				"score": 0,
			},
		)
	visit_doc.checklist_template = template
	visit_doc.save()
	return len(visit_doc.checklist_results)


def auto_create_findings_from_failed_results(visit: str) -> list[str]:
	"""On visit submit, create a Finding per failed Critical/Major item.

	Called from MYS Inspection Visit.on_submit. Minor failures are skipped —
	the inspector should raise them manually in the summary if they need
	tracking. Returns the list of created finding names.

	Idempotent: if findings already exist for this visit, does nothing.
	"""
	existing = frappe.db.count("MYS Inspection Finding", {"visit": visit})
	if existing:
		return []

	visit_doc = frappe.get_doc("MYS Inspection Visit", visit)
	created: list[str] = []
	for row in visit_doc.checklist_results or []:
		if row.result != "Fail":
			continue
		if row.severity not in ("Critical", "Major"):
			continue
		due_offset = 7 if row.severity == "Critical" else 21
		finding = frappe.get_doc(
			{
				"doctype": "MYS Inspection Finding",
				"visit": visit,
				"branch": visit_doc.branch,
				"campus": visit_doc.campus,
				"severity": row.severity,
				"category": row.category,
				"status": "Draft",
				"description": f"{row.item_text}\n\nInspector notes: {row.notes or '(none)'}",
				"reported_on": visit_doc.visit_date or today(),
				"due_date": add_days(visit_doc.visit_date or today(), due_offset),
			}
		).insert(ignore_permissions=True)
		# Findings auto-created from a submitted Visit go straight to Open
		# (docstatus=1) so they're visible to the branch and the
		# "Finding Assigned" notification fires. The Submit transition is
		# role-gated (Audit Officer / branch staff) but the inspector who
		# submitted the visit is often Academic Monitor — run the workflow
		# step as Administrator inside this system hook.
		prev_user = frappe.session.user
		try:
			frappe.set_user("Administrator")
			apply_workflow(finding, "Submit")
		finally:
			frappe.set_user(prev_user)
		created.append(finding.name)
	return created


# --- permission query conditions ----------------------------------------------


def _scoped_query(doctype: str, field: str, user: str) -> str:
	scope, branches = _user_scope(user)
	if scope == "global":
		return ""
	if scope == "none" or not branches:
		return f"`tab{doctype}`.{field} = '__none__'"
	in_list = ", ".join(frappe.db.escape(b) for b in branches)
	return f"`tab{doctype}`.{field} IN ({in_list})"


def finding_query(user):
	return _scoped_query("MYS Inspection Finding", "branch", user)


def corrective_action_query(user):
	return _scoped_query("MYS Corrective Action", "branch", user)


def checklist_template_query(user):
	# Templates are global reference data, not branch-scoped.
	return ""
