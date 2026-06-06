# E2E testing and flaky-test policy

How browser automation, coverage floors, and quarantine fit the MY School
engineering standard. Complements [development.md §5](../development.md) and
[pr-verification](../../.cursor/rules/pr-verification.mdc).

## Local gate before finalising a PR

Run the whole automatable battery with **one command**:

```bash
scripts/pr_battery.sh
```

It runs lint, unit tests + coverage, the role×surface branch-desk matrix, the
coverage floor, and the HTTP smoke, then writes `.cursor/.pr-battery-pass`
stamped with the current commit SHA. A Cursor hook
(`.cursor/hooks/require-battery.sh`, wired in `.cursor/hooks.json`) **blocks
`gh pr create` / `gh pr merge` / `gh pr ready`** unless that sentinel matches
HEAD — so a PR can't be finalised without the battery having run green on the
exact commit. The runner also prints the judgement-only items (fresh-install,
browser, PDF, CI terminal-green) to tick in the PR body.

## Test pyramid (default)

| Layer | Tool | Runs in CI? | When to add |
|-------|------|-------------|-------------|
| Unit / API | `bench run-tests --app myschools` | ✅ test job | Every non-trivial bug fix and new whitelist |
| Coverage floor | `scripts/check_coverage_floor.py` | ✅ test job | Ratchet — never lower |
| HTTP battery | `scripts/verify_http_battery.py` | ✅ e2e job | Portal routes and role landing (not a substitute for browser) |
| Branch desk matrix | `scripts/verify_branch_desk_cards.py` | ✅ e2e job | Role × number-card surface regressions |
| Fee-admin matrix | `scripts/verify_fee_admin_surfaces.py` | ✅ e2e job | Role × override/policy/bulk-run permission regressions |
| Student-lifecycle matrix | `scripts/verify_student_lifecycle_surfaces.py` | ✅ e2e job | Role × transfer/leaving permission regressions |
| SMS adapter smoke | `scripts/verify_sms_adapters.py` | ✅ e2e job | Stub `send_sms` + gateway fields on Communication Log |
| Late-fee scheduler e2e | `scripts/verify_late_fees.py` | ✅ e2e job | Fires real `scheduled_apply_late_fees()` on a self-contained overdue scenario; asserts linked late fee + idempotency. Self-cleaning |
| Playwright | `tests/e2e/*.spec.ts` | ✅ e2e job | User-visible flows that broke in production or manual battery |
| Manual battery | PR verification template | ❌ by hand | Net-new feature's *first* walk, PDF round-trip, anything no spec covers yet |

**Everything marked ✅ runs automatically on every push/PR — no one has to ask.**
The manual battery is now only: (a) the first browser walk of a brand-new
surface before a spec exists, and (b) PDF round-trip when a print format
changes. Each manual check should be converted into an automated layer the
first time it's run (add a Playwright spec / verify script), so the manual
list keeps shrinking.

**Rule:** Every production bug gets a regression test at the **cheapest layer
that would have caught it**. Browser-only bugs (CSRF, `confirm()`, form POST)
belong in Playwright.

## Playwright specs

| Spec | Scope |
|------|--------|
| `workflows.spec.ts` | Phase 5 desk workflow buttons |
| `phase6_smoke.spec.ts` | Setup wizard, reports, brand assets |
| `phase7d_inspection_portal.spec.ts` | Inspection portal matrix + guest admission |
| `phase8a_bulk_fee_run.spec.ts` | Bulk Fee Run desk: Generate Fees (seeded + from blank) + role denial |
| `phase8a_fee_admin_forms.spec.ts` | Override / late-fee-policy forms: Director create, Principal denial |
| `phase8b_student_lifecycle.spec.ts` | Transfer / leaving forms: Director submit, certificate print, Monitor denial |
| `phase8c_sms_settings.spec.ts` | MYS SMS Settings single: Stub default + save, Twilio section reveal |
| `phase8d_hr_payroll.spec.ts` | Employee branch-scope leak check (Director); Payroll Entry `mys_branch` field |
| `setup_wizard_walkthrough.spec.ts` | Opt-in (`MYS_WIZARD_TEST=1`) |

