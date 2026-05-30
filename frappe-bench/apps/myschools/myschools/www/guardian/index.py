from myschools.api.guardian_portal import populate_guardian_context


def get_context(context):
	populate_guardian_context(context)
	context.portal_title = "My Children"
	return context
