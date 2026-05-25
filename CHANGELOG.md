# Changelog

All notable changes to MY School ERP are recorded in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Documentation
- Reworked `docs/architecture.md` to reflect the inspection decomposition, multi-Company royalty,
  and shipped-vs-planned module status (✅ / 🟡 / ⬜ legend).
- Added a documentation set under `docs/`:
  - `docs/README.md` — nav index (tech + non-tech audiences).
  - `docs/overview.md` — what/who/why for non-technical readers.
  - `docs/data-model.md` — DocType-by-DocType field reference.
  - `docs/development.md` — bench setup, daily workflow, test conventions,
    debugging tips, release process, documentation policy.
  - `docs/processes/royalty-billing.md` — operator-facing monthly cycle.
  - `docs/processes/inspection-workflow.md` — operator-facing inspection lifecycle.
  - `docs/api/royalty.md`, `docs/api/inspection.md` — function references.
- Root `README.md` and `CONTRIBUTING.md` updated to link into the docs set.

### Added
- **MY Schools navigation shell** — turns vanilla ERPNext into a role-aware MY Schools ERP.
  - Brand: `app_logo_url`, `brand_html`, `website_context` (favicon, splash), `app_include_css`
    in `hooks.py`. Placeholder SVGs under `myschools/public/images/` (`mys-logo.svg`,
    `mys-favicon.svg`, `mys-splash.svg`) and a brand-tokens stylesheet at
    `myschools/public/css/myschools.css`.
  - 5 role-restricted Workspaces shipped as JSON fixtures under
    `myschools/my_school_erp/workspace/<slug>/<slug>.json`: `mys-head-office`, `mys-cluster`,
    `mys-branch`, `mys-campus`, `mys-inspection`. The HO workspace embeds the Central
    Monitoring Dashboard inline (no URL hunting); each lower-tier workspace ships the
    shortcuts and charts its roles actually need.
  - `role_home_page` hook for portal (Website User) flows. **Desk** users use
    `User.default_workspace`, which the auto-attach helper sets alongside the
    Module Profile — without this, desk users would land on `/app/home`
    regardless of the hook.
  - Read-permission matrix granted on a per-tier basis in
    `setup/install.py::grant_franchise_role_permissions` so each role's
    workspace shortcuts and number cards actually render. Row-level isolation
    still flows through `permission_query_conditions`.
  - 5 Module Profile fixtures under `myschools/fixtures/module_profile.json` (`MYS HO`,
    `MYS Cluster`, `MYS Branch`, `MYS Campus`, `MYS Inspection`) hide vanilla modules
    (Manufacturing, Stock, Buying, etc.) per tier. Attached automatically to Users on
    `User.validate` via `myschools.api.user_profile.attach_module_profile_to_user`
    (highest-tier role wins); existing Users back-filled on `after_migrate`.
  - `MYS Default` Letter Head fixture under `myschools/fixtures/letter_head.json` —
    branded header/footer that downstream Print Formats will inherit.
  - 12 tests in `myschools/tests/test_shell.py` covering workspace import, role→workspace
    routing, Letter Head presence, Module Profile import + child-row counts, the tier
    resolvers for both Module Profile and default workspace, and end-to-end
    `User.module_profile` + `User.default_workspace` auto-attach on create.
  - `scripts/seed_test_users.py`: idempotent dev-only seed that creates one
    System User per franchise role with password `admin`, so the navigation
    shell can be smoke-tested by logging in as each role.
- **MYS Central Monitoring Dashboard** — single role-aware dashboard tying together royalty,
  fee, branch, and inspection KPIs. Renders the same dashboard for every role; rows are filtered
  via the `permission_query_conditions` registered in `hooks.py` (custom-method cards apply
  `_branch_scope_sql` directly), so a Branch Admin sees their branch's numbers and the Chief
  Executive sees national totals — without a separate dashboard per role.
  - 8 Number Cards shipped as JSON fixtures under
    `myschools/my_school_erp/number_card/<slug>/<slug>.json`: Active Branches, Active Students,
    Outstanding Royalty (PKR), Overdue Invoices, This Month — Royalty Invoiced, This Month —
    Fees Collected, Open Inspection Findings, Overdue Inspection Findings.
  - 3 Dashboard Charts under `myschools/my_school_erp/dashboard_chart/`: Findings by Severity
    (Donut), Royalty by Cluster YTD (Bar), Royalty Invoiced Trend 12m (Line).
  - 1 Dashboard fixture at `myschools/my_school_erp/my_school_erp_dashboard/mys_central_monitoring/`
    wiring everything together; folder is named `<module_slug>_dashboard` because that's the
    only path `frappe.utils.dashboard.sync_dashboards` scans on migrate.
  - `myschools/api/dashboard.py`: 3 whitelisted endpoints feeding the Custom-type cards
    (`current_month_royalty_invoiced`, `current_month_fees_collected`, `overdue_findings_count`)
    plus `_branch_scope_sql` helper that converts the active user's franchise scope into a SQL
    `AND <col> IN (...)` fragment (returning a `"DENY"` sentinel for users with no scope).
  - `MYS Royalty Invoice.cluster` Link field added with `fetch_from="branch.cluster"` so the
    Royalty-by-Cluster Group By chart has a column to aggregate on.
  - `myschools/tests/test_dashboard.py`: 8 tests verifying every fixture imports on migrate,
    the dashboard's cards/charts tables wire the expected entries, and all three custom-method
    endpoints return the `{value, fieldtype, [currency]}` shape Frappe's Number Card expects.
