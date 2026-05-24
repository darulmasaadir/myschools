import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class MYSRoyaltyPayment(Document):
	def validate(self):
		if (self.paid_amount or 0) <= 0:
			frappe.throw(_("Paid Amount must be greater than zero"))

		inv = frappe.db.get_value(
			"MYS Royalty Invoice",
			self.royalty_invoice,
			["branch", "company", "docstatus"],
			as_dict=True,
		)
		if not inv:
			frappe.throw(_("Royalty Invoice {0} not found").format(self.royalty_invoice))
		if inv.docstatus != 1:
			frappe.throw(_("Royalty Invoice {0} is not submitted").format(self.royalty_invoice))
		self.branch = inv.branch
		self.company = inv.company

	def on_submit(self):
		self._sync_invoice()

	def on_cancel(self):
		self._sync_invoice()

	def _sync_invoice(self):
		invoice = frappe.get_doc("MYS Royalty Invoice", self.royalty_invoice)
		invoice.update_paid_amount()
