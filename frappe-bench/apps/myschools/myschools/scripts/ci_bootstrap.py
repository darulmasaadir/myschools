"""Bootstrap a freshly-installed test site so the legacy tests
(`test_inspection`, `test_royalty_from_fees`) have the prerequisites that
Frappe's setup wizard would normally provide — Gender records, the full
ERPNext fixture set (Warehouse Types, Item Groups, ...) and a Company
with chart of accounts. In real installs the setup wizard runs
interactively; CI skips that, so this script runs ERPNext's
`setup_complete()` headlessly with MY School Head Office defaults.

Idempotent — re-running is a no-op once setup has run once.

Run via:
  bench --site test_site execute myschools.scripts.ci_bootstrap.run
"""

import frappe
from erpnext.setup.setup_wizard.setup_wizard import setup_complete
from frappe.desk.page.setup_wizard.install_fixtures import update_genders

HEAD_OFFICE_COMPANY = "MY School Head Office"
ABBR = "MSHO"


def run():
	update_genders()
	from frappe.desk.page.setup_wizard.setup_wizard import disable_future_access

	if frappe.db.get_value("Company", {}, "name"):
		print("CI bootstrap: Company already exists, skipping setup_complete.")
		# Still make sure the wizard flags are set — older sites may have
		# data but not the setup_complete flags, which causes the desk to
		# redirect every login to /app/setup-wizard.
		for app in ("frappe", "erpnext"):
			frappe.db.set_value("Installed Application", {"app_name": app}, "is_setup_complete", 1)
		disable_future_access()
		frappe.db.commit()
		return

	setup_complete(
		frappe._dict(
			{
				"currency": "PKR",
				"full_name": "Administrator",
				"company_name": HEAD_OFFICE_COMPANY,
				"company_abbr": ABBR,
				"domain": "Education",
				"country": "Pakistan",
				# Fiscal Year must cover the dates used by integration tests
				# (test_royalty_from_fees posts Fees on 2025-09-15). Pakistan
				# academic year runs Jul-Jun, so this aligns with the test
				# data and is also what real installs will pick.
				"fy_start_date": "2025-07-01",
				"fy_end_date": "2026-06-30",
				"language": "english",
				"company_tagline": "MY Schools ERP CI Bootstrap",
				"email": "admin@example.com",
				"password": "admin",
				"chart_of_accounts": "Standard",
				"bank_account": "Default Bank",
			}
		)
	)
	# erpnext.setup_complete() performs the data setup but does NOT mark the
	# wizard as done — that's only set by Frappe's wizard orchestrator
	# (`disable_future_access`). Without these flags every desk login
	# redirects to /app/setup-wizard, which breaks Playwright e2e logins.
	for app in ("frappe", "erpnext"):
		frappe.db.set_value("Installed Application", {"app_name": app}, "is_setup_complete", 1)
	disable_future_access()
	_ensure_head_office_is_group()
	frappe.db.commit()
	print("CI bootstrap complete: ran ERPNext setup_complete with " f"company={HEAD_OFFICE_COMPANY!r}.")


def _ensure_head_office_is_group() -> None:
	"""seed_demo parents per-cluster Companies under MY School Head Office.
	ERPNext rejects that unless the parent has ``is_group=1``. setup_complete
	creates the HO Company as a leaf, so flip it here so seed_demo (and any
	other downstream parenting) Just Works on a fresh site.
	"""
	if not frappe.db.exists("Company", HEAD_OFFICE_COMPANY):
		return
	if frappe.db.get_value("Company", HEAD_OFFICE_COMPANY, "is_group"):
		return
	frappe.db.set_value("Company", HEAD_OFFICE_COMPANY, "is_group", 1)
