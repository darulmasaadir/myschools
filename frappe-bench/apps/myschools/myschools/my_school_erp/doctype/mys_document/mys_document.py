import frappe
from frappe.model.document import Document

from myschools.api.documents import validate_mys_document


class MYSDocument(Document):
	def validate(self):
		validate_mys_document(self)
