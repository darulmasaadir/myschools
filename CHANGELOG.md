# Changelog

All notable changes to MY School ERP are recorded in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
