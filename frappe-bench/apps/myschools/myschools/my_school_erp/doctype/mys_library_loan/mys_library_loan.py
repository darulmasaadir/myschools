import frappe
from frappe.model.document import Document

from myschools.api.library import (
	adjust_available_copies,
	handle_loan_return,
	validate_library_loan,
)


class MYSLibraryLoan(Document):
	def validate(self):
		validate_library_loan(self)

	def after_insert(self):
		from myschools.api.library import on_loan_inserted

		on_loan_inserted(self)

	def on_update(self):
		prev = self.get_doc_before_save()
		if not prev:
			return
		if prev.status in ("On Loan", "Overdue") and self.status == "Returned":
			adjust_available_copies(self.library_item, 1)
			handle_loan_return(self)

	def on_trash(self):
		if self.status in ("On Loan", "Overdue"):
			adjust_available_copies(self.library_item, 1)
