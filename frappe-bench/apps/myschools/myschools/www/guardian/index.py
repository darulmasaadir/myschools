import frappe


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = 0
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/guardian"
		raise frappe.Redirect
	if "Guardian" not in frappe.get_roles():
		frappe.throw("You do not have access to the Guardian portal.", frappe.PermissionError)
	context.portal_title = "Guardian Portal"
	context.portal_blurb = "Parent portal — children, fees, and receipts land in PR 7b."
	return context
