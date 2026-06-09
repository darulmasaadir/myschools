from myschools.api.guardian_portal import populate_guardian_context
from myschools.api.library import get_loans_for_guardian


def get_context(context):
	guardian = populate_guardian_context(context)
	context.portal_title = "Library"
	context.loans = get_loans_for_guardian(guardian)
	return context
