from myschools.api.branch_portal import (
	get_fees_summary,
	get_findings_summary,
	get_royalty_summary,
	populate_branch_context,
)


def get_context(context):
	branch = populate_branch_context(context)
	context.portal_title = "Branch Dashboard"
	context.findings_summary = get_findings_summary(branch)
	context.royalty_summary = get_royalty_summary(branch)
	context.fees_summary = get_fees_summary(branch)
	return context
