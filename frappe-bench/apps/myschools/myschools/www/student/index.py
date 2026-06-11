from myschools.api.student_portal import populate_student_context


def get_context(context):
	populate_student_context(context)
	context.portal_title = "My Profile"
	return context
