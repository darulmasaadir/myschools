from myschools.api.inspection_portal import list_visits, populate_inspection_context


def get_context(context):
	branches = populate_inspection_context(context)
	context.portal_title = "Inspection visits"
	context.visits = list_visits(branches)
	return context
