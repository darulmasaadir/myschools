from myschools.api.scheduling import get_schedules_for_student, group_schedule_by_date
from myschools.api.student_portal import populate_student_context


def get_context(context):
	student = populate_student_context(context)
	context.portal_title = "Class Timetable"
	context.schedule = get_schedules_for_student(student.name, days=14, limit=500)
	context.schedule_days = group_schedule_by_date(context.schedule)
	return context
