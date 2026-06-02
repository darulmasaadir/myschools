import frappe

from myschools.api.branch_portal import get_findings_for_branch, populate_branch_context


def get_context(context):
	branch = populate_branch_context(context)
	context.portal_title = "Inspection findings"
	scope = (frappe.form_dict.get("scope") or "open").lower()
	if scope == "all":
		statuses = None
	elif scope == "resolved":
		statuses = ("Resolved", "Verified")
	else:
		statuses = ("Open", "In Progress")
		scope = "open"
	context.scope = scope
	context.findings = get_findings_for_branch(branch, statuses=statuses, limit=200)
	return context