- **End-to-end Fees → Royalty Invoice loop** wired to real Frappe Education data.
  - `myschools/scripts/seed_education.py`: idempotent seed for Academic Year/Term, Programs,
    Fee Category, Fee Structures, Students (stamped with `mys_cluster` / `mys_branch` / `mys_campus`),
    Program Enrollments, and submitted `Fees` for May 2026 across BR001 and BR014.
  - `myschools/scripts/demo_royalty_invoice.py` rewritten to call
    `generate_monthly_royalty_invoices(2026, 5)` against the real `tabFees` rollup, replacing
    the previous hard-coded collection numbers.
  - `myschools/tests/test_royalty_from_fees.py`: 3-test integration suite verifying that
    `get_branch_collection_for_period` groups submitted Fees by `Student.mys_campus`, that
    out-of-period Fees are excluded, and that `generate_monthly_royalty_invoices` populates
    campus_lines from real Fees with correct rate resolution.
- `Fee Structure.income_account` Custom Field (created via `after_migrate`) to work around an
  upstream Frappe Education v15.5.3 bug where `Fees.income_account` declares
  `fetch_from: "fee_structure.income_account"` but the Fee Structure table lacks the column.
- **Inspection workflow decomposition**: replaced the single `MYS Inspection Visit` stub with a
  five-doctype workflow.
  - `MYS Inspection Checklist Template` (+ `MYS Inspection Checklist Item` child): reusable
    versioned templates per visit type with weighted scoring metadata (severity, weight, max_score).
  - `MYS Inspection Visit` (rewritten): adds checklist results table, auto-computed totals
    (items passed/failed/N/A) and both raw and weighted score percentages. Snapshots template
    items so historical visits stay stable across template revisions.
  - `MYS Inspection Finding` (submittable): one finding per Critical/Major failed checklist
    item, auto-created on visit submit. Tracks severity, due date, status (Open → In Progress →
    Resolved → Verified) with branch-scoped permissions.
  - `MYS Corrective Action`: planned/in-progress/completed/verified actions linked to a finding;
    verifying the last open action auto-flips the parent finding to Verified.
- `myschools.api.inspection`: `apply_template_to_visit`, `auto_create_findings_from_failed_results`,
  plus permission-query conditions wired through `hooks.py`.
- 9 integration tests in `myschools/tests/test_inspection.py` covering template application,
  score math (including N/A skip), branch/campus validation, auto-create idempotency, and the
  corrective-action → finding state machine.

### Initial bootstrap
- Frappe v15 bench + ERPNext v15 + Frappe Education v15.2.
- Custom `myschools` Frappe app with:
  - Franchise hierarchy DocTypes: `MYS Cluster`, `MYS Branch`, `MYS Campus`, `MYS Department`,
    `MYS Communication Log`.
  - Royalty DocTypes: `MYS Franchise Owner`, `MYS Franchise Agreement`, `MYS Royalty Rate Override`,
    `MYS Royalty Invoice` (+ `MYS Royalty Invoice Campus Line`), `MYS Royalty Payment`.
  - Custom fields on `Student`, `Employee`, `Guardian` linking them to the franchise tree.
  - Auto-ID generation: `MYS-{cluster}-{branch}-STU{######}` (Student),
    `MYS-{branch}-{role}{####}` (Staff).
  - 10 franchise roles + branch-scoped `permission_query_conditions` for data isolation.
  - Configurable royalty rate with resolution order **campus override > branch override > agreement default**.
  - Monthly scheduled job to auto-generate royalty invoices for the prior period.
- Multi-Company architecture: Head Office as group company; per-cluster Companies parented under HO;
  each `MYS Branch` linked to its Company for isolated financials.
- Seed scripts: `seed_demo.run` (franchise tree + companies + sample royalty agreements);
  `demo_royalty_invoice.run` (one fully-submitted royalty invoice with per-campus rate breakdown).

### Engineering
- Repository initialised with git.
- Pre-commit hooks: trailing whitespace, merge-conflict, AST, JSON/TOML/YAML lint, ruff (lint + format).
- Ruff configured via `pyproject.toml` (line-length 110, py310 target, tab indent).
- GitHub Actions CI: lint + unit tests on push and PR.
- Unit tests for `myschools.api.royalty.resolve_royalty_rate` covering the override precedence
  rules and effective-date gating.
