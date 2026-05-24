import frappe
from frappe import _
from frappe.model.document import Document


class MYSInspectionVisit(Document):
	def validate(self):
		if self.campus:
			campus = frappe.get_doc("MYS Campus", self.campus)
			if campus.branch != self.branch:
				frappe.throw(_("Campus {0} does not belong to branch {1}").format(self.campus, self.branch))
