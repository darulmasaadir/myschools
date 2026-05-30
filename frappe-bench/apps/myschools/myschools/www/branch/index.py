import frappe

_BRANCH_ROLES = {
	"Branch Director",
	"Branch Principal",
	"Branch Admin",
	"Branch Accountant",
	"Campus Incharge",
}


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = 0
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/branch"
		raise frappe.Redirect
	if not _BRANCH_ROLES & set(frappe.get_roles()):
		frappe.throw("You do not have access to the Branch portal.", frappe.PermissionError)
	context.portal_title = "Branch Portal"
	context.portal_blurb = "Principal dashboard — findings, royalty, and fees land in PR 7c."
	return context
