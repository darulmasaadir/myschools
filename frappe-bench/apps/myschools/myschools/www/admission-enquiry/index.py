import frappe

from myschools.api.inspection_portal import submit_admission_enquiry


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = 0
	context.portal_title = "Admission enquiry"
	context.branches = frappe.get_all(
		"MYS Branch",
		fields=["name", "branch_name", "branch_code", "city"],
		order_by="branch_name",
	)
	context.success = False
	context.error = None
	context.reference = None

	if frappe.request.method == "POST":
		try:
			out = submit_admission_enquiry(
				branch=frappe.form_dict.get("branch") or "",
				parent_name=frappe.form_dict.get("parent_name") or "",
				phone=frappe.form_dict.get("phone") or "",
				email=frappe.form_dict.get("email") or "",
				child_grade=frappe.form_dict.get("child_grade") or "",
				message=frappe.form_dict.get("message") or "",
			)
			context.success = True
			context.reference = out.get("name")
		except Exception as exc:
			context.error = str(exc)

	return context
