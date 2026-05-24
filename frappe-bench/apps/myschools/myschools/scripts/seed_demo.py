"""Run via:
  bench --site myschools.localhost execute myschools.scripts.seed_demo.run

Seeds the franchise tree + ERPNext Companies + a sample royalty agreement
so the UI is usable immediately after install. Idempotent.
"""

import frappe
from frappe.utils import add_months, today

from myschools.setup.install import create_default_head_office_departments

HEAD_OFFICE_COMPANY = "MY School Head Office"
CLUSTER_COMPANIES = {
	"CL01": "MY School Northern Punjab",
	"CL02": "MY School Central Punjab",
	"CL03": "MY School Sindh",
}


def run():
	create_default_head_office_departments()
	_create_companies()
	_create_clusters()
	_create_branches()
	_create_campuses()
	_create_sample_royalty()
	frappe.db.commit()
	print("Demo franchise tree + companies + royalty agreement seeded.")
	_print_tree()


def _ensure(doctype, name, data):
	if frappe.db.exists(doctype, name):
		return frappe.get_doc(doctype, name)
	doc = frappe.new_doc(doctype)
	for k, v in data.items():
		doc.set(k, v)
	doc.insert(ignore_permissions=True)
	return doc


def _create_companies():
	"""Multi-Company architecture: Head Office is its own Company, then one
	Company per cluster (a single franchisee usually owns all branches in a
	cluster; if not, this can be split per-branch later).
	"""
	if not frappe.db.exists("Company", HEAD_OFFICE_COMPANY):
		c = frappe.new_doc("Company")
		c.company_name = HEAD_OFFICE_COMPANY
		c.abbr = "MSHO"
		c.default_currency = "PKR"
		c.country = "Pakistan"
		c.is_group = 1  # group company — allows cluster companies to be parented under it
		c.insert(ignore_permissions=True)

	for cluster_code, company_name in CLUSTER_COMPANIES.items():
		if frappe.db.exists("Company", company_name):
			continue
		c = frappe.new_doc("Company")
		c.company_name = company_name
		c.abbr = f"MS{cluster_code}"
		c.default_currency = "PKR"
		c.country = "Pakistan"
		c.parent_company = HEAD_OFFICE_COMPANY
		c.insert(ignore_permissions=True)


def _create_clusters():
	_ensure(
		"MYS Cluster",
		"CL01",
		{"cluster_code": "CL01", "cluster_name": "Northern Punjab", "region": "Lahore Division"},
	)
	_ensure(
		"MYS Cluster",
		"CL02",
		{"cluster_code": "CL02", "cluster_name": "Central Punjab", "region": "Faisalabad Division"},
	)
	_ensure(
		"MYS Cluster", "CL03", {"cluster_code": "CL03", "cluster_name": "Sindh", "region": "Karachi Division"}
	)


def _create_branches():
	branches = [
		("BR001", "Upper Mall Lahore", "CL01", "Lahore", "Punjab"),
		("BR002", "DHA Phase 5 Lahore", "CL01", "Lahore", "Punjab"),
		("BR014", "Gulshan-e-Iqbal Karachi", "CL03", "Karachi", "Sindh"),
	]
	for code, name, cluster, city, prov in branches:
		_ensure(
			"MYS Branch",
			code,
			{
				"branch_code": code,
				"branch_name": name,
				"cluster": cluster,
				"company": CLUSTER_COMPANIES.get(cluster),
				"city": city,
				"province": prov,
				"is_active": 1,
			},
		)
		# Backfill company on existing rows (idempotent re-runs)
		if frappe.db.exists("MYS Branch", code):
			frappe.db.set_value("MYS Branch", code, "company", CLUSTER_COMPANIES.get(cluster))


def _create_campuses():
	for branch in ["BR001", "BR014"]:
		for campus_type in ["Kids", "Junior", "Senior"]:
			campus_name = f"{branch}-{campus_type}"
			if not frappe.db.exists("MYS Campus", campus_name):
				doc = frappe.new_doc("MYS Campus")
				doc.branch = branch
				doc.campus_type = campus_type
				doc.is_active = 1
				doc.insert(ignore_permissions=True)


