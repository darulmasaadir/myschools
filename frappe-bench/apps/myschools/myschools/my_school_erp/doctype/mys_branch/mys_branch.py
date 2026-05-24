import frappe
from frappe import _
from frappe.model.document import Document


class MYSBranch(Document):
	def validate(self):
		if self.branch_code:
			self.branch_code = self.branch_code.strip().upper()
		if not self.cluster:
			frappe.throw(_("Branch must belong to a Cluster"))
