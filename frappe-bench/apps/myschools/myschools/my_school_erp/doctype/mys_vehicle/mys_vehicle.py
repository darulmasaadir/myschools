import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class MYSVehicle(Document):
	def validate(self):
		# capacity can arrive as a string (REST / form set_value); coerce before compare.
		if self.capacity is not None and cint(self.capacity) <= 0:
			frappe.throw(_("Capacity must be a positive number."))
