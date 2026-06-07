import frappe

from myschools.api.guardian_portal import populate_guardian_context
from myschools.api.scheduling import get_schedules_for_guardian, group_schedule_by_date


def get_context(context):
	guardian = populate_guardian_context(context)
	context.portal_title = "Class Timetable"
	student = frappe.form_dict.get("student")
	context.selected_student = student
	context.schedule = get_schedules_for_guardian(guardian, student_name=student, days=14, limit=500)
	context.schedule_days = group_schedule_by_date(context.schedule)
	return context
