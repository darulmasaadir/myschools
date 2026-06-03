import frappe

from myschools.api.inspection_portal import (
	get_active_templates,
	get_visit_detail,
	populate_inspection_context,
)


def get_context(context):
	populate_inspection_context(context)
	visit_name = frappe.form_dict.get("name")
	if not visit_name:
		frappe.throw("Visit name is required.", frappe.ValidationError)
	context.portal_title = f"Visit {visit_name}"
	context.visit = get_visit_detail(visit_name)
	context.templates = get_active_templates(context.visit.visit_type) if context.visit.docstatus == 0 else []
	context.saved = frappe.form_dict.get("saved")
	context.submitted = frappe.form_dict.get("submitted")
	return context
