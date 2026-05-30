import frappe
from frappe.model.document import Document


class MYSCommunicationLog(Document):
	def before_insert(self):
		if not self.sender:
			self.sender = frappe.session.user
		if "Guardian" in frappe.get_roles() and not self.channel:
			self.channel = "In-App"
			self.status = "Sent"
			self.scope = "Individual"
			self.recipient_user = self.recipient_user or frappe.session.user
			if not self.branch:
				branch = frappe.db.get_value("Guardian", {"user": frappe.session.user}, "mys_branch")
				if not branch:
					email = frappe.db.get_value("User", frappe.session.user, "email")
					if email:
						branch = frappe.db.get_value("Guardian", {"email_address": email}, "mys_branch")
				self.branch = branch
