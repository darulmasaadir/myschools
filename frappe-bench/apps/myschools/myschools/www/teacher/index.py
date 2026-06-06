from myschools.api.teacher_portal import (
	get_schedule_for_teacher,
	get_schedule_summary,
	get_student_groups_for_teacher,
	populate_teacher_context,
)


def get_context(context):
	employee, instructor = populate_teacher_context(context)
	context.portal_title = "Teacher Dashboard"
	context.student_groups = get_student_groups_for_teacher(instructor, employee)
	context.schedule = get_schedule_for_teacher(instructor, days=7, limit=20)
	context.schedule_summary = get_schedule_summary(context.schedule)
	return context
