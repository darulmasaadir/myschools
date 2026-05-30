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
- **[PR verification](.cursor/rules/pr-verification.mdc)** — never say "ready to merge" off unit tests + CI alone. Walk the full battery: HTTP smoke, fresh-install smoke, browser visual check, PDF round-trip if applicable. CI green is necessary but not sufficient.
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

## Status snapshot (as of 2026-05-31)

- ✅ Phases 0–6: foundations, branding, workspaces, print formats, notifications, workflows, setup wizard + reports
- 🟡 **Phase 7 (in flight)**: Portals — 7a foundations on `feature/phase-7a-portal-foundations`; 7b–7d content slices follow
- ⬜ Phase 8: Domain extensions (per-branch Fee Structure, student lifecycle, SMS adapters, HR scaffolding, payment gateways)

Authoritative version: [`docs/roadmap.md`](docs/roadmap.md). If this file disagrees with the roadmap, **the roadmap wins** — fix this file in the same PR that updates the roadmap.
