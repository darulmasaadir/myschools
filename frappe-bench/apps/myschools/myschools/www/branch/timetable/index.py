from myschools.api.branch_portal import populate_branch_context
from myschools.api.scheduling import get_schedules_for_branch, group_schedule_by_date


def get_context(context):
	branch = populate_branch_context(context)
	context.portal_title = "Branch Timetable"
	context.schedule = get_schedules_for_branch(branch, days=14, limit=500)
	context.schedule_days = group_schedule_by_date(context.schedule)
	return context
