import frappe


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = 0
	context.portal_title = "Admission enquiry"
	context.branches = frappe.get_all(
		"MYS Branch",
		fields=["name", "branch_name", "branch_code", "city"],
		order_by="branch_name",
	)
	return context
