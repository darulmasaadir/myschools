import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class MYSRoyaltyInvoice(Document):
	def validate(self):
		self._populate_defaults_from_agreement()
		self._recompute_totals()
		self._refresh_status()

	def before_submit(self):
		if (self.royalty_amount or 0) <= 0:
			frappe.throw(_("Cannot submit a royalty invoice with zero amount"))
		if self.status == "Draft":
			self.status = "Unpaid"

	def _populate_defaults_from_agreement(self):
		if not self.agreement:
			return
		agreement = frappe.db.get_value(
			"MYS Franchise Agreement",
			self.agreement,
			["franchisee", "branch", "company"],
			as_dict=True,
		)
		if agreement:
			self.franchisee = agreement.franchisee
			if not self.branch:
				self.branch = agreement.branch
			if not self.company:
				self.company = agreement.company

	def _recompute_totals(self):
		total_collection = 0.0
		total_royalty = 0.0
		for line in self.campus_lines or []:
			line.royalty_amount = flt(flt(line.collection_amount) * flt(line.rate_percent) / 100, 2)
			total_collection += flt(line.collection_amount)
			total_royalty += flt(line.royalty_amount)

		self.total_collection = flt(total_collection, 2)
		self.royalty_amount = flt(total_royalty, 2)
		self.applicable_rate = flt((total_royalty / total_collection * 100) if total_collection else 0, 4)
		self.outstanding_amount = flt(self.royalty_amount - flt(self.paid_amount), 2)

	def _refresh_status(self):
		if self.status in ("Cancelled", "Draft"):
			return
		if flt(self.paid_amount) <= 0:
			new_status = "Unpaid"
		elif flt(self.paid_amount) < flt(self.royalty_amount):
			new_status = "Partial"
		else:
			new_status = "Paid"

		if new_status != "Paid" and self.due_date and getdate(self.due_date) < getdate():
			new_status = "Overdue"

		self.status = new_status

	def update_paid_amount(self):
		"""Called by MYS Royalty Payment hooks when payments are submitted/cancelled."""
		total = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(paid_amount), 0)
			FROM `tabMYS Royalty Payment`
			WHERE royalty_invoice = %s AND docstatus = 1
			""",
			(self.name,),
		)[0][0]
		self.db_set("paid_amount", flt(total, 2))
		self.db_set("outstanding_amount", flt(self.royalty_amount - flt(total), 2))
		self.reload()
		self._refresh_status()
		self.db_set("status", self.status)
