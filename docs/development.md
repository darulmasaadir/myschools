# Development Guide

How to set up the bench locally, run tests, write code, document changes, and
ship them.

> **Companion docs**: [../CONTRIBUTING.md](../CONTRIBUTING.md) (branching,
> commits, PR workflow) · [architecture.md](architecture.md) (system design).

---

## 1. Prerequisites

| Tool | Version | How to get it (macOS) |
|---|---|---|
| Python | 3.12 | `brew install python@3.12` |
| Node.js | 18+ | `brew install node@18` |
| MariaDB | 10.6+ | `brew install mariadb` |
| Redis | 7+ | `brew install redis` |
| wkhtmltopdf | 0.12.x (patched-qt) | `brew install --cask wkhtmltopdf` |
| Frappe Bench CLI | latest | `pipx install frappe-bench` |
| Git, ruff, pre-commit | latest | `brew install git ruff pre-commit` |

Once installed, start the services:

```bash
brew services start mariadb
brew services start redis
```

---

## 2. First-time bench setup

The full bootstrap (from a clean machine to a running site) is recorded in
[../README.md "Recreating from zero"](../README.md#recreating-from-zero). The
short version:

```bash
git clone git@book:darulmasaadir/myschools.git
cd myschools

bench init frappe-bench --python /opt/homebrew/bin/python3.12 --frappe-branch version-15 --no-backups
cd frappe-bench
bench get-app erpnext --branch version-15
bench get-app education --branch version-15.2

bench new-site myschools.localhost \
  --mariadb-root-password 'frappe_root_2026' \
  --admin-password admin \
  --install-app erpnext --install-app education \
  --db-name myschools

# Link our app (this repo tracks frappe-bench/apps/myschools)
bench --site myschools.localhost install-app myschools
bench --site myschools.localhost migrate
bench --site myschools.localhost set-config allow_tests true   # enables the test runner
bench --site myschools.localhost execute myschools.scripts.seed_demo.run
echo "y" | bench setup procfile
bench start
```

The site is then at <http://myschools.localhost:8000/login> (`Administrator` /
`admin`). Local dev only — those credentials must never appear in a real environment.

---

## 3. Repo layout (developer view)

```
myschools/
├── docs/                                ← you are here
├── .github/workflows/ci.yml             ← lint + Frappe test suite on push/PR
├── .pre-commit-config.yaml              ← whitespace, AST, ruff, JSON/TOML/YAML lint
├── CHANGELOG.md                         ← Keep-a-Changelog; update under [Unreleased]
├── CONTRIBUTING.md                      ← branching, commits, PR rules
├── README.md                            ← landing page
└── frappe-bench/                        ← gitignored except apps/myschools
    └── apps/myschools/
        ├── pyproject.toml               ← ruff config (line-length 110, py310 target, tabs)
        └── myschools/
            ├── hooks.py                 ← all Frappe wiring (events, scheduler, permissions, fixtures)
            ├── setup/install.py         ← after_install / after_migrate
            ├── api/
            │   ├── identity.py          ← student/staff ID generation
            │   ├── permissions.py       ← _user_scope() + per-doctype query conditions
            │   ├── royalty.py           ← rate resolution + monthly invoice job
            │   └── inspection.py        ← apply_template + auto-create findings
            ├── my_school_erp/doctype/   ← every custom DocType (json schema + py controller + js client)
            ├── scripts/                 ← seed_demo, demo_royalty_invoice
            ├── tests/                   ← integration tests (run via bench run-tests)
            └── patches/                 ← DocType migrations (referenced from patches.txt)
```

The entire `frappe-bench/` directory is `.gitignore`d **except** for
`apps/myschools/`. Bench, venv, sites, logs, and upstream apps are reproduced
on every clone. This means anyone can re-run the bootstrap above and end up
with an identical site.

---

## 4. Daily workflow

### Branching

```
main      ← production, protected
develop   ← integration; PRs from feature/* land here
feature/* ← one branch per feature; e.g. feature/inspection-decomposition
fix/*     ← bug fixes against develop
hotfix/*  ← urgent fixes against main (back-merged to develop)
```

Start a feature:

```bash
git checkout develop && git pull
git checkout -b feature/<short-kebab-name>
```

### Pre-commit

```bash
cd frappe-bench/apps/myschools
pre-commit install     # one-time
```

After install, `git commit` runs the hooks automatically. Run manually with
`pre-commit run --all-files`.

### Commits

