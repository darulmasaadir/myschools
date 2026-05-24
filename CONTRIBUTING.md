# Contributing to MY School ERP

Thanks for working on the MY School ERP. This document captures the
engineering conventions we follow.

## Branching model

```
main      ← production-ready; protected; only updated via PR from develop or release/*
develop   ← integration branch; PRs from feature/* merge here
feature/* ← one branch per feature or fix; name e.g. feature/royalty-overrides
fix/*     ← bug fixes against develop
hotfix/*  ← urgent fixes against main; back-merged to develop after release
release/* ← release stabilisation branches (e.g. release/0.2.0)
```

- Never commit directly to `main` or `develop`.
- Rebase feature branches on `develop` before opening a PR; squash merge into `develop`.

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```
<type>(<scope>): <subject>

<body explaining the why>

<footer with issue refs>
```

Types we use: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `ci`, `chore`.

Examples:

- `feat(royalty): add per-campus rate override with effective dates`
- `fix(permissions): branch_query returns empty IN-list crashes for users with no employee`
- `refactor(identity): extract role-code lookup into a constants module`
- `chore(ci): pin ruff to v0.8.1 to match pre-commit`

## Local setup

```bash
# clone the repo, then bootstrap a bench (see README "Recreating from zero")
cd frappe-bench/apps/myschools
uv pip install pre-commit  # or pip
pre-commit install
```

The pre-commit hooks run automatically on `git commit`. Run manually with:

```bash
pre-commit run --all-files
```

## Tests

Unit tests live in `frappe-bench/apps/myschools/myschools/tests/`. They are
run by Frappe's test runner against a real test database:

```bash
bench --site myschools.localhost run-tests --app myschools
```

Pure-Python helpers that don't touch the DB are unit-tested with `pytest`:

```bash
cd frappe-bench/apps/myschools
pytest myschools/tests/unit/
```

CI runs both on every PR.

## Pull requests

1. Open the PR against `develop` (not `main`).
2. Fill out the PR template — describe the *why*, list the verification you did,
   note any DocType / migration changes.
3. Keep PRs small. If the change touches more than ~5 DocTypes or rewrites a
   permission query, split it.
4. CI must pass (lint + tests) before merge.
5. At least one approving review is required before merging.

## DocType changes

- Always run `bench migrate` after editing a DocType JSON and re-export fixtures
  if the change touches a custom field on an upstream DocType.
- A DocType field rename requires a backfill script — add one under
  `myschools/patches/` and reference it from `myschools/patches.txt`.
- Submittable DocTypes need an `amended_from` field; don't forget it.
- Field name `owner` is **reserved** by Frappe (it's the user who created the
  doc). Use `franchisee`, `assigned_to`, or another domain term instead.

## Documentation

Documentation lives under [docs/](docs/) — start at [docs/README.md](docs/README.md)
for the nav index. Every PR should answer the question *"which doc would have
warned me about this change?"* and update it (or call out "no doc impact" in
the PR description). The matrix of which change updates which doc is in
[docs/development.md §9](docs/development.md#9-documentation-policy).

User-visible changes also need an entry in [CHANGELOG.md](CHANGELOG.md) under
`[Unreleased]`.

## Security

- Never commit secrets (`.env`, DB passwords, signed agreement PDFs from real
  franchisees, student CNICs).
- Real CNICs and parent contact info must never be checked into the repo, not
  even in test fixtures — use synthetic data.
- Pre-commit's `detect-private-key` hook catches accidental key commits.