def _create_sample_royalty():
	"""Creates one Franchise Owner + Agreement + a campus-level Rate Override.
	Proves the configurable rate end-to-end: BR014 default is 7%, but the
	Junior campus is overridden to 5% as a ramp-up incentive.
	"""
	owner_name = "Sample Franchisee — Karachi"
	owner = frappe.db.get_value("MYS Franchise Owner", {"owner_name": owner_name}, "name")
	if not owner:
		o = frappe.new_doc("MYS Franchise Owner")
		o.owner_name = owner_name
		o.cnic = "42101-1234567-1"
		o.ntn = "1234567-8"
		o.phone = "+92-300-1234567"
		o.email = "franchisee.karachi@example.com"
		o.city = "Karachi"
		o.province = "Sindh"
		o.status = "Active"
		o.insert(ignore_permissions=True)
		owner = o.name

	# One Active agreement for BR014
	agreement_exists = frappe.db.exists(
		"MYS Franchise Agreement",
		{"branch": "BR014", "status": "Active", "docstatus": 1},
	)
	if not agreement_exists:
		ag = frappe.new_doc("MYS Franchise Agreement")
		ag.franchisee = owner
		ag.branch = "BR014"
		ag.company = CLUSTER_COMPANIES["CL03"]
		ag.start_date = today()
		ag.end_date = add_months(today(), 60)  # 5-year term
		ag.default_royalty_rate = 7.0
		ag.royalty_base = "Gross Fee Collection"
		ag.billing_day = 5
		ag.grace_days = 10
		ag.security_deposit = 500000
		ag.deposit_received = 1
		ag.franchise_fee = 1500000
		ag.currency = "PKR"
		ag.status = "Draft"
		ag.insert(ignore_permissions=True)
		ag.submit()
		agreement_name = ag.name
	else:
		agreement_name = agreement_exists

	# Campus-level override: BR014 Junior campus gets 5% (ramp-up incentive)
	# This is what proves "should be configurable, can vary from campus to campus"
	junior_override_exists = frappe.db.exists(
		"MYS Royalty Rate Override",
		{"agreement": agreement_name, "branch": "BR014", "campus": "BR014-Junior"},
	)
	if not junior_override_exists:
		ov = frappe.new_doc("MYS Royalty Rate Override")
		ov.agreement = agreement_name
		ov.branch = "BR014"
		ov.campus = "BR014-Junior"
		ov.rate_percent = 5.0
		ov.effective_from = today()
		ov.is_active = 1
		ov.reason = (
			"Ramp-up incentive: reduced rate for first 12 months while Junior campus builds enrolment."
		)
		ov.insert(ignore_permissions=True)

	# Branch-level override on BR001: bumped down to 6% for the whole branch
	# (demonstrates per-branch overrides too)
	br001_agreement = frappe.db.exists(
		"MYS Franchise Agreement",
		{"branch": "BR001", "status": "Active", "docstatus": 1},
	)
	if not br001_agreement:
		# Need an agreement on BR001 too — re-use the same owner for demo
		ag2 = frappe.new_doc("MYS Franchise Agreement")
		ag2.franchisee = owner
		ag2.branch = "BR001"
		ag2.company = CLUSTER_COMPANIES["CL01"]
		ag2.start_date = today()
		ag2.end_date = add_months(today(), 60)
		ag2.default_royalty_rate = 7.0
		ag2.royalty_base = "Gross Fee Collection"
		ag2.billing_day = 5
		ag2.grace_days = 10
		ag2.security_deposit = 500000
		ag2.deposit_received = 1
		ag2.currency = "PKR"
		ag2.status = "Draft"
		ag2.insert(ignore_permissions=True)
		ag2.submit()
		br001_agreement = ag2.name

	br001_branch_override = frappe.db.exists(
		"MYS Royalty Rate Override",
		{"agreement": br001_agreement, "branch": "BR001", "campus": ["in", ["", None]]},
	)
	if not br001_branch_override:
		ov2 = frappe.new_doc("MYS Royalty Rate Override")
		ov2.agreement = br001_agreement
		ov2.branch = "BR001"
		ov2.campus = None
		ov2.rate_percent = 6.0
		ov2.effective_from = today()
		ov2.is_active = 1
		ov2.reason = "Long-standing flagship branch — negotiated 1% reduction across all campuses."
		ov2.insert(ignore_permissions=True)


def _print_tree():
	print("\nFranchise tree:")
	for cl in frappe.get_all("MYS Cluster", fields=["name", "cluster_name"]):
		print(f"  {cl.name} - {cl.cluster_name}")
		branches = frappe.get_all(
			"MYS Branch", filters={"cluster": cl.name}, fields=["name", "branch_name", "city", "company"]
		)
		for br in branches:
			print(f"    {br.name} - {br.branch_name} ({br.city})  ->  Company: {br.company}")
			campuses = frappe.get_all(
				"MYS Campus", filters={"branch": br.name}, fields=["name", "campus_type"]
			)
			for c in campuses:
				print(f"      {c.name}")
	print("\nDepartments (Head Office):")
	for d in frappe.get_all("MYS Department", fields=["name", "tier"]):
		print(f"  {d.name} - {d.tier}")

	print("\nRoyalty rates (resolved):")
	from myschools.api.royalty import resolve_royalty_rate

	for ag in frappe.get_all(
		"MYS Franchise Agreement",
		filters={"docstatus": 1},
		fields=["name", "branch", "default_royalty_rate"],
	):
		print(f"  Agreement {ag.name} (branch {ag.branch}, default {ag.default_royalty_rate}%):")
		campuses = frappe.get_all("MYS Campus", filters={"branch": ag.branch}, pluck="name")
		for c in campuses:
			rate, src = resolve_royalty_rate(ag.name, ag.branch, c)
			print(f"    {c:30s}  ->  {rate}%  ({src})")
