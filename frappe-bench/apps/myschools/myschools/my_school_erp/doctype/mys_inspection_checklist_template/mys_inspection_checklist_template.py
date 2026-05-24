from frappe import _, throw
from frappe.model.document import Document


class MYSInspectionChecklistTemplate(Document):
	def validate(self):
		if not self.items:
			throw(_("Checklist template must have at least one item"))
		for idx, item in enumerate(self.items, start=1):
			if (item.max_score or 0) <= 0:
				throw(_("Item #{0}: max_score must be > 0").format(idx))
			if (item.weight or 0) <= 0:
				throw(_("Item #{0}: weight must be > 0").format(idx))
