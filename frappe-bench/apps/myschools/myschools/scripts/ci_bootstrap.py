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
	if frappe.db.get_value("Company", {}, "name"):
		print("CI bootstrap: Company already exists, skipping setup_complete.")
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
	frappe.db.commit()
	print("CI bootstrap complete: ran ERPNext setup_complete with " f"company={HEAD_OFFICE_COMPANY!r}.")
