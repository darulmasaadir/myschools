import frappe
from frappe.model.document import Document


class MYSCluster(Document):
	def validate(self):
		if self.cluster_code:
			self.cluster_code = self.cluster_code.strip().upper()
