"""Custom setup-wizard stages for MY Schools.

Registered via the `setup_wizard_stages` hook. Runs *after* ERPNext's
stages (presets → company → defaults → wrap-up), so by the time
`create_first_franchise_tree` fires, the Company exists and the user
has been logged in. We use that Company as the default link for the
first Branch.

The slide that collects the field values lives in
`public/js/setup_wizard.js` and is registered via the
`setup_wizard_requires` hook.

Every field is optional — operators who skip the slide get a vanilla
ERPNext install plus our app, and create their first Cluster / Branch /
Campus through the normal forms later.
"""

import frappe
from frappe import _


def get_setup_stages(args=None):
	return [
		{
			"status": _("Creating first franchise tree"),
			"fail_msg": _("Failed to create first franchise tree"),
			"tasks": [
				{
					"fn": create_first_franchise_tree,
					"args": args,
					"fail_msg": _("Failed to create first franchise tree"),
				}
			],
		}
	]


def create_first_franchise_tree(args):
	"""Optionally create one Cluster + Branch + Campus from wizard input.

	Each row is created only if its required fields are present. Skips
	silently if a record with the same primary key already exists, so
	re-running the wizard (or running this from ci_bootstrap) is
	idempotent.
	"""
	args = frappe._dict(args or {})
	cluster = _maybe_create_cluster(args)
	branch = _maybe_create_branch(args, cluster_code=cluster)
	_maybe_create_campus(args, branch_code=branch)
	frappe.db.commit()


def _maybe_create_cluster(args):
	code = (args.get("mys_cluster_code") or "").strip()
	name = (args.get("mys_cluster_name") or "").strip()
	if not (code and name):
		return None
	if frappe.db.exists("MYS Cluster", code):
		return code
	frappe.get_doc(
		{
			"doctype": "MYS Cluster",
			"cluster_code": code,
			"cluster_name": name,
			"region": args.get("mys_cluster_region") or "",
			"is_active": 1,
		}
	).insert(ignore_permissions=True)
	return code


def _maybe_create_branch(args, cluster_code):
	code = (args.get("mys_branch_code") or "").strip()
	name = (args.get("mys_branch_name") or "").strip()
	if not (code and name and cluster_code):
		return None
	if frappe.db.exists("MYS Branch", code):
		return code
	company = frappe.db.get_value("Company", {}, "name")
	frappe.get_doc(
		{
			"doctype": "MYS Branch",
			"branch_code": code,
			"branch_name": name,
			"cluster": cluster_code,
			"company": company,
			"is_active": 1,
		}
	).insert(ignore_permissions=True)
	return code


def _maybe_create_campus(args, branch_code):
	campus_type = (args.get("mys_campus_type") or "").strip()
	if not (branch_code and campus_type):
		return None
	# MYS Campus autoname is `format:{branch}-{campus_type}`.
	name = f"{branch_code}-{campus_type}"
	if frappe.db.exists("MYS Campus", name):
		return name
	frappe.get_doc(
		{
			"doctype": "MYS Campus",
			"branch": branch_code,
			"campus_type": campus_type,
			"is_active": 1,
		}
	).insert(ignore_permissions=True)
	return name
