import frappe
from frappe import _
from frappe.model.document import Document


class MYSFranchiseAgreement(Document):
	def validate(self):
		if self.end_date and self.start_date and self.end_date < self.start_date:
			frappe.throw(_("End Date cannot be before Start Date"))
		if not (0 <= (self.default_royalty_rate or 0) <= 100):
			frappe.throw(_("Default Royalty Rate must be between 0 and 100"))
		if not self.company and self.branch:
			self.company = frappe.db.get_value("MYS Branch", self.branch, "company")
		if not self.franchisee:
			frappe.throw(_("Franchise Owner (franchisee) is required"))

	def on_submit(self):
		if self.status == "Draft":
			self.db_set("status", "Active")
