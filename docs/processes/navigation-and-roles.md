# Navigation & Role Landing Pages

*Audience: Engineering team, anyone debugging "wrong workspace on login" or
"missing sidebar module" reports.*

This doc explains how a logged-in operator ends up on the right workspace
with the right sidebar — and how to extend that mapping when a new role or
workspace is introduced.

> **Status legend** — ✅ shipped & tested · 🟡 partial · ⬜ planned

---

## 1. The three moving parts

Login → desk render pulls from three independent Frappe primitives, all wired
through [`hooks.py`](../../frappe-bench/apps/myschools/myschools/hooks.py):

| Primitive | Purpose | Where it lives |
|---|---|---|
| `role_home_page` hook | "After login, send this role to this URL." | `hooks.py` |
| `Workspace` fixture | The page the URL renders — sidebar chips, shortcuts, embedded charts. | `myschools/my_school_erp/workspace/<slug>/<slug>.json` |
| `Module Profile` fixture | What appears in the *module sidebar* on the left. Block-list of upstream modules per tier. | `myschools/fixtures/module_profile.json` |

The three are independent on purpose. A Branch Admin's landing page
(`mys-branch`) is unrelated to which modules they can see in the sidebar
(`MYS Branch` module profile). Mix-and-match without coupling.

---

## 2. The franchise + portal roles → landing pages

**Single source of truth:** [`setup/role_model.py`](../../frappe-bench/apps/myschools/myschools/setup/role_model.py)
defines `FRANCHISE_ROLES`, the `ROLE_SEED_USER` login map, and the positive
per-role read grants. Import from there — never re-type role-name strings.

### Desk (System User) roles → workspaces

| Role | Lands on | Tier | Module Profile | Seed login |
|---|---|---|---|---|
| Chief Executive | `/app/mys-head-office` | Head Office | MYS HO | `ceo@mys.local` |
| Finance Dept Head | `/app/mys-head-office` | Head Office | MYS HO | `finance.head@mys.local` |
| Academic Dept Head | `/app/mys-head-office` | Head Office | MYS HO | `academic.head@mys.local` |
| Monitoring Dept Head | `/app/mys-head-office` | Head Office | MYS HO | `monitoring.head@mys.local` |
| Administration Dept Head | `/app/mys-head-office` | Head Office | MYS HO | `admin.head@mys.local` |
| Training Dept Head | `/app/mys-head-office` | Head Office | MYS HO | `training.head@mys.local` |
| Cluster Director | `/app/mys-cluster` | Cluster | MYS Cluster | `cluster.dir@mys.local` |
| Academic Monitor | `/app/mys-inspection` | Inspection | MYS Inspection | `monitor@mys.local` |
| Audit Officer | `/app/mys-inspection` | Inspection | MYS Inspection | `audit@mys.local` |
| Branch Director | `/app/mys-branch` | Branch | MYS Branch | `branch.dir@mys.local` |
| Branch Principal | `/app/mys-branch` | Branch | MYS Branch | `principal@mys.local` |
| Branch Admin | `/app/mys-branch` | Branch | MYS Branch | `branch.admin@mys.local` |
| Branch Accountant | `/app/mys-branch` | Branch | MYS Branch | `accountant@mys.local` |
| Campus Incharge | `/app/mys-campus` | Campus | MYS Campus | `campus@mys.local` |
| Campus Admin | `/app/mys-campus` | Campus | MYS Campus | `campus.admin@mys.local` |

### Portal (Website User) roles → portal routes

| Role | Lands on | Portal | Seed login |
|---|---|---|---|
| Teacher | `/teacher` | Teacher portal | `e2e_teacher@mys.local` |
| Guardian | `/guardian` | Parent portal | `e2e_guardian@mys.local` |
| Student | `/student` | Student portal (Phase 17c) | `e2e-student@mys.local` |

### Mapping to the Software Infrastructure org chart

The PDF org chart lists ~21 positions; several map to **built-in** Frappe roles
rather than custom franchise roles, and one HO position folds into another:

| Org-chart position | MY School role |
|---|---|
| Chief Executive | `Chief Executive` |
| Finance Dept Head | `Finance Dept Head` |
| Academic Dept Head | `Academic Dept Head` |
| Monitoring Dept Head | `Monitoring Dept Head` |
| Admin Dept Head (+ Marketing) | `Administration Dept Head` |
| Training Dept Head | `Training Dept Head` |
| IT / Systems | built-in `System Manager` (no custom role) |
| Cluster Director | `Cluster Director` |
| Academic Monitor | `Academic Monitor` |
| Audit Officer | `Audit Officer` |
| Branch Director / Principal / Admin / Accountant | matching `Branch *` roles |
| Campus Incharge / Campus Admin | `Campus Incharge` / `Campus Admin` |
| Teacher | `Teacher` (portal) |
| Parent | `Guardian` (portal) |
| Student | `Student` (portal) |

