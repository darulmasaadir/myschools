import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from myschools.api.student_lifecycle import apply_student_leaving, generate_leaving_certificate_number


class MYSStudentLeaving(Document):
	def validate(self):
		if not self.student:
			return
		if not frappe.db.get_value("Student", self.student, "enabled"):
			frappe.throw(_("Student {0} is already marked as left (not enabled).").format(self.student))

		student = frappe.db.get_value(
			"Student",
			self.student,
			["mys_branch", "mys_campus", "mys_student_id"],
			as_dict=True,
		)
		if not student or not student.mys_branch:
			frappe.throw(_("Student {0} has no MYS Branch.").format(self.student))

		if not self.branch:
			self.branch = student.mys_branch
		if not self.campus:
			self.campus = student.mys_campus or ""
		if not self.mys_student_id:
			self.mys_student_id = student.mys_student_id or ""

		if self.branch != student.mys_branch:
			frappe.throw(_("Student {0} belongs to branch {1}, not {2}.").format(
				self.student, student.mys_branch, self.branch
			))

		if getdate(self.leaving_date) > getdate():
			frappe.throw(_("Leaving Date cannot be in the future."))

		if not self.certificate_number:
			self.certificate_number = generate_leaving_certificate_number(self.branch)

	def on_submit(self):
		apply_student_leaving(self)
