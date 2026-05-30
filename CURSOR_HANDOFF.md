# Cursor Handoff — MY School ERP

**Generated:** 2026-05-30 — at end of a Claude Code session that landed Phase 6.
**Audience:** the next agent picking up this repo, regardless of which IDE.
**Lifespan:** delete this file once you've internalised it or after the Cursor IDE PR is in.

---

## TL;DR

- **Repo root:** `/Users/ali/projects/myschools`
- **Branch:** `develop` is up to date with `origin/develop` at `19fdbc5` (Phase 6 merge commit).
- **READ FIRST:** [`AGENTS.md`](AGENTS.md), then [`docs/roadmap.md`](docs/roadmap.md). Both are authoritative.
- **Standing rules are already wired for Cursor** via [`.cursor/rules/*.mdc`](.cursor/rules/) with `alwaysApply: true` — Cursor will load them on every agent invocation. **Do not duplicate them; trust them.**
- This handoff exists to capture the **in-flight state** that lives only in working-tree changes and recent chat — not the stable rules.

---

## 1. What just shipped — Phase 6 (PR #9)

Merged into `develop` today as `19fdbc5`. Closed out the *Setup Wizard + Module Onboarding + first Query Reports* slice of the roadmap.

### What's now in the codebase

| Surface | Files |
|---|---|
| Setup-wizard slide (JS) | [`frappe-bench/apps/myschools/myschools/public/js/setup_wizard.js`](frappe-bench/apps/myschools/myschools/public/js/setup_wizard.js) |
| Setup-wizard stage (Python) | [`frappe-bench/apps/myschools/myschools/scripts/setup_wizard.py`](frappe-bench/apps/myschools/myschools/scripts/setup_wizard.py) |
| Hook registrations | `setup_wizard_requires` + `setup_wizard_stages` in [`hooks.py`](frappe-bench/apps/myschools/myschools/hooks.py) |
| Module Onboarding card | [`my_school_erp/module_onboarding/mys_franchise_setup/`](frappe-bench/apps/myschools/myschools/my_school_erp/module_onboarding/mys_franchise_setup/) |
| Onboarding steps (6 of them) | [`my_school_erp/onboarding_step/mys_*`](frappe-bench/apps/myschools/myschools/my_school_erp/onboarding_step/) |
| Script Reports (4 of them) | [`my_school_erp/report/mys_*`](frappe-bench/apps/myschools/myschools/my_school_erp/report/) — royalty aging, fee collection by branch, findings by branch & severity, branch health scorecard |
| Unit tests | [`tests/test_setup_wizard.py`](frappe-bench/apps/myschools/myschools/tests/test_setup_wizard.py), [`tests/test_onboarding.py`](frappe-bench/apps/myschools/myschools/tests/test_onboarding.py), [`tests/test_reports.py`](frappe-bench/apps/myschools/myschools/tests/test_reports.py) — 92/92 passing |
| Browser smoke spec | [`tests/e2e/phase6_smoke.spec.ts`](frappe-bench/apps/myschools/tests/e2e/phase6_smoke.spec.ts) — 12 tests, runs against `http://myschools.localhost:8000` |
| Wizard walkthrough spec (env-gated) | [`tests/e2e/setup_wizard_walkthrough.spec.ts`](frappe-bench/apps/myschools/tests/e2e/setup_wizard_walkthrough.spec.ts) — opt-in via `MYS_WIZARD_TEST=1` |
| Process doc | [`docs/processes/setup-and-onboarding.md`](docs/processes/setup-and-onboarding.md) |
| Roadmap mark | Phase 6 ⬜ → ✅ in [`docs/roadmap.md`](docs/roadmap.md) |
| Changelog | New `[Unreleased]` entry in [`CHANGELOG.md`](CHANGELOG.md) |

### Things that bit during Phase 6 — worth knowing before touching adjacent code

