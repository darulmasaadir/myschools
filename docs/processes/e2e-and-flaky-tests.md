# E2E testing and flaky-test policy

How browser automation, coverage floors, and quarantine fit the MY School
engineering standard. Complements [development.md §5](../development.md) and
[pr-verification](../../.cursor/rules/pr-verification.mdc).

## Test pyramid (default)

| Layer | Tool | When to add |
|-------|------|-------------|
| Unit / API | `bench run-tests --app myschools` | Every non-trivial bug fix and new whitelist |
| HTTP battery | `scripts/verify_http_battery.py` | Portal routes and role landing (not a substitute for browser) |
| Playwright | `tests/e2e/*.spec.ts` | User-visible flows that broke in production or manual battery |
| Manual battery | PR verification template | Shrinks as Playwright absorbs stable paths |

**Rule:** Every production bug gets a regression test at the **cheapest layer
that would have caught it**. Browser-only bugs (CSRF, `confirm()`, form POST)
belong in Playwright.

## Playwright specs

| Spec | Scope |
|------|--------|
| `workflows.spec.ts` | Phase 5 desk workflow buttons |
| `phase6_smoke.spec.ts` | Setup wizard, reports, brand assets |
| `phase7d_inspection_portal.spec.ts` | Inspection portal matrix + guest admission |
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
`myschools/*` (excluding `tests/` and `scripts/`) against
`frappe-bench/apps/myschools/coverage_floor.json`.

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

Not automated here (stay in manual battery until needed): fresh-install browser
walk, every role × desk surface, PDF round-trip.
