# Setup & onboarding

*Audience: anyone installing MY School ERP for the first time, plus
developers extending the wizard / onboarding card / reports.*

This doc covers everything an operator sees in the first hour of an
install: the Setup Wizard slide, the Module Onboarding card on the
desk, and the four Query Reports that Phase 6 shipped.

---

## The first-time install journey

A fresh `bench install-app myschools` on a brand-new site flows like
this:

```
                          ┌──────────────────────────────────────┐
1. ERPNext core wizard    │  Language / Country / Currency       │
                          │  Company / User / Region             │
                          └────────────────┬─────────────────────┘
                                           │
                          ┌────────────────▼─────────────────────┐
2. MYS slide (new)        │  Optional: Cluster + Branch + Campus │
   public/js/setup_wizard │  seed values. Skip = continue blank. │
                          └────────────────┬─────────────────────┘
                                           │
                          ┌────────────────▼─────────────────────┐
3. ERPNext stages         │  Chart of Accounts, defaults, etc.   │
                          └────────────────┬─────────────────────┘
                                           │
                          ┌────────────────▼─────────────────────┐
4. MYS stage (new)        │  create_first_franchise_tree(args)   │
   scripts/setup_wizard   │  - cluster (if code+name supplied)   │
                          │  - branch  (if code+name AND cluster)│
                          │  - campus  (if type AND branch)      │
                          └────────────────┬─────────────────────┘
                                           │
                          ┌────────────────▼─────────────────────┐
5. Land on desk           │  /app  →  redirect to role workspace │
                          │  (e.g. CEO lands on mys-head-office) │
                          └────────────────┬─────────────────────┘
                                           │
                          ┌────────────────▼─────────────────────┐
6. Onboarding card        │  MYS Franchise Setup — 6 guided      │
                          │  steps: Cluster, Branch, Campus,     │
                          │  Agreement, Inspection, Dashboard.   │
                          └──────────────────────────────────────┘
```

Steps 2 and 4 are the same data — collected once in the slide, used
once in the stage. Step 6 is what an operator who *skipped* the wizard
sees on their first login (or what anyone sees on subsequent logins,
until they tick through every step).

---

## The Setup Wizard slide

**File:** [public/js/setup_wizard.js](../../frappe-bench/apps/myschools/myschools/public/js/setup_wizard.js)
**Registered by:** `setup_wizard_requires` in [hooks.py](../../frappe-bench/apps/myschools/myschools/hooks.py)

One slide, named `mys_franchise`, ordered *after* ERPNext's stock
slides. Operators land on it after Region. Every field is optional —
an entirely blank slide is a valid submit.

| Field | Required? | What it does |
|---|---|---|
| `mys_cluster_code` | only if any cluster field is filled | Creates `MYS Cluster` with this primary key |
| `mys_cluster_name` | only if any cluster field is filled | Display name for the Cluster |
| `mys_cluster_region` | optional | Free-text region descriptor |
| `mys_branch_code` | only if any branch field is filled, AND cluster fields are filled | Primary key for the new `MYS Branch` |
| `mys_branch_name` | only if any branch field is filled | Display name |
| `mys_campus_type` | only if branch fields are filled | One of `Kids`, `Junior`, `Senior` — creates `MYS Campus` under the new Branch |

**JS-side validation** (front-end only — catches partial input early):

- If any one of `mys_branch_code` / `mys_branch_name` is filled, both must be.
- Same paired check for `mys_cluster_code` / `mys_cluster_name`.
- If `mys_branch_code` is filled, `mys_cluster_code` must also be (a Branch needs a Cluster).
- If `mys_campus_type` is set, `mys_branch_code` must be set (a Campus needs a Branch).

Server-side, the same constraints are enforced by *silently dropping*
incomplete rows — the slide could in principle be bypassed, the data
contract holds.

---

## The Python stage

**File:** [scripts/setup_wizard.py](../../frappe-bench/apps/myschools/myschools/scripts/setup_wizard.py)
**Registered by:** `setup_wizard_stages` in [hooks.py](../../frappe-bench/apps/myschools/myschools/hooks.py)

`get_setup_stages(args)` returns one stage with one task —
`create_first_franchise_tree`. The task:

1. Calls `_maybe_create_cluster(args)` — returns the cluster code (or
   `None` if `mys_cluster_code` / `mys_cluster_name` were not both
   supplied).
2. Calls `_maybe_create_branch(args, cluster_code=...)` — needs the
   cluster code to link to, the branch code/name, and reads the first
   Company on the site to populate `MYS Branch.company`.
