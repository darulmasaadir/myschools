# Agent Guide — MY School ERP

This file (and the `.cursor/rules/` directory next to it) is the **persistent memory** for any AI coding agent working on this repo. Whether you're in Cursor, Claude Code, Codex CLI, or another agent runtime, start here.

## Read-this-first checklist

Before doing **anything** other than answering a narrow read-only question:

1. **Read [`docs/roadmap.md`](docs/roadmap.md)** — single source of truth for what's shipped, what's in flight, what's next. The roadmap supersedes any session-local plan. See [`roadmap-in-repo`](.cursor/rules/roadmap-in-repo.mdc).
2. **Check `git log --oneline -25` on `develop`** — verify the work you're about to start hasn't already merged.
3. **Skim the rules in [`.cursor/rules/`](.cursor/rules/)** — every one applies always; they encode hard-won lessons.

## What this project is

A multi-tier Frappe-based school ERP for **MY School (myschools.pk)**, a nationwide Pakistan school franchise. Hierarchy: Head Office → Cluster → Branch → Campus → Students → Parents. Built by extending Frappe Education v16 with custom DocTypes, fixtures, workflows, and portals.

Full scope: [`project-myschools`](.cursor/rules/project-myschools.mdc). Baseline app: [`reference-frappe-education`](.cursor/rules/reference-frappe-education.mdc).

## Standing constraints (these bind every PR)

- **[Upgrade-safe only](.cursor/rules/upgrade-safe-only.mdc)** — no custom SPA, no core forks, no monkey-patching. Customizations live inside the `myschools` app and survive `bench update`. Phase 7 portals are Frappe Web Forms + `www/`, not Vue/React.
- **[Engineering standards](.cursor/rules/engineering-standards.mdc)** — git from day one, tests, CI, pre-commit, conventional commits, branch-per-feature, PRs even when solo. Don't ask whether to add them — just add them.
- **[PR verification](.cursor/rules/pr-verification.mdc)** — never say "ready to merge" off unit tests + CI alone. **Run `scripts/pr_battery.sh`** (lint, tests+coverage, role×surface matrix, coverage floor, HTTP smoke); it stamps a per-commit sentinel and a Cursor hook (`.cursor/hooks/require-battery.sh`) **blocks `gh pr create`/`merge`/`ready`** until it passes for the current commit. Still tick the judgement items it can't auto-run in the PR body — including the **per-phase 5a/5b/5c trio: a LOCAL Playwright run (paste pass count), a manual dev-site browser walk with attached screenshots, and a written spec-completeness audit** (every surface/variant/filter/list-scope the phase added). "CI ran Playwright" satisfies none of these. Plus fresh-install, PDF, CI terminal-green. CI green is necessary but not sufficient.
- **[Jinja render test](.cursor/rules/jinja-render-test.mdc)** — Notification / Email Template fixtures need a render-against-real-doc test. Fixture-import alone misses field typos because Frappe defers Jinja eval until the alert fires.
- **[Roadmap in repo](.cursor/rules/roadmap-in-repo.mdc)** — phase status lives in `docs/roadmap.md`, updated in the same PR that lands the phase.

## Working style

- **[Execution mode](.cursor/rules/execution-mode.mdc)** — Ali prefers direct execution over a long clarifying-question phase. One small confirmation at most when truly blocked, otherwise pick reasonable defaults, state them in one sentence, and start.
- **[User profile](.cursor/rules/user-profile.mdc)** — Ali Sufyan, product owner / decision maker; treats the agent as the implementer.

## Where the code lives

- App: [`frappe-bench/apps/myschools/`](frappe-bench/apps/myschools/) (only this is tracked under the bench; rest is regenerated)
- Tests: [`frappe-bench/apps/myschools/myschools/tests/`](frappe-bench/apps/myschools/myschools/tests/)
- Hooks: [`frappe-bench/apps/myschools/myschools/hooks.py`](frappe-bench/apps/myschools/myschools/hooks.py)
- Fixtures: [`frappe-bench/apps/myschools/myschools/fixtures/`](frappe-bench/apps/myschools/myschools/fixtures/)
- Build scripts (source-of-truth for fixtures): [`frappe-bench/apps/myschools/myschools/scripts/`](frappe-bench/apps/myschools/myschools/scripts/)
- Process docs: [`docs/processes/`](docs/processes/)

## Status snapshot (as of 2026-06-07)

- ✅ Phases 0–6: foundations, branding, workspaces, print formats, notifications, workflows, setup wizard + reports
- ✅ **Phase 7**: Portals — 7a–7d merged (PR #15, `9b02a81`)
- ✅ **Phase 8**: Domain extensions — 8a–8e complete (last: PR #20, `802e6fc` — payment gateway stubs)
- ✅ **Phase 9**: Teacher Portal — PR #22 (`09185cb`)
- ✅ **Phase 10**: Attendance + Examination — PR #23 (`584a0d0`)
- ✅ **Phase 11**: Academic scheduling — PR #24 (`98821d9`)

Authoritative version: [`docs/roadmap.md`](docs/roadmap.md). If this file disagrees with the roadmap, **the roadmap wins** — fix this file in the same PR that updates the roadmap.
