# Portals (Phase 7)

*Audience: Engineering — how MY School website portals are built and extended.*

## Constraint

Portals are **Frappe `www/` Jinja pages + Web Forms** inside the `myschools` app. No Vue/React SPA, no separate auth service. See [upgrade-safe-only](../../.cursor/rules/upgrade-safe-only.mdc).

## Phase 7a — foundations (shipped first)

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

## Phase 7b — Guardian portal content (in flight)

Branch: `feature/phase-7b-guardian-portal`.

| Route | Purpose |
|---|---|
| `/guardian` | My Children list |
| `/guardian/child?student=` | Child profile |
| `/guardian/fees` | Fee invoices + receipt download |
| `/guardian/attendance` | Last 90 days attendance |
| `/guardian-feedback` | Web Form → `MYS Communication Log` |

Data access lives in [`api/guardian_portal.py`](../../frappe-bench/apps/myschools/myschools/api/guardian_portal.py) — students are resolved via Education's **`Student Guardian`** child table on `Student` (not `Guardian.students`, which Education clears on save).

**Local HTTP smoke user:** `bench --site SITE execute myschools.scripts.seed_portal_guardian.main` → `mys-portal-smoke-guardian@test.local` / `mys-portal-smoke`.

## Later slices

- **7c** — Branch principal dashboard
- **7d** — Inspection checklist runner + admission enquiry Web Form

## Adding a new portal page

1. Add `www/<route>/index.py` with `get_context` (auth + `context.no_cache = 1`).
2. Add `index.html` extending `templates/pages/mys_portal_base.html`.
3. Extend `PORTAL_ROUTE_BY_ROLE` in `api/portal.py` if it is a new role landing.
4. Ship tests in `tests/test_portal_shell.py` or a slice-specific module + HTTP smoke.
