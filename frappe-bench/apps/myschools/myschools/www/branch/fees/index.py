from myschools.api.branch_portal import (
	get_fees_for_branch,
	get_fees_summary,
	populate_branch_context,
)


def get_context(context):
	branch = populate_branch_context(context)
	context.portal_title = "Fee collection"
	context.summary = get_fees_summary(branch)
	context.fees = get_fees_for_branch(branch, days=90, limit=100)
	return context
