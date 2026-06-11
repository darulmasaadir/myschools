from myschools.api.student_portal import get_fees_for_student, populate_student_context


def get_context(context):
	student = populate_student_context(context)
	context.portal_title = "Fees"
	context.fees = get_fees_for_student(student)
	return context