- `Fees` doctype has **no `paid_amount` column**; derive `paid = grand_total - outstanding_amount`. The Fee Collection by Branch report does this.
- `Module Onboarding.success_message` is **capped at 140 chars** — Frappe raises `CharacterLengthExceededError` on import otherwise.
- ESLint's `no-undef` does **not** treat `frappe.provide("mys.setup")` as creating a global. If you need a namespace in a public JS file, either use a file-local `const` (what we did) or add the global to `.eslintrc`.
- Frappe v15 `setup_wizard_stages` is registered as a function reference (`"myschools.scripts.setup_wizard.get_setup_stages"`); the function takes `args` and returns a list of stage dicts. The matching slide JS is registered via `setup_wizard_requires` pointing at a `/assets/<app>/js/` path.
- ERPNext also registers `setup_wizard_stages`, so `frappe.get_hooks("setup_wizard_stages")` returns multiple entries — assert with `assertIn`, not `assertEqual`.
- Script reports run through `permission_query_conditions` automatically when they query via `frappe.db.get_all`. The branch-scoping hooks already in `myschools.api.permissions` do their job for free.

### Two CI fixes landed mid-verification

| Commit | Fix |
|---|---|
| `08d58e7` | Prettier line-width + ESLint `no-undef` on `setup_wizard.js` — restructured to file-local `const slides_settings`. |
| `e308d66` | Added `socket.io` to the noise filter in the new smoke spec — CI runners have no realtime worker, so the browser logs xhr poll errors that aren't real bugs. |

### Verification battery that ran before merge (per `pr-verification.mdc`)

- ✅ Unit tests local — 92/92
- ✅ Lint / pre-commit local
- ✅ Live HTTP smoke — workspaces + onboarding card + 4 reports + brand assets all 200
- ✅ All 4 reports execute end-to-end via `bench execute`
- ✅ `bench migrate` on `myschools.localhost` clean; all 11 new fixture JSONs parse
- ✅ Browser smoke — 12/12 Playwright tests green locally
- ✅ Wizard walkthrough — drove the full flow against `test_p4` (setup_complete=0 → walk all slides → Complete Setup → verified `Company`, `MYS Cluster CLR-WIZARD`, `MYS Branch BR-WIZ`, `MYS Campus BR-WIZ-Junior` all persisted with correct link chain)
- ✅ CI Lint + Tests + E2E all green on `4fe7f78`

---

## 2. Uncommitted state on `develop` — DO NOT LOSE

`git status` on the local clone shows several uncommitted things that are **not Phase 6** — they're a separate in-flight piece of work:

```
M  .gitignore
?? .cursor/                                          # rules/ subdir is intended-to-commit
?? AGENTS.md                                         # intended-to-commit
?? myschools.code-workspace                          # intended-to-stay-ignored (by new gitignore)
?? frappe-bench/apps/myschools/myschools/public/node_modules   # Playwright cache leak, needs gitignore rule
?? frappe-bench/apps/myschools/myschools/scripts/_smoke_inspect_comm.py   # throwaway, delete
?? frappe-bench/apps/myschools/myschools/scripts/_smoke_notif_fire.py     # throwaway, delete
?? frappe-bench/apps/myschools/myschools/scripts/_smoke_notif_jinja.py    # throwaway, delete
?? frappe-bench/apps/myschools/myschools/scripts/_smoke_seed_check.py     # throwaway, delete
```

### Two separable PRs

**PR A — Cursor IDE support** (this is the work that produced this handoff doc):
- The `.gitignore` modification adds rules that **commit** `AGENTS.md` and `.cursor/rules/`, and **ignore** per-user Cursor scratch and `myschools.code-workspace`.
- Files to stage: `.gitignore`, `AGENTS.md`, `.cursor/rules/*.mdc` (9 files), `.cursor/mcp.json` (if present).
- Verify after staging that `git status` no longer lists `myschools.code-workspace` or the rest of `.cursor/` — that confirms the ignore rules took.

