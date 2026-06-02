from myschools.api.inspection_portal import (
	get_branches_for_form,
	populate_inspection_context,
)


def get_context(context):
	branches = populate_inspection_context(context)
	context.portal_title = "New inspection visit"
	context.branches = get_branches_for_form(branches)
	context.visit_types = [
		"Academic Monitoring",
		"Financial Audit",
		"Facility",
		"Complaint",
		"Routine",
	]
	return context
