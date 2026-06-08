from myschools.api.guardian_portal import populate_guardian_context
from myschools.api.transport import get_transport_for_guardian


def get_context(context):
	guardian = populate_guardian_context(context)
	context.portal_title = "Transport"
	context.assignments = get_transport_for_guardian(guardian)
	return context
