from myschools.api.branch_portal import (
	get_royalty_for_branch,
	get_royalty_summary,
	populate_branch_context,
)


def get_context(context):
	branch = populate_branch_context(context)
	context.portal_title = "Royalty invoices"
	context.invoices = get_royalty_for_branch(branch, limit=24)
	context.summary = get_royalty_summary(branch)
	return context
