import frappe

from myschools.api.teacher_portal import (
	get_roster_for_group,
	get_student_groups_for_teacher,
	populate_teacher_context,
)


def get_context(context):
	employee, instructor = populate_teacher_context(context)
	group_name = frappe.form_dict.get("group")
	if not group_name:
		frappe.local.flags.redirect_location = "/teacher/classes"
		raise frappe.Redirect
	groups = {g["name"]: g for g in get_student_groups_for_teacher(instructor, employee)}
	group = groups.get(group_name)
	if not group:
		frappe.throw("Class not found or not assigned to you.", frappe.PermissionError)
	context.group = group
	context.roster = get_roster_for_group(group_name, instructor, employee)
	context.portal_title = group.get("student_group_name") or group_name
	return context
