import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class MYSBulkFeeRun(Document):
	def validate(self):
		if getdate(self.due_date) < getdate(self.posting_date):
			frappe.throw(_("Due Date cannot be before Posting Date"))
		if self.program:
			sg_program = frappe.db.get_value("Student Group", self.student_group, "program")
			if sg_program and sg_program != self.program:
				frappe.msgprint(
					_("Student Group program {0} differs from filter {1}").format(sg_program, self.program),
					indicator="orange",
					alert=True,
				)
