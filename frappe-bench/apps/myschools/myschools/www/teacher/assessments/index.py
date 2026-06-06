from myschools.api.teacher_portal import get_assessment_plans_for_teacher, populate_teacher_context


def get_context(context):
	employee, instructor = populate_teacher_context(context)
	context.portal_title = "Assessments"
	context.plans = get_assessment_plans_for_teacher(instructor, employee)
