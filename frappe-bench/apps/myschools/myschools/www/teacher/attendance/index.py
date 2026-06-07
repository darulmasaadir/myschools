import frappe
from frappe.utils import nowdate

from myschools.api.teacher_portal import (
	get_attendance_sheet,
	get_student_groups_for_teacher,
	populate_teacher_context,
)


def get_context(context):
	employee, instructor = populate_teacher_context(context)
	context.portal_title = "Mark Attendance"
	context.student_groups = get_student_groups_for_teacher(instructor, employee)
	group = (frappe.form_dict.get("group") or "").strip()
	att_date = (frappe.form_dict.get("date") or nowdate()).strip()
	context.selected_group = group
	context.attendance_date = att_date
	context.saved = frappe.form_dict.get("saved")
	context.sheet = None
	if group:
		context.sheet = get_attendance_sheet(group, att_date, instructor, employee)