3. Calls `_maybe_create_campus(args, branch_code=...)` — needs the
   branch code to link to, and the campus type. The campus name is
   computed as `{branch_code}-{campus_type}` (matches the doctype's
   `autoname: format:{branch}-{campus_type}`).
4. Commits.

**Idempotent re-runs.** Each helper first checks `frappe.db.exists()`
and returns the existing code instead of inserting. The same args can
be POSTed twice — or the headless `ci_bootstrap.run()` can wire the
same Cluster/Branch on every CI boot — without error.

---

## Headless installs and the `is_setup_complete` trap

The wizard flag matters even when no human runs the wizard.

When the headless CI bootstrap (`scripts/ci_bootstrap.run`) calls
`erpnext.setup.setup_wizard.setup_complete()`, ERPNext creates the
Company, Chart of Accounts and other artefacts — but **does not** flip
the wizard-completion flags. Specifically:

- `Installed Application.is_setup_complete` stays 0 for both `frappe` and `erpnext`.
- `System Settings.setup_complete` stays 0.

Without those flags, the next login redirects every user (including
the Administrator) to `/app/setup-wizard`, which fails the role
permission check on Page "Setup Wizard" and shows a blocking error.
This was caught in CI as four red Playwright e2e tests in Phase 5.

The fix lives in [scripts/ci_bootstrap.py](../../frappe-bench/apps/myschools/myschools/scripts/ci_bootstrap.py): after `setup_complete()` (and on the idempotent early-return path when a Company already exists), the script explicitly sets `Installed Application.is_setup_complete = 1` for both apps and calls Frappe's own `disable_future_access()`. This is the only documented way to honour the wizard contract without actually running the wizard's JS.

---

## The Module Onboarding card

**Fixture:** [my_school_erp/module_onboarding/mys_franchise_setup/](../../frappe-bench/apps/myschools/myschools/my_school_erp/module_onboarding/mys_franchise_setup/)
**Steps:** [my_school_erp/onboarding_step/](../../frappe-bench/apps/myschools/myschools/my_school_erp/onboarding_step/)

Frappe surfaces a Module Onboarding card on every workspace whose
`module` matches the onboarding's `module`. All five MYS workspaces
share `module: MY School ERP`, so the same `MYS Franchise Setup` card
shows on each of them — until the logged-in user has ticked every
step.

### The six steps

| # | Title | Action | Reference |
|---|---|---|---|
| 1 | Add Your First Cluster | Create Entry | `MYS Cluster` |
| 2 | Add Your First Branch | Create Entry | `MYS Branch` |
| 3 | Add Your First Campus | Create Entry | `MYS Campus` |
| 4 | Sign Your First Franchise Agreement | Create Entry | `MYS Franchise Agreement` |
| 5 | Book Your First Inspection Visit | Create Entry | `MYS Inspection Visit` |
| 6 | View the Central Monitoring Dashboard | Go to Page | `dashboard-view/MYS Central Monitoring` |

### Who sees the card

Six operator-facing roles: Chief Executive, HO Dept Head, Cluster
Director, Branch Director, Branch Principal, Branch Admin. The two
inspection-only roles (Academic Monitor, Audit Officer) do not see
this card because they don't run the franchise-tree setup.

### Adding a new step

1. Create a new directory under [my_school_erp/onboarding_step/](../../frappe-bench/apps/myschools/myschools/my_school_erp/onboarding_step/) and drop a `<slug>/<slug>.json` matching the existing schema.
2. Append `{"step": "<Onboarding Step name>"}` to the `steps` array in `module_onboarding/mys_franchise_setup/mys_franchise_setup.json`.
3. `bench --site myschools.localhost migrate` to import. The `is_standard=Yes` filter in `hooks.py` is *not* on Onboarding Step — instead it's filtered by name prefix `MYS %`, so make sure your new step's `name` starts with `MYS `.
4. Add an assertion in [tests/test_onboarding.py](../../frappe-bench/apps/myschools/myschools/tests/test_onboarding.py) — `EXPECTED_STEPS` is the source of truth for the test.

### Why one card, not five

The original Phase 6 plan called for "Module Onboarding tours per
workspace (HO, Cluster, Branch, Campus, Inspection)." Frappe's
primitive is **per module, not per workspace** — a Module Onboarding
links to a `Module Def`, and all five MYS workspaces hang off the
single `MY School ERP` Module Def. We could have created five
identically-targeted Module Onboarding documents, but the rendering
behaviour with multiple cards for the same module is undefined.
Instead we ship one card that covers the full operator journey, since
every role lands on a workspace where the card is relevant.

---

