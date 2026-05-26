# MY School ERP — Customisation Roadmap

**Last updated:** 2026-05-26
**Up next:** Phase 5 — Workflows & List View polish

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
| 4 | Notifications & Communication wiring | 🟡 | PR pending (branch `feature/notifications`) |
| 5 | Workflows & List View polish | ⬜ | — |
| 6 | Setup Wizard, Module Onboarding, Reports | ⬜ | — |
| 7 | Portals — Guardian / Branch / Inspection (Web Forms + `www/`) | ⬜ | — |
| 8 | Domain extensions | ⬜ | — |

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

## Phase 4 — Notifications & Communication wiring 🟡

**Status:** In flight on `feature/notifications`; PR pending.
**Estimated size:** M (8–12 h) — actuals tracked when PR merges.

Shipped on the branch:
- 6 `Email Template` fixtures + 6 `Notification` fixtures generated from a single source-of-truth builder ([`scripts/build_notifications.py`](../frappe-bench/apps/myschools/myschools/scripts/build_notifications.py)):
  royalty invoice generated, royalty invoice overdue (Days After due_date),
  inspection finding assigned, finding overdue, corrective action overdue,
  franchise agreement expiring (Days Before end_date, 30 days).
- `Communication.after_insert` mirror ([`api/notifications.log_outbound_email`](../frappe-bench/apps/myschools/myschools/api/notifications.py)) — every outbound system email tied to an MYS doctype (or `Fees`) is mirrored into `MYS Communication Log` with branch / campus / scope auto-resolved.
- Provider-agnostic `send_sms()` stub ([`api/notifications.send_sms`](../frappe-bench/apps/myschools/myschools/api/notifications.py)) — writes a `Sent` row to `MYS Communication Log` today; Phase 8 swaps in Jazz / Easypaisa / Twilio behind the same signature.
- 11 unit tests in [`tests/test_notifications.py`](../frappe-bench/apps/myschools/myschools/tests/test_notifications.py) across 3 classes (fixture coverage, SMS stub, log helper).
- Verification battery: 58/58 unit tests · pre-commit clean · 48/48 HTTP smoke · live mirror smoke (Communication → Log) · live SMS-stub smoke.

**Files:** [scripts/build_notifications.py](../frappe-bench/apps/myschools/myschools/scripts/build_notifications.py), [api/notifications.py](../frappe-bench/apps/myschools/myschools/api/notifications.py), [fixtures/email_template.json](../frappe-bench/apps/myschools/myschools/fixtures/email_template.json), [fixtures/notification.json](../frappe-bench/apps/myschools/myschools/fixtures/notification.json), [tests/test_notifications.py](../frappe-bench/apps/myschools/myschools/tests/test_notifications.py), [processes/notifications.md](processes/notifications.md)

---

## Phase 5 — Workflows & List View polish ⬜

**Estimated size:** M (6–10 h)

Scope:
- Convert status enums to formal Frappe Workflows with role-gated transitions:
  - `MYS Inspection Finding` (Open → In Progress → Resolved → Verified)
  - `MYS Royalty Invoice` (Draft → Submitted → Paid / Overdue / Cancelled)
  - `MYS Inspection Visit` (Draft → Scheduled → In Progress → Completed → Submitted)
- List view JS (`<doctype>_list.js`) for severity colour badges and status indicators.
- Per-doctype form JS (`<doctype>.js`) for primary action buttons ("Generate Royalty Now", "Close Finding", "Send Reminder") — turns link-driven flows into button-driven ones inside the desk.

---

## Phase 6 — Setup Wizard, Module Onboarding, Reports ⬜

**Estimated size:** M (10–14 h)

Scope:
- Custom Setup Wizard replacing ERPNext's stages: Head Office → first Cluster → first Branch → first Campus.
- Module Onboarding tours per workspace (first-login walkthroughs).
- First batch of Query Reports:
  - Royalty aging
  - Fee collection by branch
  - Findings by branch + severity
  - Branch health scorecard

---

## Phase 7 — Portals: Guardian / Branch / Inspection ⬜

**Important rewrite from the original plan.** The original scoped a Vue/React SPA frontend; per the **upgrade-safe-only** standing constraint, this is now **Frappe Web Forms + `www/` Jinja templates inside the `myschools` app**. No parallel codebase, no separate auth, no separate build pipeline.

**Estimated size:** L (16–24 h)

Scope:
- Guardian portal — see your children, their fees, download receipts, view attendance.
- Branch portal — mobile-friendly dashboard for principals: today's findings, pending royalty, fee collection.
- Inspection portal — mobile-friendly checklist runner for auditors in the field.
- Web Forms: admission enquiry, guardian feedback.

---

## Phase 8 — Domain extensions ⬜

**Estimated size:** XL (30–50 h, split across 3–4 sub-PRs)

Scope:
- Per-branch Fee Structure overrides + late-fee automation.
- Student lifecycle doctypes (Enrollment, Transfer, Leaving Certificate).
- SMS / Email provider adapters wired to `MYS Communication Log` + Phase 4 templates.
- HR scaffolding (custom fields on Employee, payroll cycle).
- Payment gateway stubs (JazzCash, Easypaisa, HBL).

---

## How this doc is maintained

- **Updated in the same PR that lands a phase.** Whoever ships work updates this doc as part of the same commit / PR that introduces it.
- **Status changes always cite evidence.** ✅ entries link to a PR number and merge commit short SHA. ⬜ → 🟡 transitions cite the branch name.
- **Don't trust session plans.** This doc supersedes any "roadmap" written in a Claude session, a Notion page, or a Linear ticket. If they diverge, this doc wins. The pattern of keeping a session plan in `~/.claude/plans/` and forgetting it diverged from `develop` is what motivated creating this doc in the first place.
