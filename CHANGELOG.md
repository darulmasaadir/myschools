# Changelog

All notable changes to MY School ERP are recorded in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Phase 11 e2e backfill (PR #25, `e747c60`).** Playwright asserts `/branch`
  dashboard timetable card, guardian `?student=` filter (owned + rejected
  non-owned child), and desk `Course Schedule` list scope; guardian seed links a
  second child for the selector.
- **Phase 11 — Academic scheduling (PR #24, `98821d9`).** Shared `api/scheduling.py`;
  `/branch/timetable`, `/guardian/timetable`, week-grouped `/teacher/schedule`;
  desk `course_schedule_query` + `student_group_query`; seed Mon–Fri schedules +
  `e2e_guardian@mys.local`; `test_scheduling.py`, HTTP battery, Playwright
  `phase11_timetable.spec.ts`.
- **Phase 10 — Attendance + Examination (PR #23, `584a0d0`).** Teacher portal
  attendance + assessment marking (`/teacher/attendance`, `/teacher/assessments`,
  `/teacher/assessment`); `save_class_attendance` / `save_assessment_scores` /
  `download_report_card`; `MYS Report Card` print format; seed, unit tests, HTTP
  battery POST, Playwright `phase10_teacher_attendance.spec.ts` (incl. PDF bytes).
- **Phase 9 — Teacher Portal (PR #22, `09185cb`).** `Teacher` franchise role;
  `api/teacher_portal.py`; `/teacher` routes (dashboard, classes, roster,
  schedule); `seed_portal_teacher.py`; unit tests, HTTP battery, Playwright
  `phase9_teacher_portal.spec.ts`.
- **Phase 8e — payment gateway stubs (PR #20, `802e6fc`).** `MYS Payment Settings`
  single (Stub, JazzCash, Easypaisa, HBL); `payment_providers.dispatch_payment` +
  `payments.initiate_fee_payment` with Communication Log audit (`channel=Payment`);
  `stub_payment_complete` guest callback; `verify_payment_adapters.py`, unit tests,
  Playwright settings + full payment happy-path e2e; battery + CI wiring.
- **Phase 8d — HR / payroll scaffolding (PR #19, `376576f`).** `frappe/hrms` in
  `required_apps`; branch-scoped `Employee`; `mys_branch`/`mys_campus` on Payroll Entry;
  `verify_hr_surfaces.py` + Playwright `phase8d_hr_payroll`.
- **Phase 8c — SMS/email provider adapters (PR #18, `7094642`).** `MYS SMS Settings`;
  `sms_providers` registry; gateway fields on Communication Log; verify script + Playwright.
- **Phase 8b — student lifecycle (PR #17, `341295e`).** `MYS Student Transfer` /
  `MYS Student Leaving`; leaving certificate print format; verify script + Playwright.
- **Phase 8a — fee-admin desk polish.** Bulk Fee Run / Fee Structure Override / Late
  Fee Policy added to the MYS Branch workspace (shortcut + links); fee-admin link-target
  reads (Program/Academic Year/Term/Fee Structure/Student Group/Fee Category) granted to
  Branch Director/Accountant/Admin so the desk forms are fillable; role × surface guard
  `scripts/verify_fee_admin_surfaces.py` (wired into battery + CI); Playwright
  `phase8a_bulk_fee_run` (seeded + from-blank) and `phase8a_fee_admin_forms`.

### Changed

- **CI — GitHub Actions Node-24 majors (PR #26, `a84b840`).** Bump
  `checkout`/`setup-python`/`setup-node`/`cache`/`upload-artifact` to v5/v6
  runtimes ahead of the Node 20 runner deprecation (2026-09-16).
- **PR verification rule** — mandatory per-phase **5a/5b/5c** trio (local
  Playwright, manual dev browser walk with screenshots, spec-completeness audit);
  codified after Phase 11 PR #24 shortfall (`3062c3d`).

### Fixed

- **Late Fee Policy validate `TypeError`.** `grace_days` compared against `int` raised
  `'<' not supported between 'str' and 'int'` when set as a string (client `set_value`,
  API, import); now `cint`-guarded with a regression test.

### Added (cont.)

- **Phase 8a-4 — bulk Fees generator.** `MYS Bulk Fee Run` doctype with **Generate Fees**
  action; `generate_bulk_fees_for_run` creates submitted `Fees` per active student-group
  member (override resolution, duplicate skip); `tests/test_bulk_fee_run.py`.
- **Phase 8a-2/8a-3 (in branch).** Billing safety (module profile + `restrict_split_brain_billing_paths`);
  `Fees.validate` → `apply_resolved_fee_structure_on_fees`.
- **Phase 8a — fee overrides + late fees (in flight).** `MYS Fee Structure Override` and
  `MYS Late Fee Policy` doctypes; [`api/fees.py`](frappe-bench/apps/myschools/myschools/api/fees.py)
  with `resolve_fee_structure`, `apply_late_fees`, and daily scheduler; custom fields on `Fees`
  (`mys_late_fee_for`, `mys_late_fee_applied`); tests in `tests/test_fees.py`.
- **Billing model decision** — [docs/processes/billing-model.md](docs/processes/billing-model.md):
  canonical student billing = Education `Fees`; Fee Schedule → Sales Invoice is out of
  scope; roadmap follow-ups **8a-2** (module profile trim), **8a-3** (wire
  `resolve_fee_structure` on Fees creation), **8a-4** (bulk Fees generator).
- **Late-fee scheduler e2e** (`scripts/verify_late_fees.py`) — fires the real
  `scheduled_apply_late_fees()` entrypoint against a self-contained overdue scenario and asserts
  the linked late fee, parent flag, and idempotency. Wired into `scripts/pr_battery.sh` and the CI
  e2e job so the 8a scheduler path is covered automatically, not by hand.
- **Phase 7d Playwright regression** (`tests/e2e/phase7d_inspection_portal.spec.ts`) — inspection
  portal happy path, fail→finding, role denial, guest admission; extends `seed_e2e` with
  `e2e_monitor@mys.local` and checklist template.
- **Coverage ratchet** — `coverage_floor.json` + `check_coverage_floor.py` enforced in CI
  after `run-tests --coverage`.
- **E2E / flaky policy** — [docs/processes/e2e-and-flaky-tests.md](docs/processes/e2e-and-flaky-tests.md).
- **HTTP battery + branch-desk matrix in CI** — `verify_http_battery.py` and
  `verify_branch_desk_cards.py` (previously run by hand) now execute in the
  e2e job after a `seed_test_users` step, so the full role × surface check is
  automated on every push.
- **Unit regression** — `test_fail_critical_as_academic_monitor_creates_open_finding` (workflow
  Submit as Monitor).
- **Setup Wizard, Module Onboarding & Reports (Phase 6).** Three
  independent slices that close out the operator-onboarding gap:
  - **Setup Wizard.** New JS slide
    (`public/js/setup_wizard.js`) added after ERPNext's stock slides via
    `setup_wizard_requires`. Optional fields for first Cluster / Branch /
    Campus. The matching Python stage
    (`scripts/setup_wizard.py`) is registered via `setup_wizard_stages`
    and runs after ERPNext has created the Company, so the first Branch
    has a Company to link to. Every field is optional, partial input is
    silently dropped, and re-running the wizard is idempotent (skips
    records that already exist).
  - **Module Onboarding.** New `MYS Franchise Setup` Module Onboarding
    fixture plus six Onboarding Step fixtures (Add First Cluster → Add
    First Branch → Add First Campus → Sign First Agreement → Book First
    Inspection → View Central Dashboard). The card surfaces on every MYS
    workspace because all five workspaces share `module = MY School ERP`.
    Six operator-facing roles have visibility.
  - **First batch of Query Reports.** Four Script Reports under
    `my_school_erp/report/`: `MYS Royalty Aging`,
    `MYS Fee Collection by Branch`, `MYS Findings by Branch and
    Severity`, `MYS Branch Health Scorecard`. All four respect existing
    `permission_query_conditions` so a Cluster Director sees only her
    cluster, etc.
  - New fixture filters in `hooks.py` export Module Onboarding,
    Onboarding Step and `is_standard=Yes` MYS Reports.
  - 18 new tests across three modules (`tests/test_setup_wizard.py`,
    `tests/test_onboarding.py`, `tests/test_reports.py`) — full suite
    now 92/92 passing.
  - Process doc `docs/processes/setup-and-onboarding.md` covers the
    full first-time-install operator journey, the wizard slide contract,
    the onboarding step model, the four reports' columns and roles, and
    headless-install gotchas (`is_setup_complete` flag flipping in
    `ci_bootstrap`).

- **Workflows & List View polish (Phase 5).** Two formal Frappe Workflows
  attached to existing `status` fields:
  - `MYS Inspection Finding Workflow` — Draft → Open → In Progress →
    Resolved → Verified (+ Cancelled). Role-gated transitions:
    Submit/Cancel by Audit Officer / Branch Director / Branch Principal,
    Acknowledge + Mark Resolved by Branch Director / Branch Principal,
    Verify + Reject Resolution by **Audit Officer only**.
  - `MYS Royalty Invoice Workflow` — Draft → Unpaid (submit by HO Dept
    Head or Branch Accountant). Payment-driven states (Partial / Paid /
    Overdue) keep flowing via `db.set_value` from the controller's
    `_refresh_status` — a regression test pins that bypass.
  - All three fixture files (`workflow.json`, `workflow_state.json`,
    `workflow_action_master.json`) generated from
    `scripts/build_workflows.py` — never hand-edit the JSON.
  - List-view JS for severity badges (Finding) and status indicators
    (Finding, Royalty Invoice, Visit).
  - Form-JS primary actions: "Create Corrective Action" shortcut on
    Open / In Progress Findings; "Send Reminder" on overdue Royalty
    Invoices that fires the Phase-4 overdue template immediately via the
    new whitelisted `api.royalty.send_overdue_reminder`.
  - 10 new tests in `tests/test_workflows.py` (fixture coverage, state
    machine walks, role gating with `frappe.set_user` context, payment
    `db_set` bypass) — full suite now 74/74 passing.
  - Process doc `docs/processes/workflows.md` covers transition matrices,
    the `update_after_submit` controller-validate gotcha, the
    `allow_on_submit` field requirement, and `WorkflowTransitionError`
    vs `WorkflowPermissionError` semantics.
  - **Playwright e2e suite** (`tests/e2e/workflows.spec.ts`, 6 cases) wired
    into a new `e2e` CI job: logs in as the Audit Officer / Branch Director
    / Administrator, opens the Resolved finding + the overdue royalty
    invoice, and asserts the right workflow buttons render for each role.
    Deterministic test data is created by
    `scripts/seed_e2e.py`. The suite caught a missing
    `Workflow State Draft` fixture record that unit tests couldn't see —
    `Draft` and `Cancelled` are now shipped in `workflow_state.json`
    alongside the visible states. Frappe ships `Pending`/`Approved`/
    `Rejected` as defaults but **not** these two, and without the records
    the form throws a blocking "Workflow State X not found" modal even
    though every backend transition still works.

- **Notifications & Communication wiring (Phase 4).** Six `Email Template` +
  six `Notification` fixtures generated from a single source-of-truth builder
  (`scripts/build_notifications.py`) cover royalty invoice generated, royalty
  invoice overdue (Days After due_date), inspection finding assigned, finding
  overdue, corrective action overdue, and franchise agreement expiring (30
  days before end_date). Each fires off the underlying doctype's lifecycle
  events and pings the right mix of role-based recipients and
  document-field-based recipients (e.g. `reported_by`, `assigned_to`). All
  templates use the MY Schools branded HTML container and inherit the
  primary green `#0F7A4A`.
  - `Communication.after_insert` mirror (`api/notifications.log_outbound_email`)
    so every outbound system email tied to an MYS doctype (or `Fees`) lands in
    `MYS Communication Log` with branch / campus / scope auto-resolved.
    Inbound mail, drafts, and non-MYS references are skipped — Frappe's own
    `Communication` doctype already captures those, and the audit log shouldn't
    double up.
  - Provider-agnostic `send_sms(recipient, message, doctype, name)` stub
    (`api/notifications.send_sms`) writes a `Sent` row to `MYS Communication
    Log` today; Phase 8 swaps `gateway="stub"` for a real Pakistani gateway
    (Jazz / Easypaisa / Twilio) without changing the signature. Callers
    (Notifications using `channel=SMS`, scheduled jobs, future WhatsApp
    adapter) stay unchanged when the real gateway lands.
  - 11 unit tests in `tests/test_notifications.py` across three classes —
    fixture coverage (all 6 imported, use_html, enabled, correct doctype +
    event, Days After date_changed, 30-days-before for agreement, mixed-mode
    recipients on Finding Assigned), SMS stub (returns ok/gateway/log, writes
    Log, rejects empty args), and `log_communication` helper field round-trip.
  - Process doc `docs/processes/notifications.md` covers what ships, how an
    alert actually fires, how to add a new one (always via the builder, never
    by hand-editing fixtures), why the audit log lives outside Frappe's own
    `Communication`, and a troubleshooting table.

### Fixed
- **Dashboard charts no longer crash the Central Monitoring view.** The three
  MYS Dashboard Chart fixtures shipped `filters_json` as a JSON object
  (`{"docstatus":1}`) instead of an array of arrays. Frappe's
  `dashboard_chart.get()` calls `.append()` on the parsed filters, so the
  object form crashed every chart render with `'NoneType' object is not
  callable` and the desk dashboard surfaced a server-error modal in front of
  the loading charts. All three fixtures (`MYS - Findings by Severity`,
  `MYS - Royalty by Cluster (YTD)`, `MYS - Royalty Invoiced Trend (12m)`)
  now use the array-of-arrays form Frappe expects. Two regression tests
  added to `tests/test_dashboard.py` so this shape mistake can never land
  again: one parses each chart's `filters_json` and asserts list-of-lists,
  one calls `dashboard_chart.get()` directly and asserts no exception.

### Documentation
- **`docs/roadmap.md` — single source of truth for customisation phase status.**
  Captures all 8 phases (Branding, Workspaces, Print Formats, Notifications,
  Workflows, Setup Wizard, Portals, Domain extensions) with status, delivering
  PR + commit SHA for each shipped phase, and the standing constraints that bind
  every PR (upgrade-safe only, test-first, conventional commits). Phase 7
  rewritten in this doc from "Vue/React SPA" to "Frappe Web Forms + `www/`
  Jinja templates" per the upgrade-safe-only constraint. Motivated by
  near-mistake: cut a `feature/shell-phase-1-2` branch to "start Phase 1+2"
  when it had already shipped in PR #3 — the session plan was stale, the repo
  had no roadmap doc to consult. Now the repo does.
- `docs/overview.md` § "What's shipped today" updated to match current state:
  adds the role-aware ERP shell (Phases 1+2) and branded Print Formats
  (Phase 3) as ✅, and lists Phases 4–8 as ⬜ with a one-line scope hint.
- `docs/architecture.md` § 3 "Modules shipped so far" gains two rows for the
  Navigation shell and Print Formats modules so the architectural table
  doesn't trail behind the roadmap.
- `docs/README.md` nav index links to `roadmap.md` for evaluators and adds it
  to the layout diagram.
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
- **Branded Print Formats (Phase 3)** — 4 Jinja-driven Print Formats ship as fixtures and become
  the default print layout on the doctypes franchise operators actually hand to franchisees, the
  branch staff, parents, and inspectors.
  - `myschools/fixtures/print_format.json` — generated from
    `myschools/scripts/build_print_formats.py` (single Python source of truth, one triple-quoted
    Jinja template per format). 4 records:
    - `MYS Royalty Invoice` (doctype `MYS Royalty Invoice`) — campus breakdown, totals, status
      badge, paid/outstanding panel.
    - `MYS Inspection Report` (doctype `MYS Inspection Visit`) — scorecard tiles
      (items/passed/failed/score/weighted), severity-coloured checklist table, recommendations.
    - `MYS Fee Receipt` (doctype `Fees`) — student / program / term header, component table,
      PAID / OUTSTANDING badge.
    - `MYS Franchise Agreement` (doctype `MYS Franchise Agreement`) — royalty terms,
      financials, signature blocks.
  - `setup/install.py::set_default_print_formats` creates 4 Property Setters wiring
    `default_print_format` on each target doctype, so opening a doc and hitting Print shows the
    MYS layout without needing to choose it from the picker. Runs on both `after_install` and
    `after_migrate` (after fixtures import, so target records exist).
  - All four records ship with `custom_format=1` — required so the renderer dispatches to our
    `html` field instead of falling back to Frappe's auto-built "Standard" layout.
  - `Print Format` and the four `Property Setter` records are exported via `fixtures` in
    `hooks.py` so they import cleanly on a fresh install.
  - `myschools/tests/test_print_formats.py`: 6 tests building a full fixture tree (Cluster →
    Branch → Campus → Employee + Franchise Owner/Agreement + Program/AcademicYear/Fee chain +
    Inspection Visit + generated Royalty Invoice), asserting every Print Format exists, every
    Property Setter exists, and each format renders against a real doc with the expected MYS
    marker in the HTML.
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
