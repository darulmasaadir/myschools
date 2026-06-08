import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class MYSLibraryItem(Document):
	def validate(self):
		total = cint(self.total_copies)
		if total <= 0:
			frappe.throw(_("Total copies must be a positive number."))
		available = cint(self.available_copies)
		if self.is_new() and not self.available_copies:
			self.available_copies = total
			available = total
		if available > total:
			frappe.throw(_("Available copies cannot exceed total copies."))
		if available < 0:
			frappe.throw(_("Available copies cannot be negative."))