Defined in
[`hooks.py.role_home_page`](../../frappe-bench/apps/myschools/myschools/hooks.py)
and in the 5 Workspace fixtures under
[`my_school_erp/workspace/`](../../frappe-bench/apps/myschools/myschools/my_school_erp/workspace/).

> **Phase 17a migration.** The generic `HO Dept Head` role was split into the
> five specialized dept-head roles above. `after_migrate` strips the legacy role
> from users (`migrate_legacy_ho_dept_head`), copies its DocPerms onto the five
> new roles (`mirror_ho_dept_head_doctype_perms`), and re-syncs the workspace /
> module-onboarding role gates (`sync_franchise_workspace_roles`,
> `sync_module_onboarding_roles`) — all idempotent and upgrade-safe.

---

## 3. What each workspace shows

Each fixture is a JSON file with three meaningful sections — `shortcuts` (chips
at the top), `cards` (Number Card embeds), and `charts` (Dashboard Chart
embeds). All three reuse the existing Central Monitoring artefacts; nothing
is rebuilt.

| Workspace | Audience | Key contents |
|---|---|---|
| `mys-head-office` | CEO + the 5 dept heads (Finance / Academic / Monitoring / Administration / Training) | 8 Number Cards (Active Branches, Outstanding Royalty, Open Findings…) + 3 charts + shortcuts to Cluster / Branch / Franchise Agreement / Royalty Invoice / Inspection Visit. The full Central Monitoring Dashboard, embedded inline. |
| `mys-cluster` | Cluster Director | Cluster-scoped subset: Branches, Royalty Invoices, Findings. Royalty-by-Cluster + Findings charts. |
| `mys-branch` | Branch Director, Principal, Admin, Accountant | Student / Fees / Royalty Invoice / Finding / Employee shortcuts. Numbers come through `permission_query_conditions` automatically scoped to the user's branch. |
| `mys-campus` | Campus Incharge, Campus Admin | Smallest workspace — Students + attendance shortcuts. Numbers scoped to the campus. |
| `mys-inspection` | Academic Monitor, Audit Officer | Inspection Checklist Template / Visit / Finding / Corrective Action shortcuts + Findings by Severity chart. Cross-cuts the hierarchy. |

> The five HO dept heads share the `mys-head-office` workspace but get **different
> doctype read grants** via `HO_DEPT_ROLE_READS` in `role_model.py` — e.g. Finance
> sees royalty/fees masters, Monitoring sees inspection doctypes, Training sees
> LMS/Program. The workspace renders the same; what each head can open differs.

The HO workspace has the most content because the CEO needs a single page that
answers "is the franchise healthy?"; the Campus workspace is intentionally
sparse because a Campus Incharge mostly works inside Student records.

---

## 4. Module Profiles — sidebar scoping

Frappe's left sidebar lists every *module* a user has access to. By default
that includes Manufacturing, Stock, Buying, Maintenance, Quality Management,
Subcontracting, Bulk Transaction, Assets, Regional, ERPNext Integrations,
Telephony, Support, Projects, Utilities, EDI — all irrelevant to a school
franchise.

A `Module Profile` doctype carries a `block_modules` child table listing the
modules to **hide**. Each MYS Module Profile blocks a tier-appropriate set.

> **Phase 17d — allow-list discipline.** The block-lists were widened so the
> sidebar is a deliberate *allow*-list, not a leaky deny-list. Every tier now
> also blocks `Website`, `Automation`, `Integrations` (pure admin/dev surfaces),
> and the non-HO tiers additionally block `HR`/`Payroll`/`LMS`/`Setup` where the
> tier has no business there. This closed the Academic-Monitor HR/Payroll leak
> (an `Employee`-backed inspection user was auto-granted the stock `Employee`
> role, and the old block-list never named HR). The contract is now mechanical —
> [`scripts/verify_sidebar_surfaces.py`](../../frappe-bench/apps/myschools/myschools/scripts/verify_sidebar_surfaces.py)
> asserts each profile's required blocks **and** required allows, and is wired
> into `scripts/pr_battery.sh`.

| Profile | Blocks (beyond the 15 vanilla modules) |
|---|---|
| `MYS HO` | + Website, Automation, Integrations |
| `MYS Cluster` | + Accounts, CRM, Selling, HR, Payroll, LMS, Website, Automation, Integrations, Setup |
| `MYS Branch` | + Accounts, CRM, Selling, LMS, Website, Automation, Integrations, Setup (keeps HR — branch manages its own roster) |
| `MYS Campus` | + Accounts, CRM, Selling, HR, Payroll, LMS, Website, Automation, Integrations, Setup |
| `MYS Inspection` | + Accounts, CRM, Selling, Education, HR, Payroll, LMS, Website, Automation, Integrations, Setup |

Net effect on what each tier sees in the left sidebar:

