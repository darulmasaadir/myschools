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
