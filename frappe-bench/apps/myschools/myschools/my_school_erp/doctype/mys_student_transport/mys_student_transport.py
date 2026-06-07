import frappe
from frappe import _
from frappe.model.document import Document

from myschools.api.transport import validate_student_transport


class MYSStudentTransport(Document):
	def validate(self):
		validate_student_transport(self)
