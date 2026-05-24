# Changelog

All notable changes to MY School ERP are recorded in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project skeleton: Frappe v15 bench + ERPNext v15 + Frappe Education v15.2.
- Custom `myschools` Frappe app with:
  - Franchise hierarchy DocTypes: `MYS Cluster`, `MYS Branch`, `MYS Campus`, `MYS Department`,
    `MYS Inspection Visit`, `MYS Communication Log`.
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
