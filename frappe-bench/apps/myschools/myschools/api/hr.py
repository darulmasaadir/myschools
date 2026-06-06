"""Phase 8d — HR / payroll scaffolding over ERPNext + frappe/hrms.

MY School does not fork payroll. We layer the franchise hierarchy onto hrms'
``Payroll Entry`` with two `mys_*` Custom Fields (created in `setup/install.py`)
and the helpers below:

  * `set_payroll_entry_company_from_branch` — keep the payroll run's `Company`
    aligned with the branch's books (each MYS Branch owns one ERPNext Company).
  * `payroll_entry_query` — branch-scope the Payroll Entry list so franchise
    roles only see their own branch's runs, mirroring the Student/Employee
    pattern in `api/permissions.py`.
"""

import frappe
from frappe import _

from myschools.api.permissions import _branch_filter, _user_scope


def set_payroll_entry_company_from_branch(doc, method=None):
	"""Default / validate `company` from the selected MYS Branch.

	Each MYS Branch links to exactly one ERPNext Company (its books). When a
	payroll run is scoped to a branch we default the Company from it, and reject
	a Company that does not match the branch — so a branch's salaries can never
	post to another branch's ledger.
	"""
	if not doc.get("mys_branch"):
		return
	branch_company = frappe.db.get_value("MYS Branch", doc.mys_branch, "company")
	if not branch_company:
		return
	if not doc.get("company"):
		doc.company = branch_company
	elif doc.company != branch_company:
		frappe.throw(
			_("Company {0} does not match branch {1}'s company {2}").format(
				doc.company, doc.mys_branch, branch_company
			)
		)


def payroll_entry_query(user):
	"""Row scoping for Payroll Entry — branch staff only see their branch's
	runs; cluster roles their cluster; HO/CEO/System Manager see all."""
	return _branch_filter("mys_branch", user) or ""


def payroll_entry_has_permission(doc, ptype="read", user=None):
	"""Per-document permission check for Payroll Entry, mirroring Student."""
	user = user or frappe.session.user
	scope, branches = _user_scope(user)
	if scope == "global":
		return True
	if not branches:
		return False
	return doc.get("mys_branch") in branches
