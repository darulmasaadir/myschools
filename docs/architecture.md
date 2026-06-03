# Architecture

System architecture for **MY School ERP** (myschools.pk) — a multi-tier school franchise
management system built on Frappe.

> **Status legend** — ✅ shipped & tested · 🟡 partial · ⬜ planned

For high-level "what is this and who uses it" see [overview.md](overview.md).
For doctype-level field reference see [data-model.md](data-model.md).

---

## 1. Stack

| Layer | Choice | Why |
|---|---|---|
| Framework | Frappe v15 (Python 3.12) | Mature low-code metadata-driven ERP, MIT-licensed |
| Database | MariaDB 10.6+ | Frappe's primary supported DB |
| Cache / queue | Redis 7 | Frappe's default |
| Front-end | Frappe Desk (built-in) + Education SPA | No custom front-end yet |
| Base apps | `frappe`, `erpnext`, `education` | Education has ERPNext as a hard dep |
| Custom app | `myschools` (this repo) | All customisations live here; upstream apps stay clean for `bench update` |

**Optional later:** `hrms` (richer payroll), `lms` (digital learning), `payments` (Pakistani gateways).

---

## 2. Hierarchy

```
Head Office (Company, is_group=1)
   ├── Cluster Company (Northern Punjab, Central Punjab, Sindh, ...)
   │     │ ← ERPNext Company; each cluster gets its own books
   │     │
   │     └── MYS Cluster (cluster_code, region, director, monitor, audit officer)
   │           └── MYS Branch (branch_code, city, principal, accountant, admin)
   │                 │ ← linked to its cluster Company for financial isolation
   │                 │
   │                 └── MYS Campus (Junior / Kids / Senior)
   │                       └── Student / Teacher / Admin staff
   │                             └── Guardian (read-only via portal)
   │
   └── (Other clusters …)
```

**Two parallel hierarchies, intentional:**

- **ERPNext Company tree** — for accounting consolidation. Head Office is a group company; each
  cluster is a sub-company under HO. Royalty invoices post to the cluster company's books.
- **MYS Cluster / Branch / Campus tree** — for operational scoping. A user assigned to a branch
  sees data only for that branch; a Cluster Director sees their whole cluster.

The MYS Branch doctype carries a `company` Link that bridges the two.

---

## 3. Modules shipped so far

For phase-by-phase status with delivering PRs and commits, see [roadmap.md](roadmap.md).
This table is the architectural view — module by module, what it ships:

