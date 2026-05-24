import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class MYSInspectionFinding(Document):
	def before_insert(self):
		if not self.reported_on:
			self.reported_on = today()
		if not self.reported_by:
			self.reported_by = frappe.session.user

	def validate(self):
		if self.status == "Resolved" and not self.resolved_on:
			self.resolved_on = today()
		if self.status == "Verified" and not self.resolution_notes:
			frappe.throw(_("Cannot mark finding as Verified without resolution notes"))
