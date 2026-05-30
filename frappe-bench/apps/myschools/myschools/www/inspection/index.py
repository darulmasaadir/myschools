import frappe

_INSPECTION_ROLES = {"Academic Monitor", "Audit Officer"}


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = 0
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/inspection"
		raise frappe.Redirect
	if not _INSPECTION_ROLES & set(frappe.get_roles()):
		frappe.throw("You do not have access to the Inspection portal.", frappe.PermissionError)
	context.portal_title = "Inspection Portal"
	context.portal_blurb = "Field checklist runner lands in PR 7d."
	return context