| Module | Status | DocTypes / fixtures | Notes |
|---|---|---|---|
| Franchise hierarchy | ✅ | `MYS Cluster`, `MYS Branch`, `MYS Campus`, `MYS Department` | [data-model](data-model.md#1-franchise-hierarchy) |
| Royalty | ✅ | `MYS Franchise Owner`, `MYS Franchise Agreement`, `MYS Royalty Rate Override`, `MYS Royalty Invoice` (+ `Campus Line` child), `MYS Royalty Payment` | [process](processes/royalty-billing.md) · [API](api/royalty.md) |
| Inspection workflow | ✅ | `MYS Inspection Checklist Template` (+ `Item` child), `MYS Inspection Visit` (+ `Result` child), `MYS Inspection Finding`, `MYS Corrective Action` | [process](processes/inspection-workflow.md) · [API](api/inspection.md) |
| Communication | ✅ | `MYS Communication Log`; 6 `Email Template` + 6 `Notification` fixtures; `Communication.after_insert` mirror; provider-agnostic `send_sms` stub | Royalty + inspection + agreement alerts wired; system emails mirrored into the audit log. SMS gateway swap is Phase 8. [process](processes/notifications.md) |
| Permissions | ✅ | (no doctypes — pure Python in `api/permissions.py`) | Branch / cluster scoping via `permission_query_conditions` |
| SIS (Student Info System) | ✅ | upstream `education.Student` extended with `mys_cluster`/`mys_branch`/`mys_campus` custom fields | Seeded end-to-end via `scripts/seed_education.py` |
| Fees | 🟡 | upstream `education.Fees` + `Fee Structure`; Phase **8a**: `MYS Fee Structure Override`, `MYS Late Fee Policy`, [`api/fees.py`](../frappe-bench/apps/myschools/myschools/api/fees.py) | **Canonical billing object** — not Fee Schedule → Sales Invoice ([billing-model](processes/billing-model.md)). Submitted `Fees` → royalty, dashboard, portals, late-fee job. Overrides API-only until **8a-3**; bulk path **8a-4**. |
| Central Monitoring Dashboard | ✅ | `Dashboard` + 8 `Number Card` + 3 `Dashboard Chart` shipped as JSON under `my_school_erp/` | Single role-aware dashboard — same view for every role, rows filtered through `permission_query_conditions`. Custom-method cards in [`api/dashboard.py`](../frappe-bench/apps/myschools/myschools/api/dashboard.py) |
| Navigation shell (Phases 1+2) | ✅ | 5 `Workspace`, 5 `Module Profile`, `Letter Head` `MYS Default`; brand CSS + assets; `app_logo_url` / `brand_html` / `role_home_page` hooks | All 10 franchise roles land on a tier-specific workspace with a trimmed sidebar. [process](processes/navigation-and-roles.md) · §9 below |
| Print Formats (Phase 3) | ✅ | 4 branded Jinja Print Formats: `MYS Royalty Invoice`, `MYS Inspection Report`, `MYS Fee Receipt`, `MYS Franchise Agreement`; Property Setters mark each as default | All inherit `MYS Default` Letter Head. [process](processes/print-formats.md) |
| Workflows + list polish (Phase 5) | ✅ | `Workflow` + `Workflow State`/`Action` fixtures for inspection finding + royalty invoice; list-view JS settings | Role-gated transitions (e.g. Verify = Audit Officer). [process](processes/workflows.md) |
| Setup Wizard, Onboarding, Reports (Phase 6) | ✅ | `setup_wizard.js` slide + `setup_wizard_stages`; `MYS Franchise Setup` Module Onboarding; 4 Query Reports | Operator onboarding + ops reporting. |
| Portals — Guardian / Branch / Inspection (Phase 7) | ✅ | `www/` Jinja pages + `api/{guardian,branch,inspection}_portal.py`; `Guardian` website role; `/admission-enquiry` | Frappe Web Forms + `www/`, not a custom SPA. Delivered 7a–7d; merge `9b02a81` (PR #15). [process](processes/portals.md) |

Full module-to-coverage map for the original 22-module spec is in [overview.md](overview.md#scope).

---

## 4. Royalty — rate resolution

Configurable royalty rate (not fixed at 7%). Resolution order, highest priority first:

1. **Campus override** — a `MYS Royalty Rate Override` row for this (agreement, branch, campus) effective on the billing date
2. **Branch override** — a row for this (agreement, branch, campus=None)
3. **Agreement default** — `MYS Franchise Agreement.default_royalty_rate`

Implementation: [`api/royalty.py`](../frappe-bench/apps/myschools/myschools/api/royalty.py) `resolve_royalty_rate(agreement, branch, campus, on_date)`.

Each override has `effective_from` / `effective_to` / `is_active` — so rates can be scheduled
ahead of time, retired, or temporarily disabled without losing history. Past invoices are
unaffected because they store the resolved rate on each campus line at submission.

```
                  ┌──────────────────────────────┐
billing date ───→ │ campus override (matching     │ ─ found ──→ campus_override
                  │  agreement+branch+campus,     │
                  │  effective range, is_active)? │
                  └──────────┬───────────────────┘
                             │ not found
                             ↓
                  ┌──────────────────────────────┐
                  │ branch override (campus=null) │ ─ found ──→ branch_override
                  └──────────┬───────────────────┘
                             │ not found
                             ↓
                  ┌──────────────────────────────┐
                  │ agreement.default_royalty_rate│ ────────→ agreement_default
                  └──────────────────────────────┘
```

Monthly scheduled job (`0 3 1 * *` in [hooks.py](../frappe-bench/apps/myschools/myschools/hooks.py))
generates invoices for the previous month. Per-campus collection comes from
`tabFees` filtered by `student.mys_branch` and `posting_date`.

---

## 5. Inspection — workflow

Decomposed from a single submittable doc into a five-doctype workflow:

```
Checklist Template (versioned, per visit type)
   │
   │ apply_template_to_visit() snapshots items
   ↓
Inspection Visit (draft → submitted)
   │  ├── checklist_results[]  (snapshot of items + Pass/Fail/N/A + score)
   │  └── auto-computed: total_items, items_passed, items_failed, items_na,
   │                     score_percent, weighted_score
   │
   │ on submit → auto-create one Finding per failed Critical/Major item
   ↓
Inspection Finding (submittable: Open → In Progress → Resolved → Verified)
   │
   │ (one or many)
   ↓
Corrective Action (Planned → In Progress → Completed → Verified)
   │
   └─ when all corrective actions are Verified, finding auto-flips to Verified
```

Design notes:

- **Template items are snapshotted** into the visit's checklist_results — a later template
  revision doesn't rewrite historical visits.
- **Auto-findings cover Critical + Major only** — Minor failures need a manual finding from
  the inspector's summary. Critical findings get a 7-day due date; Major get 21.
- **Corrective Action is intentionally not submittable** — the workflow needs status edits
  (Planned → In Progress → Completed → Verified) that a submittable lifecycle would block.

Implementation: [`api/inspection.py`](../frappe-bench/apps/myschools/myschools/api/inspection.py).

---

## 6. Permissions (branch/cluster scoping)

Frappe's `permission_query_conditions` hook is used to scope list/report queries per role tier:

| Tier | Roles | Scope |
|---|---|---|
| Global | System Manager, Administrator, Chief Executive, HO Dept Head | All branches |
| Cluster | Cluster Director, Academic Monitor, Audit Officer | Branches in the user's cluster |
| Branch | Branch Director, Branch Principal, Branch Admin, Branch Accountant, Campus Incharge | The user's branch only |
| None | Other | `branch = '__none__'` (returns no rows) |

The user's branch is resolved via `Employee.mys_branch`. Cluster is derived by joining up
through `MYS Branch.cluster`.

Implementation:

- [`api/permissions.py`](../frappe-bench/apps/myschools/myschools/api/permissions.py) — `_user_scope()` and per-doctype query functions for branches, campuses, students, inspection visits.
- [`api/royalty.py`](../frappe-bench/apps/myschools/myschools/api/royalty.py) — query functions for the four royalty doctypes.
- [`api/inspection.py`](../frappe-bench/apps/myschools/myschools/api/inspection.py) — query functions for findings and corrective actions.
- All are wired in [`hooks.py`](../frappe-bench/apps/myschools/myschools/hooks.py) under `permission_query_conditions`.

---

## 7. ID generation

`before_insert` hooks set unique IDs on Student / Employee:

- Student: `MYS-{cluster_code}-{branch_code}-STU{######}`
- Employee: `MYS-{branch_code}-{role_code}{####}`

Implementation: [`api/identity.py`](../frappe-bench/apps/myschools/myschools/api/identity.py).

---

## 8. Custom fields on upstream doctypes

Applied as `Custom Field` records (exported as fixtures, filter `name like '%-mys_%'`):

- **Student**: `mys_cluster`, `mys_branch` (fetch from cluster), `mys_campus`, `mys_student_id`
- **Employee**: `mys_branch`, `mys_campus`, `mys_role_tier` (HO / Cluster / Branch / Campus), `mys_staff_id`
- **Guardian**: `mys_branch` (so parent portal only shows their branch)

---

## 9. Navigation shell (branding, workspaces, roles)

The app ships a **role-aware ERP shell** so each franchise operator logs in to
a workspace built for their tier rather than vanilla ERPNext's full sidebar.

- **Brand** — `app_logo_url`, `brand_html`, `website_context` (favicon, splash),
  and `app_include_css` are set in [`hooks.py`](../frappe-bench/apps/myschools/myschools/hooks.py).
  Assets live under [`myschools/public/images/`](../frappe-bench/apps/myschools/myschools/public/images/)
  (placeholder SVGs — swap for final artwork in a 1-file change) and CSS tokens
  in [`myschools/public/css/myschools.css`](../frappe-bench/apps/myschools/myschools/public/css/myschools.css).
- **Workspaces (5)** — JSON fixtures under
  [`myschools/my_school_erp/workspace/<slug>/<slug>.json`](../frappe-bench/apps/myschools/myschools/my_school_erp/workspace/).
  Each carries `restrict_to_role` and ships shortcuts and embedded charts for
  its tier: `mys-head-office`, `mys-cluster`, `mys-branch`, `mys-campus`,
  `mys-inspection`.
- **Role landing** — `role_home_page` in `hooks.py` maps all 10 franchise roles
  to a workspace, so login goes straight there instead of `/app/home`.
- **Sidebar scoping** — 5 Module Profile fixtures in
  [`myschools/fixtures/module_profile.json`](../frappe-bench/apps/myschools/myschools/fixtures/module_profile.json)
  block vanilla modules (Manufacturing, Stock, Buying, etc.) per tier. Attached
  automatically on `User.validate` via
  [`myschools.api.user_profile.attach_module_profile_to_user`](../frappe-bench/apps/myschools/myschools/api/user_profile.py)
  — highest-tier role wins. Existing Users are back-filled on `after_migrate`.
- **Letter Head** — `MYS Default` in
  [`myschools/fixtures/letter_head.json`](../frappe-bench/apps/myschools/myschools/fixtures/letter_head.json),
  inherited by the shipped Print Formats.
- **Print Formats (4)** — branded Jinja PDF layouts for `MYS Royalty Invoice`,
  `MYS Inspection Visit`, `Fees`, and `MYS Franchise Agreement`. Source of truth
  is [`myschools/scripts/build_print_formats.py`](../frappe-bench/apps/myschools/myschools/scripts/build_print_formats.py);
  generated fixture at [`myschools/fixtures/print_format.json`](../frappe-bench/apps/myschools/myschools/fixtures/print_format.json).
  Wired as each doctype's `default_print_format` via 4 Property Setters created
  in [`setup/install.py::set_default_print_formats`](../frappe-bench/apps/myschools/myschools/setup/install.py).
  Details: [processes/print-formats.md](processes/print-formats.md).

Full role-to-workspace mapping and how to add a new role live in
[processes/navigation-and-roles.md](processes/navigation-and-roles.md).

---

## 10. Scheduled jobs

| When | Job | Purpose |
|---|---|---|
| `0 3 1 * *` (3am on day 1) | `myschools.api.royalty.scheduled_monthly_royalty_run` | Generate royalty invoices for the previous month |

Registered in [`hooks.py`](../frappe-bench/apps/myschools/myschools/hooks.py) under `scheduler_events.cron`.

---

## 11. Repository layout

```
.
├── docs/                                     ← this directory
├── frappe-bench/                             ← gitignored except the app below
│   └── apps/myschools/
│       └── myschools/
│           ├── api/                          ← business logic (royalty, inspection, permissions, identity)
│           ├── my_school_erp/doctype/<name>/ ← doctype definitions (json schema + py controller)
│           ├── scripts/                      ← seed_demo, demo_royalty_invoice
│           ├── tests/                        ← integration tests (run via `bench run-tests`)
│           ├── setup/install.py              ← after_install / after_migrate hooks
│           └── hooks.py                      ← Frappe wiring (events, scheduler, permissions, fixtures)
├── .github/                                  ← CI workflow, PR/issue templates, CODEOWNERS
├── CHANGELOG.md                              ← Keep-a-Changelog format
├── CONTRIBUTING.md                           ← branching, commit conventions, PR workflow
├── README.md                                 ← landing page
└── LICENSE                                   ← AGPL-3.0
```

The whole `frappe-bench/` directory is gitignored except for `apps/myschools/`, so the repo
only tracks our app and the project-level docs / config. Bench, venv, sites, logs, and
upstream apps are all reproduced from scratch on each clone.

---

## 12. Engineering practices

See [development.md](development.md) for the full picture. Summary:

- **Branching:** `main` (production, protected) ← `develop` ← `feature-*` / `fix-*`
- **Commits:** Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`)
- **Lint/format:** ruff (configured in `pyproject.toml`, runs in pre-commit + CI)
- **Tests:** `bench --site myschools.localhost run-tests --app myschools` — 16 integration tests at time of writing
- **CI:** GitHub Actions (`.github/workflows/ci.yml`) — lint job + Frappe test suite with MariaDB + Redis services
