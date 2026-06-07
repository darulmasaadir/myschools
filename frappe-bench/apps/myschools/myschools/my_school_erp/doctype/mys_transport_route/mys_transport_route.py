import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class MYSTransportRoute(Document):
	def validate(self):
		if flt(self.fee_amount) < 0:
			frappe.throw(_("Monthly Fee cannot be negative."))
		if self.vehicle:
			vehicle_branch = frappe.db.get_value("MYS Vehicle", self.vehicle, "branch")
			if vehicle_branch and vehicle_branch != self.branch:
				frappe.throw(
					_("Vehicle {0} belongs to branch {1}, not {2}.").format(
						self.vehicle, vehicle_branch, self.branch
					)
				)
