from myschools.api.student_portal import (
	get_attendance_for_student,
	get_attendance_summary,
	populate_student_context,
)


def get_context(context):
	student = populate_student_context(context)
	context.portal_title = "Attendance"
	context.attendance = get_attendance_for_student(student)
	context.attendance_summary = get_attendance_summary(context.attendance)
	return context
