"""Bootstrap a freshly-installed test site so the legacy tests
(`test_inspection`, `test_royalty_from_fees`) have the prerequisites that
Frappe's setup wizard would normally provide — Gender records and at least
one Company. In real installs the setup wizard runs interactively; CI
skips that, so this script mimics the slice of it the tests depend on.

Idempotent — safe to run multiple times.

Run via:
  bench --site test_site execute myschools.scripts.ci_bootstrap.run
"""

import frappe
from frappe.desk.page.setup_wizard.install_fixtures import update_genders


HEAD_OFFICE_COMPANY = "MY School Head Office"


def run():
    update_genders()
    _ensure_company()
    frappe.db.commit()
    print(
        "CI bootstrap complete: Genders + Company "
        f"({HEAD_OFFICE_COMPANY}) ready for tests."
    )


def _ensure_company():
    if frappe.db.get_value("Company", {}, "name"):
        return
    company = frappe.new_doc("Company")
    company.company_name = HEAD_OFFICE_COMPANY
    company.abbr = "MSHO"
    company.default_currency = "PKR"
    company.country = "Pakistan"
    company.insert(ignore_permissions=True)
