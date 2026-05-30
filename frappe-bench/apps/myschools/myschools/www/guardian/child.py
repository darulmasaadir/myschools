import frappe

from myschools.api.guardian_portal import get_student_detail, populate_guardian_context


def get_context(context):
	guardian = populate_guardian_context(context)
	student_id = frappe.form_dict.get("student")
	if not student_id:
		frappe.local.flags.redirect_location = "/guardian"
		raise frappe.Redirect
	context.student = get_student_detail(student_id, guardian)
	context.portal_title = context.student.student_name or student_id
	return context
