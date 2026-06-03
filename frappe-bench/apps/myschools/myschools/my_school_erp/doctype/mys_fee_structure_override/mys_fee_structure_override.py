import frappe
from frappe import _
from frappe.model.document import Document


class MYSFeeStructureOverride(Document):
	def validate(self):
		if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
			frappe.throw(_("Effective To cannot be before Effective From"))

		if self.campus:
			campus_branch = frappe.db.get_value("MYS Campus", self.campus, "branch")
			if campus_branch != self.branch:
				frappe.throw(_("Campus {0} does not belong to branch {1}").format(self.campus, self.branch))

		fs = frappe.db.get_value(
			"Fee Structure",
			self.fee_structure,
			["program", "academic_year"],
			as_dict=True,
		)
		if not fs:
			frappe.throw(_("Fee Structure {0} not found").format(self.fee_structure))
		if fs.program != self.program:
			frappe.throw(
				_("Fee Structure program {0} must match override program {1}").format(
					fs.program, self.program
				)
			)
		if fs.academic_year != self.academic_year:
			frappe.throw(
				_("Fee Structure academic year {0} must match override {1}").format(
					fs.academic_year, self.academic_year
				)
			)
