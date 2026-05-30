import frappe

from myschools.api.portal import redirect_guest_to_login, redirect_to_portal_home


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = 0
	if frappe.session.user == "Guest":
		redirect_guest_to_login()
	redirect_to_portal_home()
	return context
