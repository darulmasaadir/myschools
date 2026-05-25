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

## 2. The 10 franchise roles → workspaces

| Role | Lands on | Tier | Module Profile |
|---|---|---|---|
| Chief Executive | `/app/mys-head-office` | Head Office | MYS HO |
| HO Dept Head | `/app/mys-head-office` | Head Office | MYS HO |
| Cluster Director | `/app/mys-cluster` | Cluster | MYS Cluster |
| Academic Monitor | `/app/mys-inspection` | Inspection | MYS Inspection |
| Audit Officer | `/app/mys-inspection` | Inspection | MYS Inspection |
| Branch Director | `/app/mys-branch` | Branch | MYS Branch |
| Branch Principal | `/app/mys-branch` | Branch | MYS Branch |
| Branch Admin | `/app/mys-branch` | Branch | MYS Branch |
| Branch Accountant | `/app/mys-branch` | Branch | MYS Branch |
| Campus Incharge | `/app/mys-campus` | Campus | MYS Campus |

Defined in
[`hooks.py.role_home_page`](../../frappe-bench/apps/myschools/myschools/hooks.py)
and in the 5 Workspace fixtures under
[`my_school_erp/workspace/`](../../frappe-bench/apps/myschools/myschools/my_school_erp/workspace/).

---

## 3. What each workspace shows

Each fixture is a JSON file with three meaningful sections — `shortcuts` (chips
at the top), `cards` (Number Card embeds), and `charts` (Dashboard Chart
embeds). All three reuse the existing Central Monitoring artefacts; nothing
is rebuilt.

| Workspace | Audience | Key contents |
|---|---|---|
| `mys-head-office` | CEO, HO Dept Head | 8 Number Cards (Active Branches, Outstanding Royalty, Open Findings…) + 3 charts + shortcuts to Cluster / Branch / Franchise Agreement / Royalty Invoice / Inspection Visit. The full Central Monitoring Dashboard, embedded inline. |
| `mys-cluster` | Cluster Director | Cluster-scoped subset: Branches, Royalty Invoices, Findings. Royalty-by-Cluster + Findings charts. |
| `mys-branch` | Branch Director, Principal, Admin, Accountant | Student / Fees / Royalty Invoice / Finding / Employee shortcuts. Numbers come through `permission_query_conditions` automatically scoped to the user's branch. |
| `mys-campus` | Campus Incharge | Smallest workspace — Students + attendance shortcuts. Numbers scoped to the campus. |
| `mys-inspection` | Academic Monitor, Audit Officer | Inspection Checklist Template / Visit / Finding / Corrective Action shortcuts + Findings by Severity chart. Cross-cuts the hierarchy. |

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
modules to **hide**. Each MYS Module Profile blocks a tier-appropriate set:

| Profile | Blocks (additive top to bottom) |
|---|---|
| `MYS HO` | The 15 vanilla modules listed above |
| `MYS Cluster` | + CRM, Selling |
| `MYS Branch` | (same as Cluster) |
| `MYS Campus` | + Accounts |
| `MYS Inspection` | + Education |

Net effect on what each tier sees in the left sidebar:

| Profile | Visible modules |
|---|---|
| MYS HO | MY School ERP, Accounts, CRM, Education, HR, Selling, Setup |
| MYS Cluster | MY School ERP, Accounts, Education, HR, Setup |
| MYS Branch | MY School ERP, Accounts, Education, HR, Setup |
| MYS Campus | MY School ERP, Education, HR, Setup |
| MYS Inspection | MY School ERP, HR, Setup |

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

1. Add the role name to `FRANCHISE_ROLES` in
   [`setup/install.py`](../../frappe-bench/apps/myschools/myschools/setup/install.py).
2. Add the role → workspace mapping in `role_home_page` in `hooks.py`.
3. Decide which Module Profile the role belongs to: add it to the right tier
   set in `TIER_PROFILE_ORDER` in
   [`api/user_profile.py`](../../frappe-bench/apps/myschools/myschools/api/user_profile.py).
4. Add the role to the target workspace's `roles` array (the
   `restrict_to_role` mechanism). Edit the JSON fixture under
   `my_school_erp/workspace/<slug>/<slug>.json`.
5. `bench --site myschools.localhost migrate` to apply.
6. Add a test in
   [`tests/test_shell.py`](../../frappe-bench/apps/myschools/myschools/tests/test_shell.py)
   that asserts the new role resolves to the right Module Profile.

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
