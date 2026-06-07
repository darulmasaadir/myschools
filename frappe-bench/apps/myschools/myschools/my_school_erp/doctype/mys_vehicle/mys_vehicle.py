import frappe
from frappe import _
from frappe.model.document import Document


class MYSVehicle(Document):
	def validate(self):
		if self.capacity is not None and self.capacity <= 0:
			frappe.throw(_("Capacity must be a positive number."))
