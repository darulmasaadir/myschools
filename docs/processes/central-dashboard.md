# Central Monitoring Dashboard

The **MYS Central Monitoring** dashboard is a single role-aware dashboard at
[`/app/dashboard-view/MYS Central Monitoring`](/app/dashboard-view/MYS%20Central%20Monitoring). It
ships with the app as JSON fixtures, so every install gets it on `bench migrate` — no manual
seeding step.

There is only one dashboard for everyone. A Branch Admin and the Chief Executive open the same
URL and see the same eight cards and three charts; what differs is the **scope** of the rows
behind each tile. Branch scoping is handled by Frappe's `permission_query_conditions` registered
in [`hooks.py`](../../frappe-bench/apps/myschools/myschools/hooks.py), so document-type cards
auto-filter; custom-method cards apply `_branch_scope_sql` directly.

## Tiles

### Number cards

| Card | Source | Card type |
|---|---|---|
| Active Branches | `MYS Branch` count where `is_active=1` | Document Type |
| Active Students | `Student` count where `enabled=1` | Document Type |
| Outstanding Royalty | Sum of `MYS Royalty Invoice.outstanding_amount` (submitted) | Document Type |
| Overdue Invoices | Count of `MYS Royalty Invoice` with `status="Overdue"` | Document Type |
| This Month — Royalty Invoiced | Sum of `royalty_amount` for current period | Custom method |
| This Month — Fees Collected | Sum of `Fees.grand_total` for current month (joined via `Student.mys_branch`) | Custom method |
| Open Inspection Findings | Count of `MYS Inspection Finding` with status in (Open, In Progress) | Document Type |
| Overdue Inspection Findings | Count of unresolved findings past `due_date` | Custom method |

### Charts

| Chart | Type | Source |
|---|---|---|
| Royalty Invoiced Trend (12m) | Line (Sum, Monthly) | `MYS Royalty Invoice.royalty_amount` over the last year |
| Royalty by Cluster (YTD) | Bar (Group By Sum) | `MYS Royalty Invoice` grouped by `cluster` (fetched from `branch.cluster`) |
| Findings by Severity | Donut (Group By Count) | `MYS Inspection Finding` grouped by `severity`, excluding Resolved/Verified |

## File layout

Frappe scans these specific paths on `bench migrate` (via
[`frappe.utils.dashboard.sync_dashboards`](../../frappe-bench/apps/frappe/frappe/utils/dashboard.py)):

```
myschools/my_school_erp/
├── my_school_erp_dashboard/          # NB: folder is <module_slug>_dashboard, not "dashboard"
│   └── mys_central_monitoring/
│       └── mys_central_monitoring.json
├── dashboard_chart/
│   ├── mys_findings_by_severity/
│   ├── mys_royalty_by_cluster_ytd/
│   └── mys_royalty_invoiced_trend_12m/
└── number_card/
    ├── mys_active_branches/
    ├── mys_active_students/
    ├── mys_open_findings/
    ├── mys_outstanding_royalty/
    ├── mys_overdue_findings/
    ├── mys_overdue_invoices/
    ├── mys_this_month_fees_collected/
    └── mys_this_month_royalty_invoiced/
```

Each card / chart / dashboard is shipped with `"is_standard": 1`. That's why these must be JSON
fixtures rather than created programmatically — Frappe blocks creating standard dashboard
objects outside `developer_mode`.

## Custom-method endpoints

Three Number Cards have `type="Custom"` because their queries either need joins or branch
scoping that the standard Number Card filter can't express. They live in
[`myschools/api/dashboard.py`](../../frappe-bench/apps/myschools/myschools/api/dashboard.py):

- `current_month_royalty_invoiced()` — sum of `royalty_amount` for the active period,
  scoped via `_branch_scope_sql("branch")`.
- `current_month_fees_collected()` — sum of `Fees.grand_total` for the current month, joined
  through `Student.mys_branch` to apply the user's franchise scope.
- `overdue_findings_count()` — uses `frappe.db.count("MYS Inspection Finding", …)` so Frappe
  applies the permission query automatically.

All three return `{"value": <number>, "fieldtype": "Currency"|"Int", ["currency": "PKR"]}`.

## How scoping works

```
                  ┌──────────────────────────────────────────────┐
user opens ─────→ │ Dashboard "MYS Central Monitoring"            │
                  │ (same view for every role)                    │
                  └──────────────────────────────────────────────┘
                                       │
                  ┌────────────────────┴────────────────────┐
                  │                                          │
       ┌──────────▼─────────┐                  ┌────────────▼────────────┐
       │ Document Type card │                  │ Custom-method card      │
       │ (filters_json …)   │                  │ (api.dashboard.<fn>)    │
       └──────────┬─────────┘                  └────────────┬────────────┘
                  │                                          │
       Frappe applies                                _branch_scope_sql()
       permission_query_conditions                   adds AND branch IN (…)
       from hooks.py                                 (or returns DENY)
                  │                                          │
                  └────────────────┬─────────────────────────┘
                                   │
                          rows the user can see
```

## Tests

[`myschools/tests/test_dashboard.py`](../../frappe-bench/apps/myschools/myschools/tests/test_dashboard.py)
— 8 tests covering: dashboard exists, cards/charts wired correctly, every fixture imported,
custom-method cards point at the right whitelisted method, all three endpoints return
well-formed payloads.

Run them with:

```
bench --site myschools.localhost run-tests --app myschools --module myschools.tests.test_dashboard
```
