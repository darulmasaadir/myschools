import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class MYSCorrectiveAction(Document):
	def validate(self):
		if self.status in ("Completed", "Verified") and not self.completion_date:
			self.completion_date = today()
		if self.status == "Verified":
			if not self.verification_notes:
				frappe.throw(_("Cannot mark as Verified without verification notes"))
			if not self.verified_by:
				self.verified_by = frappe.session.user
			if not self.verified_on:
				self.verified_on = today()

	def on_update(self):
		"""When all corrective actions for a finding are Verified, mark the finding Verified too."""
		if self.status != "Verified":
			return
		open_actions = frappe.db.count(
			"MYS Corrective Action",
			{
				"finding": self.finding,
				"status": ["!=", "Verified"],
				"name": ["!=", self.name],
			},
		)
		if open_actions == 0:
			frappe.db.set_value("MYS Inspection Finding", self.finding, "status", "Verified")
