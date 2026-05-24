import frappe
from frappe.model.document import Document


class MYSCommunicationLog(Document):
	def before_insert(self):
		if not self.sender:
			self.sender = frappe.session.user
