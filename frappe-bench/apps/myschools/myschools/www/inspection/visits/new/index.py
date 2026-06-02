import frappe

from myschools.api.inspection_portal import (
	create_draft_visit,
	get_branches_for_form,
	get_campuses_for_branch,
	populate_inspection_context,
)


def get_context(context):
	branches = populate_inspection_context(context)
	context.portal_title = "New inspection visit"
	context.branches = get_branches_for_form(branches)
	context.visit_types = [
		"Academic Monitoring",
		"Financial Audit",
		"Facility",
		"Complaint",
		"Routine",
	]
	context.created = None
	context.error = None

	if frappe.form_dict.get("created"):
		context.created = frappe.form_dict.created

	if frappe.request.method == "POST":
		try:
			branch = frappe.form_dict.get("branch")
			visit_type = frappe.form_dict.get("visit_type")
			visit_date = frappe.form_dict.get("visit_date")
			campus = frappe.form_dict.get("campus") or None
			name = create_draft_visit(branch, visit_type, visit_date, campus)
			frappe.local.flags.redirect_location = f"/inspection/visit?name={name}"
			raise frappe.Redirect
		except frappe.Redirect:
			raise
		except Exception as exc:
			context.error = str(exc)

	return context
