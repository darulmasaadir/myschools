# MY School ERP — Customisation Roadmap

**Last updated:** 2026-06-03
**Up next:** Phase 8a merge → 8b student lifecycle

This doc is the **single source of truth** for what's been built, what's in flight, and what's planned. If you're scoping new work, start here. If the truth on disk diverges from this doc, the doc is wrong — fix it in the same PR that lands the change.

## Status legend

| Symbol | Meaning |
|---|---|
| ✅ | Shipped — code merged to `develop`, tests + CI green, end-to-end verified |
| 🟡 | In flight — branch open, PR not yet merged |
| ⬜ | Planned — scoped, not started |

## Standing constraints

These bind every phase:

- **Upgrade-safe only.** No custom SPA, no core forks, no monkey-patching. All customisations live inside the `myschools` app and survive `bench update`. Phase 7 portals are Frappe Web Forms + `www/` Jinja templates, never a parallel Vue/React codebase.
- **Test-first.** Every PR ships unit tests + CI green; full verification battery (HTTP smoke, fresh-install smoke, browser visual check, PDF round-trip if applicable) before "ready to merge."
- **Conventional commits.** Branch off `develop`, merge via PR, no force-push to `main`.

## Phase status at a glance

| Phase | Title | Status | Delivered |
|---|---|---|---|
| 0 | Foundations: hierarchy, royalty, inspection, dashboard | ✅ | Multiple merges into `develop` (pre-roadmap) |
| 1 | Branding | ✅ | PR [#3](https://github.com/darulmasaadir/myschools/pull/3) (`9ad4351`) |
| 2 | Workspaces + role landing | ✅ | PR [#3](https://github.com/darulmasaadir/myschools/pull/3) (`9ad4351`) |
| 3 | Print Formats | ✅ | PR [#4](https://github.com/darulmasaadir/myschools/pull/4) (`d952960`) + hotfix PR [#5](https://github.com/darulmasaadir/myschools/pull/5) (`c1b22b7`) |
| 4 | Notifications & Communication wiring | ✅ | PR [#7](https://github.com/darulmasaadir/myschools/pull/7) (`ff4dc38`) |
| 5 | Workflows & List View polish | ✅ | PR #8 (`feature/workflows`) |
| 6 | Setup Wizard, Module Onboarding, Reports | ✅ | PR #9 (`feature/setup-wizard-and-reports`) |
| 7 | Portals — Guardian / Branch / Inspection (Web Forms + `www/`) | ✅ | 7a PR #12 · 7b PR #13 · 7c PR #14 (`e4432df`) · 7d PR [#15](https://github.com/darulmasaadir/myschools/pull/15) (`9b02a81`) |
| 8 | Domain extensions | 🟡 | 8a in flight · 8b–8e ⬜ |

---

## Phase 0 — Foundations ✅

Delivered before the customisation roadmap was formally tracked.

Shipped:
- Franchise hierarchy: `MYS Cluster` / `MYS Branch` / `MYS Campus` / `MYS Department` doctypes
- Royalty engine: rate resolution (campus → branch → agreement default), monthly cron, `MYS Royalty Invoice` + child `Campus Line`, `MYS Royalty Payment`
- Inspection workflow: 5 doctypes (`MYS Inspection Checklist Template`, `MYS Inspection Visit`, `MYS Inspection Finding`, `MYS Corrective Action`, + child tables)
- Branch-scoped permissions across every custom doctype
- Auto-generated MYS student / staff IDs tied to the franchise tree
- Central Monitoring Dashboard: 8 number cards + 3 charts, role-aware via `permission_query_conditions`
- Test suite covering royalty, inspection, dashboard, fees → royalty roll-up

**Files:** [doctype/](../frappe-bench/apps/myschools/myschools/my_school_erp/doctype/), [api/](../frappe-bench/apps/myschools/myschools/api/), [tests/](../frappe-bench/apps/myschools/myschools/tests/)

---

## Phase 1 — Branding ✅

**Delivered:** PR [#3](https://github.com/darulmasaadir/myschools/pull/3) (commit `9ad4351`), `feature/navigation-shell`

What shipped:
- Brand assets: SVG logo, favicon, splash
- Brand CSS (token-based): `--mys-primary`, `--mys-primary-dark`, `--mys-primary-light`, `--mys-accent`, `--mys-text`, `--mys-text-muted`
- `app_logo_url`, `brand_html`, `website_context`, `app_include_css`, `web_include_css` hooks in `hooks.py`
- Letter Head fixture `MYS Default` — every Print Format shipped in Phase 3 inherits it

**Files:** [public/images/](../frappe-bench/apps/myschools/myschools/public/images/), [public/css/myschools.css](../frappe-bench/apps/myschools/myschools/public/css/myschools.css), [hooks.py](../frappe-bench/apps/myschools/myschools/hooks.py), [fixtures/letter_head.json](../frappe-bench/apps/myschools/myschools/fixtures/letter_head.json)

**Optional follow-up:**
- `docs/design-tokens.md` — formal palette / font / radius / shadow scales. The CSS ships 6 colour tokens; no documented scales yet.

---

## Phase 2 — Workspaces + Role Landing ✅

**Delivered:** PR [#3](https://github.com/darulmasaadir/myschools/pull/3) (commit `9ad4351`)

What shipped:
- 5 Workspace fixtures (`mys-head-office`, `mys-cluster`, `mys-branch`, `mys-campus`, `mys-inspection`) with `restrict_to_role`
- 5 Module Profile fixtures (`MYS HO`, `MYS Cluster`, `MYS Branch`, `MYS Campus`, `MYS Inspection`) — each trims the sidebar to the modules that tier needs
- `role_home_page` mapping all 10 franchise roles → their workspace
- Auto-attach via `User.validate` doc_event: when a user gets a franchise role, the matching Module Profile + `default_workspace` are wired automatically
- Tier resolver in [`api/user_profile.py`](../frappe-bench/apps/myschools/myschools/api/user_profile.py) (`resolve_profile_for_roles`, `resolve_workspace_for_roles`) — picks the highest tier when a user holds multiple roles
- 6 test classes in [`tests/test_shell.py`](../frappe-bench/apps/myschools/myschools/tests/test_shell.py)

**Files:** [workspace/](../frappe-bench/apps/myschools/myschools/my_school_erp/workspace/), [fixtures/module_profile.json](../frappe-bench/apps/myschools/myschools/fixtures/module_profile.json), [api/user_profile.py](../frappe-bench/apps/myschools/myschools/api/user_profile.py), [tests/test_shell.py](../frappe-bench/apps/myschools/myschools/tests/test_shell.py), [processes/navigation-and-roles.md](processes/navigation-and-roles.md)

---

## Phase 3 — Print Formats ✅

**Delivered:** PR [#4](https://github.com/darulmasaadir/myschools/pull/4) (commit `d952960`) + hotfix PR [#5](https://github.com/darulmasaadir/myschools/pull/5) (commit `c1b22b7`)

What shipped:
- 4 branded Jinja Print Formats:
  - `MYS Royalty Invoice`
  - `MYS Inspection Report`
  - `MYS Fee Receipt`
  - `MYS Franchise Agreement`
- Each wired as the default Print Format for its doctype via Property Setters
- All inherit `MYS Default` Letter Head from Phase 1
- `after_sync` hook ensures Property Setters fire AFTER fixture import on fresh installs (vs. `after_install` which runs too early)
- HTTP smoke + PDF round-trip verified end-to-end

**Files:** [print_format/](../frappe-bench/apps/myschools/myschools/my_school_erp/print_format/), [scripts/build_print_formats.py](../frappe-bench/apps/myschools/myschools/scripts/build_print_formats.py), [fixtures/print_format.json](../frappe-bench/apps/myschools/myschools/fixtures/print_format.json), [tests/test_print_formats.py](../frappe-bench/apps/myschools/myschools/tests/test_print_formats.py), [processes/print-formats.md](processes/print-formats.md)

---

## Phase 4 — Notifications & Communication wiring ✅

**Status:** Shipped in PR [#7](https://github.com/darulmasaadir/myschools/pull/7), merge commit `ff4dc38` (squash).
**Size:** M (matched estimate — ~10 h including the bug-fix follow-up).

Shipped:
- 6 `Email Template` fixtures + 6 `Notification` fixtures generated from a single source-of-truth builder ([`scripts/build_notifications.py`](../frappe-bench/apps/myschools/myschools/scripts/build_notifications.py)):
  royalty invoice generated, royalty invoice overdue (Days After due_date),
  inspection finding assigned, finding overdue, corrective action overdue,
  franchise agreement expiring (Days Before end_date, 30 days).
- `Communication.after_insert` mirror ([`api/notifications.log_outbound_email`](../frappe-bench/apps/myschools/myschools/api/notifications.py)) — every outbound system email tied to an MYS doctype (or `Fees`) is mirrored into `MYS Communication Log` with branch / campus / scope auto-resolved. Accepts both `Communication` and `Automated Message` types (the latter is what Notifications produce).
- Provider-agnostic `send_sms()` stub ([`api/notifications.send_sms`](../frappe-bench/apps/myschools/myschools/api/notifications.py)) — writes a `Sent` row to `MYS Communication Log` today; Phase 8 swaps in Jazz / Easypaisa / Twilio behind the same signature.
- 17 unit tests in [`tests/test_notifications.py`](../frappe-bench/apps/myschools/myschools/tests/test_notifications.py) across 5 classes — fixture coverage, Jinja render against real docs (would have caught the 3 field typos found pre-merge), SMS stub, log helper, and the `log_outbound_email` mirror filter regression coverage.
- Verification battery: 64/64 unit tests · pre-commit clean · 48/48 HTTP smoke · fresh-install smoke (drop-site → install-app → migrate) · live end-to-end Notification fire smoke (Communication → MYS Communication Log).

**Files:** [scripts/build_notifications.py](../frappe-bench/apps/myschools/myschools/scripts/build_notifications.py), [api/notifications.py](../frappe-bench/apps/myschools/myschools/api/notifications.py), [fixtures/email_template.json](../frappe-bench/apps/myschools/myschools/fixtures/email_template.json), [fixtures/notification.json](../frappe-bench/apps/myschools/myschools/fixtures/notification.json), [tests/test_notifications.py](../frappe-bench/apps/myschools/myschools/tests/test_notifications.py), [processes/notifications.md](processes/notifications.md)

---

## Phase 5 — Workflows & List View polish ✅

**Delivered:** PR #8, `feature/workflows`.

Shipped:
- Formal Frappe Workflows attached to the two doctypes with a `status` field:
  - **`MYS Inspection Finding Workflow`** — Draft → Open → In Progress → Resolved → Verified, plus Cancelled. Role-gated transitions: Submit by Audit Officer / Branch Director / Branch Principal; Acknowledge by Branch Director / Branch Principal; Mark Resolved by Branch Director / Branch Principal; Verify and Reject Resolution by Audit Officer only.
  - **`MYS Royalty Invoice Workflow`** — Draft → Unpaid (submit by HO Dept Head or Branch Accountant); payment-driven states (Partial / Paid / Overdue) reached only via `db.set_value` from the controller's `_refresh_status`, which bypasses workflow validation as required. Cancel gated to Chief Executive / HO Dept Head.
- Source-of-truth Python script [`scripts/build_workflows.py`](../frappe-bench/apps/myschools/myschools/scripts/build_workflows.py) emits the three fixture files (`workflow.json`, `workflow_state.json`, `workflow_action_master.json`) so edits never touch hand-written JSON.
- `status` and `resolution_notes` fields on `MYS Inspection Finding` marked `allow_on_submit: 1` so workflow transitions can update them post-submit; controller's `_validate_resolution_state` wired into both `validate` and `before_update_after_submit` so the "Verified requires resolution_notes" guard still fires after submission.
- `api/inspection.py` auto-creation drives new Findings through `apply_workflow("Submit")` so they land at Open with `docstatus=1` instead of being directly submitted.
- List-view JS (`<doctype>_list.js`) for severity colour badges (Finding) and status indicators (Finding, Royalty Invoice, Visit).
- Form-JS primary actions: "Send Reminder" on overdue Royalty Invoice (calls new `api.royalty.send_overdue_reminder`); "Create Corrective Action" shortcut on Open / In Progress Findings.
- Tests: [`tests/test_workflows.py`](../frappe-bench/apps/myschools/myschools/tests/test_workflows.py) covers fixture import, finding state machine, role gates, and the Royalty `db_set` bypass. Existing `test_inspection.py::test_finding_cannot_be_verified_without_resolution_notes` updated to use `db.set_value` to seed Resolved state (bypassing the workflow's transition rules) so it exercises only the controller guard. 74/74 passing.
- Process doc: [`docs/processes/workflows.md`](processes/workflows.md).

Deferred to a small follow-up:
- `MYS Inspection Visit` workflow — the doctype currently has no `status` field (only `visit_type` + `is_submittable: 1`). Adding the field + workflow is a separate small PR rather than bloating this one.

---

## Phase 6 — Setup Wizard, Module Onboarding, Reports ✅

**Delivered:** PR #9, `feature/setup-wizard-and-reports`

Three independent slices, each landed as its own commit on the branch:

**Slice 1 — Setup Wizard slide + stage** (`16ba09d`)

- New JS slide [`public/js/setup_wizard.js`](../frappe-bench/apps/myschools/myschools/public/js/setup_wizard.js) registered via the `setup_wizard_requires` hook, runs *after* ERPNext's stock slides. Optional fields for first Cluster (code/name/region), first Branch (code/name) and first Campus (type).
- New Python stage [`scripts/setup_wizard.py`](../frappe-bench/apps/myschools/myschools/scripts/setup_wizard.py) registered via the `setup_wizard_stages` hook. Three idempotent helpers (`_maybe_create_cluster`, `_maybe_create_branch`, `_maybe_create_campus`) that silently drop incomplete rows.
- Every field optional — operators who skip the slide get a vanilla install plus our app, and create records through the normal forms later.

**Slice 2 — Module Onboarding card** (`0d76dc4`)

- One [`Module Onboarding` fixture](../frappe-bench/apps/myschools/myschools/my_school_erp/module_onboarding/mys_franchise_setup/mys_franchise_setup.json) named `MYS Franchise Setup`, attached to module `MY School ERP` (so it surfaces on every MYS workspace, since all five workspaces share that module).
- Six [`Onboarding Step` fixtures](../frappe-bench/apps/myschools/myschools/my_school_erp/onboarding_step/) walking an operator through Cluster → Branch → Campus → Franchise Agreement → Inspection Visit → Central Monitoring Dashboard.
- Visible to the six operator-facing roles that actually do the setup (Chief Executive, HO Dept Head, Cluster Director, Branch Director, Branch Principal, Branch Admin).

**Slice 3 — First batch of Query Reports** (`6987be5`)

Four Script Reports under [`my_school_erp/report/`](../frappe-bench/apps/myschools/myschools/my_school_erp/report/):

| Report | `ref_doctype` | Use case |
|---|---|---|
| `MYS Royalty Aging` | MYS Royalty Invoice | Aged outstanding (0-30 / 31-60 / 61-90 / 90+) per branch |
| `MYS Fee Collection by Branch` | Fees | Billed vs. collected vs. outstanding, with collection % |
| `MYS Findings by Branch and Severity` | MYS Inspection Finding | Pivot of open findings by branch (rows) × severity (cols) |
| `MYS Branch Health Scorecard` | MYS Branch | One-row-per-branch overview: campuses, students, findings, royalty, last inspection |

All four respect existing `permission_query_conditions` — Cluster Directors see only their cluster, Branch Directors only their branch.

**Hooks wired** in [`hooks.py`](../frappe-bench/apps/myschools/myschools/hooks.py):

```python
setup_wizard_requires = "/assets/myschools/js/setup_wizard.js"
setup_wizard_stages = "myschools.scripts.setup_wizard.get_setup_stages"

# fixtures = [..., Module Onboarding (MYS %), Onboarding Step (MYS %),
#                  Report (MYS %, is_standard=Yes) ]
```

**Tests:** 18 new tests across 3 modules ([`tests/test_setup_wizard.py`](../frappe-bench/apps/myschools/myschools/tests/test_setup_wizard.py), [`tests/test_onboarding.py`](../frappe-bench/apps/myschools/myschools/tests/test_onboarding.py), [`tests/test_reports.py`](../frappe-bench/apps/myschools/myschools/tests/test_reports.py)). Full app suite: 92 / 92 passing.

---

## Phase 7 — Portals: Guardian / Branch / Inspection ✅

**Important rewrite from the original plan.** The original scoped a Vue/React SPA frontend; per the **upgrade-safe-only** standing constraint, this is now **Frappe Web Forms + `www/` Jinja templates inside the `myschools` app**. No parallel codebase, no separate auth, no separate build pipeline.

**Estimated size:** L (16–24 h), split into 7a–7d PRs.

### 7a — Portal foundations ✅

Delivered PR [#12](https://github.com/darulmasaadir/myschools/pull/12).

- `Guardian` website role + `Guardian.user` custom field + email→User linker (`api/identity.py`).
- `/portal` dispatcher + stub `/guardian`, `/branch`, `/inspection` pages with shared `mys_portal_base.html` layout.
- `role_home_page` for Guardian; read perms for Guardian role on Guardian / Student / Fees.
- Tests: `tests/test_portal_shell.py` · process doc [`processes/portals.md`](processes/portals.md).

### 7b — Guardian portal content ✅

Delivered PR [#13](https://github.com/darulmasaadir/myschools/pull/13) (`f7b5cf7`).

- `/guardian` children list, `/guardian/child`, `/guardian/fees`, `/guardian/attendance`
- Fee receipt PDF via `download_fee_receipt` whitelist + `MYS Fee Receipt` print format
- `guardian-feedback` Web Form → `MYS Communication Log`
- Tests: `tests/test_guardian_portal.py` (4 tests; full app suite 106)
- Smoke seed: `scripts/seed_portal_guardian.py`

### 7c — Branch portal ✅

Delivered PR [#14](https://github.com/darulmasaadir/myschools/pull/14) (`e4432df`).

- `/branch` dashboard with branch info + findings / royalty / fees KPIs
- `/branch/findings`, `/branch/royalty`, `/branch/fees`
- API: `api/branch_portal.py` — branch resolution via `Employee.user_id`, scoped queries
- Desk: Mobile Dashboard shortcut on `mys-branch` workspace; number-card fixes for all branch staff
- Tests: `tests/test_branch_portal.py` · `scripts/verify_branch_desk_cards.py` · `scripts/verify_http_battery.py`
- Smoke seed: `scripts/seed_portal_branch.py`
- Fresh-install: `ci_bootstrap` marks Head Office as group company so `seed_demo` works on greenfield sites

### 7d — Inspection portal ✅

**Delivered:** PR [#15](https://github.com/darulmasaadir/myschools/pull/15) (merge `9b02a81` on `develop`).

What shipped:
- `/inspection` dashboard, `/inspection/visits`, `/inspection/visits/new`, `/inspection/visit` mobile checklist runner (apply template → save → submit), cluster-scoped via `Employee.mys_branch`.
- API: [`api/inspection_portal.py`](../frappe-bench/apps/myschools/myschools/api/inspection_portal.py) — `create_visit`, `apply_template`, `save_checklist`, `submit_visit`, all whitelisted and scope-checked.
- Public `/admission-enquiry` → `MYS Communication Log` (guest POST, optional branch).
- Auto-finding on submit runs the `Submit` workflow step as Administrator so an Academic Monitor inspector isn't blocked by the Audit-Officer-gated transition.
- Tests: [`tests/test_inspection_portal.py`](../frappe-bench/apps/myschools/myschools/tests/test_inspection_portal.py) (incl. Academic-Monitor fail-Critical → Open finding regression).

**Engineering hardening shipped in the same PR** (process-debt paydown, not 7d feature scope):
- Playwright matrix [`tests/e2e/phase7d_inspection_portal.spec.ts`](../frappe-bench/apps/myschools/tests/e2e/phase7d_inspection_portal.spec.ts) — monitor happy path, fail→finding, audit access, branch-director denial, guest admission validation.
- `seed_e2e` extended with `e2e_monitor@mys.local` + a Routine checklist template.
- **CI now auto-runs the full role × surface battery** on every push: `verify_http_battery.py` (all franchise roles + guest admission POST) and `verify_branch_desk_cards.py` (branch number-card matrix), after a `seed_test_users` step.
- **Coverage ratchet** — `coverage_floor.json` (63%) enforced by `scripts/check_coverage_floor.py` in the Tests job.
- Process doc [`processes/e2e-and-flaky-tests.md`](processes/e2e-and-flaky-tests.md) — test pyramid (which layers are CI-enforced vs the shrinking manual list) + flaky-test quarantine policy.

---

## Phase 8 — Domain extensions 🟡

**Estimated size:** XL (30–50 h), split into sub-PRs 8a–8e.

### 8a — Fee overrides + late fees 🟡

**In flight:** branch `feature/phase-8a-fee-overrides-late-fees`.

- `MYS Fee Structure Override` — branch/campus + program + academic year → alternate `Fee Structure` (campus wins over branch, same precedence as royalty rates).
- `MYS Late Fee Policy` — grace days, late-fee % of outstanding, minimum amount, fee category.
- [`api/fees.py`](../frappe-bench/apps/myschools/myschools/api/fees.py) — `resolve_fee_structure`, `apply_late_fees`, daily scheduler `0 6 * * *`.
- Custom fields on `Fees`: `mys_late_fee_for`, `mys_late_fee_applied` (idempotent late-fee generation).
- Tests: [`tests/test_fees.py`](../frappe-bench/apps/myschools/myschools/tests/test_fees.py).
- **`resolve_fee_structure()` wired on `Fees.validate`** (8a-3) — defaults `fee_structure` from campus/branch override; warns if operator picks a different structure while an override is active.
- **Billing safety** (8a-2) — `Accounts` module blocked on MYS Branch/Cluster profiles; franchise roles denied create on `Fee Schedule` / `Sales Invoice` via `restrict_split_brain_billing_paths()` in install/migrate.
- **Bulk Fees** (8a-4) — `MYS Bulk Fee Run` + `generate_bulk_fees_for_run` (student group → submitted `Fees`, override resolution, duplicate skip).

### 8a follow-ups ✅ (in branch)

Decision record: [processes/billing-model.md](processes/billing-model.md). Canonical object = Education **`Fees`**.

| ID | Status | Scope |
|----|--------|--------|
| **8a-2** | ✅ in branch | Module profile + `restrict_split_brain_billing_paths()` |
| **8a-3** | ✅ in branch | `Fees` validate → `apply_resolved_fee_structure_on_fees` |
| **8a-4** | ✅ in branch | **`MYS Bulk Fee Run`** — student group + term → N submitted `Fees` via `generate_bulk_fees_for_run`; uses `resolve_fee_structure`; tests `test_bulk_fee_run.py` |

### 8b–8e (planned)

- **8b** — Student lifecycle (Enrollment, Transfer, Leaving Certificate).
- **8c** — SMS / Email provider adapters on `MYS Communication Log`.
- **8d** — HR scaffolding (Employee custom fields, payroll cycle).
- **8e** — Payment gateway stubs (JazzCash, Easypaisa, HBL).

---

## How this doc is maintained

- **Updated in the same PR that lands a phase.** Whoever ships work updates this doc as part of the same commit / PR that introduces it.
- **Status changes always cite evidence.** ✅ entries link to a PR number and merge commit short SHA. ⬜ → 🟡 transitions cite the branch name.
- **Don't trust session plans.** This doc supersedes any "roadmap" written in a Claude session, a Notion page, or a Linear ticket. If they diverge, this doc wins. The pattern of keeping a session plan in `~/.claude/plans/` and forgetting it diverged from `develop` is what motivated creating this doc in the first place.