[Conventional Commits](https://www.conventionalcommits.org/) — see
[../CONTRIBUTING.md](../CONTRIBUTING.md#commit-messages) for the type list and
examples.

### Migrations

Any DocType JSON edit needs a migrate:

```bash
bench --site myschools.localhost migrate
```

Field renames or destructive schema changes need a patch under
`myschools/patches/<name>.py` referenced from `myschools/patches.txt`.

---

## 5. Running tests

```bash
# all integration tests for our app
bench --site myschools.localhost run-tests --app myschools

# a single test module
bench --site myschools.localhost run-tests --app myschools --module myschools.tests.test_royalty

# a single test
bench --site myschools.localhost run-tests --app myschools \
  --module myschools.tests.test_inspection \
  --test test_apply_template_snapshots_items
```

Suite at time of writing: **19 integration tests** (7 royalty resolution + 3 royalty-from-fees + 9 inspection).

### Test conventions

- We use Frappe's `FrappeTestCase` (from `frappe.tests.utils`), not the
  older `unittest.TestCase`. `FrappeTestCase` rolls back at **class** level
  (`tearDownClass`), not per test — so if your tests mutate data, add a
  per-test `tearDown` to clean up.
- Synthetic CNICs only. No real PII in fixtures or test data.
- Employees use Frappe's autoname (`HR-EMP-XXX`) — you can't pass a custom
  `name`. Tag test Employees with a unique field like `personal_email`,
  insert, then capture `emp.name` for later lookups.
- Submitted documents must be cancelled before delete in `tearDownClass`.

### CI

Every push and PR runs:

1. **Lint** — `ruff check` + `ruff format --check`.
2. **Frappe test suite** — spins up MariaDB + Redis services in GitHub
   Actions, builds the bench, installs erpnext/education/myschools, runs the
   suite.

Workflow: [.github/workflows/ci.yml](../.github/workflows/ci.yml). Both jobs
must pass before a PR can merge.

---

## 6. Adding a new DocType

1. Create the DocType in the UI under
   `http://myschools.localhost:8000/app/doctype/new?module=my_school_erp&custom=0`.
   Module = `My School ERP`, app = `myschools`, prefix the name with `MYS`.
2. Add fields in the UI; commit the auto-generated JSON.
3. Write the Python controller next to the JSON
   (`mys_<name>/mys_<name>.py`).
4. Add integration tests under `myschools/tests/test_<area>.py`.
5. If the doctype needs branch-scoping, add a `*_query` function in
   `api/permissions.py` (or the relevant module) and wire it in `hooks.py`
   under `permission_query_conditions`.
6. Update [data-model.md](data-model.md) with the new DocType's fields.
7. Add a CHANGELOG entry under `[Unreleased]`.

---

## 7. Adding a custom field to an upstream DocType

We never fork upstream apps. Customisations go through Custom Field records:

1. UI → Customize Form → pick the DocType (e.g. `Student`) → add the field
   with a `mys_` prefix (e.g. `mys_branch`).
2. Export fixtures (this is wired in `hooks.py` `fixtures` already):

   ```bash
   bench --site myschools.localhost export-fixtures
   ```

3. Commit the regenerated JSON under
   `frappe-bench/apps/myschools/myschools/fixtures/custom_field.json`.
4. Update [data-model.md §5](data-model.md#5-custom-fields-on-upstream-doctypes).

---

## 8. Debugging tips

- **`bench start` won't boot** — kill stragglers: `ps aux | grep -E
  '(node|gunicorn|worker)' | grep -v grep`. If MariaDB is grumpy, check
  `tail -50 frappe-bench/logs/*.log`.
- **"Testing is disabled"** — run
  `bench --site myschools.localhost set-config allow_tests true`.
- **Permission queries returning nothing in dev** — the System Manager
  bypasses all `permission_query_conditions`. To test branch scoping, log in
  as a real user with one of the cluster/branch roles, not Administrator.
- **`ValidationError: ... already exists`** in tests — `FrappeTestCase`
  doesn't roll back per test. Add a `tearDown()` that deletes the records
  your test created.
- **`bench update` rewrites my custom field** — never edit custom fields
  via JSON directly; always go through the UI and re-export fixtures.
  Manual JSON edits are blown away by `bench migrate`.

---

## 9. Documentation policy

Each PR should answer: *what doc would have warned me about this change?*
Update that one (or note "no doc impact" in the PR).

| Change | Update |
|---|---|
| New DocType or schema change | [data-model.md](data-model.md) + [architecture.md](architecture.md) module table |
| New business rule / API function | [api/*.md](api/) + reference from the relevant process doc |
| New process or workflow | new doc under [processes/](processes/) + nav entry in [README.md](README.md) |
| Change a user-facing flow | [processes/](processes/) for that flow |
| New external dependency | [architecture.md §1 stack](architecture.md#1-stack) + [development.md prerequisites](#1-prerequisites) |
| Anything user-visible | [../CHANGELOG.md](../CHANGELOG.md) under `[Unreleased]` |

CI does **not** verify doc updates. Reviewers do.

---

## 10. Releasing

We follow [SemVer](https://semver.org/). Cutting a release:

1. Branch `release/X.Y.Z` from `develop`.
2. Move `[Unreleased]` entries in [../CHANGELOG.md](../CHANGELOG.md) under a
   new `[X.Y.Z] — YYYY-MM-DD` heading. Leave `[Unreleased]` empty above it.
3. Bump version in `frappe-bench/apps/myschools/myschools/__init__.py`.
4. Open PR to `main`. Once merged, tag the merge commit `vX.Y.Z` and push the tag.
5. Back-merge `main` → `develop`.
