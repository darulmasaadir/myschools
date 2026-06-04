import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class MYSLateFeePolicy(Document):
	def validate(self):
		# cint/flt guard against str values (API, client set_value before type cast,
		# data import) — a bare `self.grace_days < 0` raises TypeError on a string.
		if cint(self.grace_days) < 0:
			frappe.throw(_("Grace Days cannot be negative"))
		if not (0 <= flt(self.late_fee_percent) <= 100):
			frappe.throw(_("Late Fee % must be between 0 and 100"))
		if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
			frappe.throw(_("Effective To cannot be before Effective From"))
		if self.campus:
			campus_branch = frappe.db.get_value("MYS Campus", self.campus, "branch")
			if campus_branch != self.branch:
				frappe.throw(_("Campus {0} does not belong to branch {1}").format(self.campus, self.branch))
