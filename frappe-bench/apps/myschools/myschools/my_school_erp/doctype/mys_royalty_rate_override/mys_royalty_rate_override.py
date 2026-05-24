import frappe
from frappe import _
from frappe.model.document import Document


class MYSRoyaltyRateOverride(Document):
	def validate(self):
		if not (0 <= (self.rate_percent or 0) <= 100):
			frappe.throw(_("Royalty Rate % must be between 0 and 100"))
		if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
			frappe.throw(_("Effective To cannot be before Effective From"))

		agreement_branch = frappe.db.get_value("MYS Franchise Agreement", self.agreement, "branch")
		if agreement_branch and agreement_branch != self.branch:
			frappe.throw(
				_("Override branch {0} must match agreement branch {1}").format(self.branch, agreement_branch)
			)

		if self.campus:
			campus_branch = frappe.db.get_value("MYS Campus", self.campus, "branch")
			if campus_branch != self.branch:
				frappe.throw(_("Campus {0} does not belong to branch {1}").format(self.campus, self.branch))
