import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from myschools.api.student_lifecycle import apply_student_transfer


class MYSStudentTransfer(Document):
	def validate(self):
		if not self.student:
			return
		if not frappe.db.get_value("Student", self.student, "enabled"):
			frappe.throw(_("Cannot transfer a student who has already left (not enabled)."))

		student_branch = frappe.db.get_value(
			"Student", self.student, ["mys_branch", "mys_campus"], as_dict=True
		)
		if not student_branch or not student_branch.mys_branch:
			frappe.throw(_("Student {0} has no MYS Branch.").format(self.student))

		if not self.from_branch:
			self.from_branch = student_branch.mys_branch
		if not self.from_campus:
			self.from_campus = student_branch.mys_campus or ""

		if self.from_branch == self.to_branch and (self.from_campus or "") == (self.to_campus or ""):
			frappe.throw(_("To Branch / Campus must differ from the student's current location."))

		if self.to_campus:
			campus_branch = frappe.db.get_value("MYS Campus", self.to_campus, "branch")
			if campus_branch != self.to_branch:
				frappe.throw(
					_("Campus {0} does not belong to branch {1}").format(self.to_campus, self.to_branch)
				)

		if getdate(self.transfer_date) > getdate():
			frappe.throw(_("Transfer Date cannot be in the future."))

	def on_submit(self):
		apply_student_transfer(self)
