# Portals (Phase 7)

*Audience: Engineering — how MY School website portals are built and extended.*

## Constraint

Portals are **Frappe `www/` Jinja pages + Web Forms** inside the `myschools` app. No Vue/React SPA, no separate auth service. See [upgrade-safe-only](../../.cursor/rules/upgrade-safe-only.mdc).

## Phase 7a — foundations ✅

| Piece | Location |
|---|---|
| Guardian website role (`desk_access=0`) | `setup/install.py` → `create_portal_roles()` |
| `Guardian.user` custom field + email linker | `api/identity.py` → `link_guardian_user` |
| Role → portal home map | `api/portal.py` |
| `/portal` dispatcher | `www/portal/` |
| Stub slices `/guardian`, `/branch`, `/inspection` | `www/*/` |
| Shared layout | `templates/pages/mys_portal_base.html` |
| `role_home_page["Guardian"] = "guardian"` | `hooks.py` |

Anonymous `/portal` → `/login`. Logged-in users are redirected to the first matching portal role (Guardian before branch staff).

## Phase 7b — Guardian portal content ✅

Delivered PR [#13](https://github.com/darulmasaadir/myschools/pull/13).

| Route | Purpose |
|---|---|
| `/guardian` | My Children list |
| `/guardian/child?student=` | Child profile |
| `/guardian/fees` | Fee invoices + receipt download |
| `/guardian/attendance` | Last 90 days attendance |
| `/guardian-feedback` | Web Form → `MYS Communication Log` |

Data access: [`api/guardian_portal.py`](../../frappe-bench/apps/myschools/myschools/api/guardian_portal.py).

**Local smoke:** `bench --site SITE execute myschools.scripts.seed_portal_guardian.main`

## Phase 7c — Branch portal ✅

Delivered PR [#14](https://github.com/darulmasaadir/myschools/pull/14).

| Route | Purpose |
|---|---|
| `/branch` | Dashboard: branch info + findings / royalty / fee KPIs |
| `/branch/findings` | Open / resolved / all inspection findings |
| `/branch/royalty` | Last 24 royalty invoices for the branch |
| `/branch/fees` | Last 90 days fee invoices + outstanding totals |

Branch resolution: `Employee.user_id == frappe.session.user` → `Employee.mys_branch`. Branch staff only (Director / Principal / Admin / Accountant / Campus Incharge).

**Local smoke:** `bench --site SITE execute myschools.scripts.seed_portal_branch.main`

**Desk verify:** `bench --site SITE execute myschools.scripts.verify_branch_desk_cards.run`

**HTTP battery:** `cd frappe-bench && ./env/bin/python -c "from myschools.scripts.verify_http_battery import run; run()"`

## Phase 9 — Teacher portal 🟡

Branch: `feature/phase-9-teacher-portal`.

| Route | Purpose |
|---|---|
| `/teacher` | Dashboard: class count + this week's schedule summary |
| `/teacher/classes` | Student groups assigned to the instructor |
| `/teacher/class?group=` | Branch-scoped class roster |
| `/teacher/schedule` | Next 14 days `Course Schedule` rows |

Scope: `Employee.user_id` → `Instructor` → `Student Group Instructor` child rows. Roster students filtered to `Employee.mys_branch`.

**Local smoke:** `bench --site SITE execute myschools.scripts.seed_portal_teacher.main`

## Phase 7d — Inspection portal (in flight)

Branch: `feature/phase-7d-inspection-portal`.

| Route | Purpose |
|---|---|
| `/inspection` | Dashboard: open findings + recent visits |
| `/inspection/visits` | Visits list (cluster-scoped) |
| `/inspection/visit?name=` | Draft checklist runner (apply template, save results, submit) |
| `/admission-enquiry` | Public admission form → `MYS Communication Log` |

Inspectors: Academic Monitor, Audit Officer (cluster-scoped via `Employee.mys_branch` → cluster branches).

**Local smoke:** `bench --site SITE execute myschools.scripts.seed_portal_inspection.main`

## Adding a new portal page

1. Add `www/<route>/index.py` with `get_context` (auth + `context.no_cache = 1`).
2. Add `index.html` extending `templates/pages/mys_portal_base.html`.
3. Extend `PORTAL_ROUTE_BY_ROLE` in `api/portal.py` if it is a new role landing.
4. Ship tests in `tests/test_portal_shell.py` or a slice-specific module + HTTP smoke.
