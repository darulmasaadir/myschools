from myschools.api.guardian_portal import (
	get_attendance_for_guardian,
	get_attendance_summary,
	populate_guardian_context,
)


def get_context(context):
	guardian = populate_guardian_context(context)
	context.portal_title = "Attendance"
	context.attendance = get_attendance_for_guardian(guardian, days=90)
	context.summary = get_attendance_summary(context.attendance)
	return context
