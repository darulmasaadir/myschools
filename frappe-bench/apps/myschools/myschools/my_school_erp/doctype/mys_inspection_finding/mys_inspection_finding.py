import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class MYSInspectionFinding(Document):
	def before_insert(self):
		if not self.reported_on:
			self.reported_on = today()
		if not self.reported_by:
			self.reported_by = frappe.session.user

	def validate(self):
		self._validate_resolution_state()

	def before_update_after_submit(self):
		# Frappe skips validate() on update_after_submit. We re-run the
		# resolution-state guard here so post-submit status changes (driven
		# by the Phase-5 workflow or by Corrective Action's db.set_value
		# auto-verify) still enforce the resolution_notes rule.
		self._validate_resolution_state()

	def _validate_resolution_state(self):
		if self.status == "Resolved" and not self.resolved_on:
			self.resolved_on = today()
		if self.status == "Verified" and not self.resolution_notes:
			frappe.throw(_("Cannot mark finding as Verified without resolution notes"))
