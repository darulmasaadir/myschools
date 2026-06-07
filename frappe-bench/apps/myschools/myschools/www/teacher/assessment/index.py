import frappe

from myschools.api.teacher_portal import get_assessment_entry_sheet, populate_teacher_context


def get_context(context):
	employee, instructor = populate_teacher_context(context)
	plan_name = (frappe.form_dict.get("plan") or "").strip()
	context.portal_title = "Enter Scores"
	context.plan_name = plan_name
	context.saved = frappe.form_dict.get("saved")
	context.entry = None
	if plan_name:
		context.entry = get_assessment_entry_sheet(plan_name, instructor, employee)
		if context.entry:
			context.portal_title = context.entry["plan"]["assessment_name"]