## The four Query Reports

All four live under [my_school_erp/report/](../../frappe-bench/apps/myschools/myschools/my_school_erp/report/) and follow the standard Frappe Script Report convention: a `<slug>.json` declaring the Report doctype, a `<slug>.py` exporting `execute(filters=None) -> (columns, rows)`, and an `__init__.py`.

### 1. MYS Royalty Aging

| | |
|---|---|
| **Source** | `MYS Royalty Invoice` rows with status in `(Unpaid, Partial, Overdue)` |
| **Filter** | `as_on` (default = today), optional `branch`, optional `cluster` |
| **Columns** | Branch, Cluster, Outstanding, 0-30, 31-60, 61-90, 90+, Oldest Due Date, # Open Invoices |
| **Aggregation** | Per branch — invariant: `outstanding == b_0_30 + b_31_60 + b_61_90 + b_over_90` (regression-tested) |
| **Roles** | Chief Executive, HO Dept Head, Cluster Director, Branch Director, Branch Accountant |

### 2. MYS Fee Collection by Branch

| | |
|---|---|
| **Source** | Submitted (`docstatus=1`) `Fees` joined via `Student.mys_branch` |
| **Filter** | `from_date` (default = jan 1 of current year), `to_date` (default = today), optional branch/cluster |
| **Columns** | Branch, Cluster, # Fee Invoices, Billed, Paid, Outstanding, Collection % |
| **Computed columns** | `paid = grand_total - outstanding_amount` (Fees has no `paid_amount` column); `collection_rate = paid/billed * 100` |
| **Roles** | Chief Executive, HO Dept Head, Cluster Director, Branch Director, Branch Accountant |

### 3. MYS Findings by Branch and Severity

| | |
|---|---|
| **Source** | `MYS Inspection Finding` |
| **Filter** | `status` (default = `(Open, In Progress)`), optional branch |
| **Columns** | Branch, Critical, Major, Minor, Total |
| **Pivot** | Branch on rows × severity on columns; invariant: `total == critical + major + minor` (regression-tested) |
| **Roles** | Chief Executive, HO Dept Head, Cluster Director, Branch Director, Academic Monitor, Audit Officer |

### 4. MYS Branch Health Scorecard

| | |
|---|---|
| **Source** | `MYS Branch` (active only), joined to 4 child queries |
| **Filter** | Optional branch / cluster |
| **Columns** | Branch, Cluster, Active Campuses, Active Students, Open Findings, Outstanding Royalty, Last Inspection |
| **Roles** | Chief Executive, HO Dept Head, Cluster Director, Branch Director |

### Branch scoping is free

None of the four reports re-implement permission logic. Each goes
through `frappe.db.get_all` against doctypes that already have
`permission_query_conditions` registered (see [hooks.py](../../frappe-bench/apps/myschools/myschools/hooks.py)). A Cluster Director running the
Royalty Aging report sees only branches under her cluster; a Branch
Director sees only his branch.

### Adding a new report

1. `mkdir my_school_erp/report/<slug>/`
2. Drop a `<slug>.json` (`is_standard: Yes`, `report_type: Script Report`, `ref_doctype: <real DocType>`, `roles: [...]`, `module: MY School ERP`).
3. Add `<slug>.py` exporting `def execute(filters=None) -> (list[dict], list[dict])`.
4. Add `__init__.py` (empty).
5. The `hooks.py` fixture filter `{"dt": "Report", "filters": [["name", "like", "MYS %"], ["is_standard", "=", "Yes"]]}` picks it up automatically — no extra registration.
6. Add an entry to `REPORTS` in [tests/test_reports.py](../../frappe-bench/apps/myschools/myschools/tests/test_reports.py) for fixture-import and shape coverage.

---

## Tests

| Module | Tests | Covers |
|---|---|---|
| [tests/test_setup_wizard.py](../../frappe-bench/apps/myschools/myschools/tests/test_setup_wizard.py) | 7 | Hook registration, full-args creation, empty-args no-op, partial-args dropping, idempotent re-runs, campus-without-branch skip |
| [tests/test_onboarding.py](../../frappe-bench/apps/myschools/myschools/tests/test_onboarding.py) | 6 | Fixture import, module link, step ordering, doctype references, dashboard path, role allow-list |
| [tests/test_reports.py](../../frappe-bench/apps/myschools/myschools/tests/test_reports.py) | 5 | Fixture import + report_type=Script Report, execute()-shape, royalty bucket math invariant, fee collection % bounds, findings pivot total invariant |

Full app suite is **92 / 92 passing** as of the Phase 6 merge.
