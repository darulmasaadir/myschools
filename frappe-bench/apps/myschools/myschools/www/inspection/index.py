from myschools.api.inspection_portal import get_dashboard_summary, populate_inspection_context


def get_context(context):
	branches = populate_inspection_context(context)
	context.portal_title = "Inspection Dashboard"
	context.summary = get_dashboard_summary(branches)
	return context
