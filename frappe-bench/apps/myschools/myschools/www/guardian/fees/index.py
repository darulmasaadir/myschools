from myschools.api.guardian_portal import get_fees_for_guardian, populate_guardian_context


def get_context(context):
	guardian = populate_guardian_context(context)
	context.portal_title = "Fees"
	context.fees = get_fees_for_guardian(guardian)
	return context