**PR B — Cleanup debt** (small, atomic):
1. Delete the four `_smoke_*.py` scratch scripts. They were ad-hoc verification helpers from Phases 4/5; their work is now baked into proper unit tests under `myschools/tests/`. Underscore prefix = throwaway.
2. Extend the `.gitignore` to cover `frappe-bench/apps/myschools/myschools/public/node_modules/` (the existing rule covers the parent app's `node_modules/` but not this nested Playwright cache).

These can be done in either order; both are tiny.

---

## 3. Where the roadmap goes next — Phase 7 (Portals)

Authoritative source: [`docs/roadmap.md`](docs/roadmap.md). Summary so the next agent knows the shape:

- **Goal:** mobile-friendly `/portal`, `/branch-dashboard`, `/inspection` surfaces for Guardians, Branch staff, and Audit officers.
- **Hard constraint** (from [`upgrade-safe-only.mdc`](.cursor/rules/upgrade-safe-only.mdc)): **Frappe Web Forms + `www/` Jinja templates, not Vue/React.** No custom SPA. This was explicitly confirmed during planning — don't relitigate it.
- **Auth:** start with email/password (Frappe default). SMS OTP is a Phase 8 follow-up if the Pakistani UX requires it.
- **Estimated size:** L (16–24h).

### Suggested first move for Phase 7

1. `git log --oneline -25 develop` and `ls www/` (per the verify-before-starting rule in `pr-verification.mdc`).
2. Open a planning thread to decide: which portal first (Guardian likely — biggest user base), what data scope (children + fees + receipts as the MVP), and which Web Form vs. plain `www/` page each surface should be.
3. Cut `feature/phase-7-portals` off `develop` once the plan is agreed.

---

## 4. How to actually run things locally

These are the commands that worked during Phase 6 — no guessing.

### Frappe bench

```bash
cd /Users/ali/projects/myschools/frappe-bench
bench start                        # serves on http://myschools.localhost:8000
bench --site myschools.localhost migrate    # apply latest fixtures
bench --site myschools.localhost console    # interactive Python
```

### Tests (Python)

```bash
cd /Users/ali/projects/myschools/frappe-bench
bench --site myschools.localhost run-tests --app myschools
# or scoped:
bench --site myschools.localhost run-tests --app myschools --module myschools.tests.test_setup_wizard
```

Test sites currently present:
- `myschools.localhost` — primary dev site
- `test_p4` — currently in **post-wizard-walkthrough** state (setup_complete=1, has `MY School HO Wizard Test` company, `CLR-WIZARD` cluster, `BR-WIZ` branch, `BR-WIZ-Junior` campus). There's a `sites/test_p4.localhost` symlink → `test_p4` so it's reachable at `http://test_p4.localhost:8000`.
- `test_mys_pf`, `test_workflow_phase5` — earlier-phase test sites.

### Playwright (E2E)

```bash
cd /Users/ali/projects/myschools/frappe-bench/apps/myschools
npx playwright test tests/e2e/phase6_smoke.spec.ts --project=chromium       # ~20s
npx playwright test tests/e2e/workflows.spec.ts --project=chromium          # phase 5 spec
```

For the wizard walkthrough (needs setup_complete=0):

```bash
MYS_WIZARD_TEST=1 MYS_BASE_URL=http://test_p4.localhost:8000 \
  npx playwright test tests/e2e/setup_wizard_walkthrough.spec.ts --project=chromium
```

Note: `test_p4` is currently already-set-up so this would fail until you bootstrap a new pre-setup site. The spec is committed precisely so the next operator running a fresh install has a regression net.

### Direct report runs (no UI)

```bash
cd /Users/ali/projects/myschools/frappe-bench
cat > /tmp/r.py <<'PY'
import frappe
frappe.init(site="myschools.localhost")
frappe.connect()
from myschools.my_school_erp.report.mys_royalty_aging.mys_royalty_aging import execute
cols, rows = execute(None)
print(f"cols={len(cols)} rows={len(rows)}")
PY
bench --site myschools.localhost execute "exec(open('/tmp/r.py').read())"
```

### Pre-commit + lint

```bash
cd /Users/ali/projects/myschools
pre-commit run --all-files
# specific hooks:
pre-commit run prettier --all-files
pre-commit run eslint --all-files
pre-commit run ruff --all-files
```

---

## 5. Test passwords currently in use (local-dev only — not secrets)

- `Administrator` / `admin` — every bench site
- `e2e_audit@mys.local` / `mys-e2e-audit` — Phase 5 e2e seed
- `e2e_director@mys.local` / `mys-e2e-director` — Phase 5 e2e seed
- `wizard-test@mys.local` / `wizard-test-pw-123` — created by the wizard walkthrough spec on `test_p4`

These are committed in test code intentionally; they only work against local bench sites.

---

## 6. Conventions you'll trip over otherwise

- **Roadmap is the single source of truth.** If `docs/roadmap.md` and any other doc (this one included) disagree, the roadmap wins. Update the roadmap in the same PR that lands the phase. ([roadmap-in-repo](.cursor/rules/roadmap-in-repo.mdc))
- **Fixture conventions:**
  - All MYS fixtures are prefixed `MYS ` or `MYS-`.
  - Reports use `is_standard: "Yes"` and `report_type: "Script Report"` with a sibling `<slug>.py` exporting `execute(filters=None) -> (columns, rows)` and an `__init__.py`.
  - Onboarding steps live under `my_school_erp/onboarding_step/<slug>/<slug>.json`, NOT under their parent card.
  - Module Onboarding is per-Module-Def, not per-Workspace. Phase 6 ships **one** comprehensive card, not five per-workspace ones — the rationale is in [`docs/processes/setup-and-onboarding.md`](docs/processes/setup-and-onboarding.md).
- **Commit messages:** Conventional Commits. Look at `git log --oneline -25` for the style.
- **Verification before merge:** walk the full battery, never just lean on CI. See [`pr-verification.mdc`](.cursor/rules/pr-verification.mdc) — it lists the seven steps and the three incidents that motivated each.

---

## 7. What this session actually accomplished — chronological

For grep value, the commits that produced the Phase 6 work:

```
16ba09d feat(setup-wizard): add MYS franchise-tree slide and stage
0d76dc4 feat(onboarding): add MYS Franchise Setup module onboarding card
6987be5 feat(reports): add first batch of MYS Query Reports
67d82c8 docs(phase-6): roadmap, CHANGELOG and new process doc
08d58e7 fix(setup-wizard,lint): drop mys.* global, satisfy prettier line width
94fc0ae test(e2e): add Phase 6 browser smoke spec
e308d66 test(e2e): ignore socket.io connection errors in Phase 6 report smoke
4fe7f78 test(e2e): add Setup Wizard walkthrough spec (env-gated)
19fdbc5 Merge pull request #9 from darulmasaadir/feature/setup-wizard-and-reports
```

Conversation arc, briefly:
1. Ali asked to start Phase 6. Plan was agreed in the previous session: 4 slices = wizard + onboarding + reports + docs.
2. Slices landed in order (`16ba09d` → `67d82c8`).
3. PR #9 opened; first CI hit a Lint failure (`08d58e7` fixed it).
4. Ali pushed back: *"have you tested it?"* This triggered the full verification battery per `pr-verification.mdc`.
5. Battery work produced two new specs (`94fc0ae`, `4fe7f78`) and one more CI fix (`e308d66`).
6. Ali asked specifically whether the **wizard slide and fresh-install walkthrough** were exercised. They weren't — that became the walkthrough spec (`4fe7f78`), which drove the wizard end-to-end against `test_p4`.
7. Ali authorised merge. PR squashed in as merge commit `19fdbc5`. Local feature branch deleted.
8. Ali asked about the untracked files (above) — turns out it's an unrelated in-flight Cursor IDE integration plus some Phase 4/5 throwaway smoke scripts.
9. Ali asked for this handoff doc to move to Cursor.

---

## 8. Open questions / decisions Cursor might face

- **Cleanup PR ordering** — do PR A (Cursor IDE) and PR B (delete `_smoke_*.py` + gitignore `public/node_modules`) separately, or bundle? My recommendation: separate, since they touch different intents and PR A is reviewable as a self-contained "agent infra" change.
- **Phase 7 portal scope** — Guardian portal first vs. Branch dashboard first. Roadmap is silent on order. The Guardian portal is highest user count; the Branch dashboard probably reuses more existing fixtures. Decide before writing JSON.
- **Test site for wizard walkthrough in CI** — currently env-gated and only runs locally. If Phase 7 adds more wizard-related work, it may be worth carving a second CI matrix job that bootstraps a wizard-able site. Not urgent.

---

**End of handoff. Go read [`AGENTS.md`](AGENTS.md) and [`docs/roadmap.md`](docs/roadmap.md) before doing anything else.**