| Profile | Visible modules |
|---|---|
| MYS HO | MY School ERP, Accounts, CRM, Education, HR, Payroll, LMS, Selling, Setup |
| MYS Cluster | MY School ERP, Education |
| MYS Branch | MY School ERP, Education, HR |
| MYS Campus | MY School ERP, Education |
| MYS Inspection | MY School ERP |

**Auto-attach.** When a User is saved (`User.validate` doc_event), the helper
[`myschools.api.user_profile.attach_module_profile_to_user`](../../frappe-bench/apps/myschools/myschools/api/user_profile.py)
inspects the User's roles, picks the **highest-tier** MYS role present, and
sets `User.module_profile` to the matching profile name. Highest tier wins so
a user with both `Branch Admin` and `Cluster Director` gets `MYS Cluster`.

**Back-fill.** Users created before this app was installed get profiles
applied on `after_migrate` via `backfill_existing_users` in
[`api/user_profile.py`](../../frappe-bench/apps/myschools/myschools/api/user_profile.py)
— no manual cleanup required.

---

## 5. Adding a new role or workspace

### To add a new role

1. Add the role name + seed login to
   [`setup/role_model.py`](../../frappe-bench/apps/myschools/myschools/setup/role_model.py)
   (`FRANCHISE_ROLES`, `ROLE_SEED_USER`, and a positive read grant in the right
   `*_READS` map). This is the single source of truth — `install.py`, the seeds,
   and the verify scripts all import from here.
2. Add the role → workspace/route mapping in `role_home_page` in `hooks.py`,
   and to the `Role` fixture list in `hooks.py.fixtures`.
3. Decide which Module Profile the role belongs to: add it to the right tier
   set in `TIER_ORDER` in
   [`api/user_profile.py`](../../frappe-bench/apps/myschools/myschools/api/user_profile.py).
4. Add the role to the target workspace's `roles` array. Edit the JSON fixture
   under `my_school_erp/workspace/<slug>/<slug>.json` **and** add it to the
   matching set in `sync_franchise_workspace_roles` in `install.py` (so existing
   sites pick it up on migrate without a full fixture re-import).
5. `bench --site myschools.localhost migrate` to apply.
6. Add the role to `tests/test_shell.py` (`EXPECTED_ROLE_HOMES`), and to the
   `ROLE_EXPECTED_PROFILE` map in `scripts/verify_sidebar_surfaces.py`. The
   umbrella `scripts/verify_all_roles.py` picks it up automatically from
   `FRANCHISE_ROLES`.

### To add a new workspace

1. Create the folder and JSON file:
   `myschools/my_school_erp/workspace/mys-newslug/mys-newslug.json`.
2. Set `restrict_to_role` to the role(s) that should see it.
3. Populate `shortcuts`, `cards`, `charts` as needed. Existing JSON files in
   the same folder are the closest reference.
4. Map the roles to this workspace in `role_home_page` in `hooks.py`.
5. `bench --site myschools.localhost migrate`.
6. Add the workspace to `EXPECTED_WORKSPACES` in `test_shell.py`.

---

## 6. Verifying changes locally

After any change above, run:

```bash
bench --site myschools.localhost migrate
bench --site myschools.localhost clear-cache
bench --site myschools.localhost run-tests --app myschools --module myschools.tests.test_shell
# Mechanical role/sidebar contracts (no role silently dropped):
bench --site myschools.localhost execute myschools.scripts.verify_all_roles.run
bench --site myschools.localhost execute myschools.scripts.verify_sidebar_surfaces.run
```

For a full smoke test create a test user with the role and log in as them in
a fresh browser session — Frappe caches the home page per-user, so an
existing logged-in tab may not pick up the new mapping until logout.

---

## 7. Why this design (over the alternatives)

- **Tier-based 5 workspaces** (over 10 per-role workspaces) — the four
  Branch-tier roles see the same operational data; duplicating the workspace
  per role would mean keeping 4 nearly-identical JSON files in sync.
- **`Module Profile` fixtures** (over `restrict_to_domain`) — domains are
  heavyweight, primarily a marketing/installer concept; Module Profile is the
  Frappe-native sidebar scoping mechanism and binds to a User explicitly.
- **`role_home_page` hook** (over a Python redirect in `on_login`) — a single
  declarative map; Frappe handles the redirect during desk boot, so it's
  faster and survives upgrades.
- **`User.validate` (over `after_insert`)** — `after_insert` fires after the
  row is written, so mutating `doc.module_profile` does nothing. `validate`
  runs before the save so the attribute change is persisted naturally.
- **`User.default_workspace` for desk landing (in addition to
  `role_home_page`)** — in Frappe v15 the `role_home_page` hook only fires
  for portal (Website User) logins. For System Users the login API reads
  `User.default_workspace` and redirects to `/app/<slug>`. We set both —
  `role_home_page` is harmless for portal users and future-proofs the
  customer-facing pages we'll add in Phase 7. Caught by HTTP smoke (curl
  login + parse `home_page`); see [`tests/test_shell.py`](../../frappe-bench/apps/myschools/myschools/tests/test_shell.py).