### Running locally

```bash
bench --site myschools.localhost execute myschools.scripts.seed_e2e.main
cd frappe-bench/apps/myschools
MYS_BASE_URL=http://myschools.localhost:8000 npx playwright test tests/e2e/phase7d_inspection_portal.spec.ts
```

CI runs the full suite after `seed_e2e.main` on `test_site`.

## Coverage floor (ratchet)

After unit tests with `--coverage`, CI runs
`myschools/scripts/check_coverage_floor.py`, which compares line coverage for
the `myschools` app (excluding `tests/` and `scripts/`) against
`frappe-bench/apps/myschools/coverage_floor.json`. The floor is **63%**
(CI measured 64.5% on 2026-06-03; local dev ~67%). `bench run-tests --coverage` writes
`frappe-bench/sites/.coverage` with absolute paths, so the script matches the
include glob anywhere in the path.

- **Do not lower the floor** without an explicit product decision.
- **Raise the floor** in the same PR when you add tests that increase coverage.

## Flaky-test policy

1. **Do not delete or `@skip` a flaky test** to get CI green.
2. **Reproduce** locally with `npx playwright test <file> --repeat-each=5`.
3. **Fix root cause** (timing, missing `waitForURL`, shared state, seed drift).
4. If fix needs more than one session, **quarantine**:
   - Playwright: `test.fixme(true, "flaky: issue #NNN — …")` with a linked issue.
   - Python: `@unittest.skip("flaky: #NNN")` only with the same issue link.
5. **Time-box quarantine:** resolve or rewrite within 14 days; quarantined tests
   count against the team until fixed.
6. **Retries:** CI uses `retries: 1` for Playwright only. Retries are not a
   substitute for fixing flakes.

## Phase 7d matrix (automated)

| Cell | Playwright test |
|------|-----------------|
| Monitor dashboard | `Academic Monitor dashboard…` |
| Monitor happy path | `Monitor happy path…` |
| Fail Critical → finding | `Monitor fail Critical…` + unit `test_fail_critical_as_academic_monitor…` |
| Audit Officer access | `Audit Officer can open…` |
| Branch Director denied | `Branch Director is denied…` |
| Guest admission validation | `requires parent name and phone…` |
| Guest admission success | `guest submission succeeds` |

## Phase 8a matrix (automated)

| Cell | Playwright test |
|------|-----------------|
| Branch Accountant → Generate Fees (seeded draft) | `Branch Accountant: Generate Fees on seeded draft` |
| Branch Accountant → new run from blank → Generate | `Branch Accountant: new run from blank…` |
| Branch Director → create override / policy | `Branch Director creates a Fee Structure Override` / `… Late Fee Policy` |
| Branch Accountant → Fees override orange alert | `Branch Accountant: Fees orange alert when fee structure mismatches override` |
| Branch Principal denied (override) | `Branch Principal is denied on Fee Structure Override` |
| Academic Monitor denied (bulk run) | `Academic Monitor is denied on Bulk Fee Run list` |
| Role × surface permission matrix | `scripts/verify_fee_admin_surfaces.py` |
| Bulk API / override / skip | `tests/test_bulk_fee_run.py` + `verify_late_fees.py` |

## Phase 8b matrix (automated)

| Cell | Playwright test |
|------|-----------------|
| Branch Director → campus transfer submit | `Branch Director submits campus transfer` |
| Branch Director → leaving submit + certificate print | `Branch Director submits student leaving + leaving certificate print` |
| Academic Monitor denied (transfer) | `Academic Monitor is denied on Student Transfer list` |
| Role × surface permission matrix | `scripts/verify_student_lifecycle_surfaces.py` |
| Transfer / leaving API + enrollment guard | `tests/test_student_lifecycle.py` |

Not automated here (stay in manual battery until needed): fresh-install browser
walk, every role × desk surface, PDF round-trip.
