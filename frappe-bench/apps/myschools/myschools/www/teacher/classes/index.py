from myschools.api.teacher_portal import get_student_groups_for_teacher, populate_teacher_context


def get_context(context):
	employee, instructor = populate_teacher_context(context)
	context.portal_title = "My Classes"
	context.student_groups = get_student_groups_for_teacher(instructor, employee)
	return context
