from myschools.api.branch_portal import (
	get_fees_summary,
	get_findings_summary,
	get_royalty_summary,
	populate_branch_context,
)
from myschools.api.scheduling import get_schedule_portal_summary, get_schedules_for_branch


def get_context(context):
	branch = populate_branch_context(context)
	context.portal_title = "Branch Dashboard"
	context.findings_summary = get_findings_summary(branch)
	context.royalty_summary = get_royalty_summary(branch)
	context.fees_summary = get_fees_summary(branch)
	context.timetable_summary = get_schedule_portal_summary(get_schedules_for_branch(branch, days=14))
	return context
