from myschools.api.teacher_portal import get_schedule_for_teacher, populate_teacher_context


def get_context(context):
	employee, instructor = populate_teacher_context(context)
	context.portal_title = "My Schedule"
	context.schedule = get_schedule_for_teacher(instructor, days=14, limit=100)
	return context
