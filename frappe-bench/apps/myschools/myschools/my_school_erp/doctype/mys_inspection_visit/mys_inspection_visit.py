import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class MYSInspectionVisit(Document):
	def validate(self):
		if self.campus:
			campus = frappe.get_doc("MYS Campus", self.campus)
			if campus.branch != self.branch:
				frappe.throw(_("Campus {0} does not belong to branch {1}").format(self.campus, self.branch))
		self._compute_scores()

	def on_submit(self):
		from myschools.api.inspection import auto_create_findings_from_failed_results

		auto_create_findings_from_failed_results(self.name)

	def _compute_scores(self):
		"""Recalculate totals and weighted score from checklist_results."""
		results = self.checklist_results or []
		passed = failed = na = 0
		earned = max_possible = weighted_earned = weighted_max = 0.0

		for row in results:
			if row.result == "Pass":
				passed += 1
			elif row.result == "Fail":
				failed += 1
			elif row.result == "N/A":
				na += 1

			if row.result == "N/A":
				# N/A items don't contribute to score or denominator
				continue

			score = flt(row.score or 0)
			max_score = flt(row.max_score or 0)
			weight = flt(row.weight or 0)

			earned += score
			max_possible += max_score
			weighted_earned += score * weight
			weighted_max += max_score * weight

		self.total_items = len(results)
		self.items_passed = passed
		self.items_failed = failed
		self.items_na = na
		self.score_percent = (earned / max_possible * 100) if max_possible else 0
		self.weighted_score = (weighted_earned / weighted_max * 100) if weighted_max else 0
