# API: `myschools.api.royalty`

Function reference for the royalty module.

> **Source**: [`api/royalty.py`](../../frappe-bench/apps/myschools/myschools/api/royalty.py) ·
> **Process**: [royalty-billing.md](../processes/royalty-billing.md) ·
> **Doctypes**: [data-model.md §2](../data-model.md#2-royalty)

---

## Public functions

### `resolve_royalty_rate(agreement, branch, campus=None, on_date=None) → (rate, source)`

Resolves the effective royalty rate for a billing event.

**Parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `agreement` | `str` | yes | name of a `MYS Franchise Agreement` |
| `branch` | `str` | yes | name of a `MYS Branch` |
| `campus` | `str` or `None` | no | name of a `MYS Campus`; `None` skips campus lookup |
| `on_date` | `date`, `datetime`, str, or `None` | no | defaults to today |

**Returns**

`(rate_percent: float, source: str)` where `source` is one of:

- `"campus_override"` — a matching `MYS Royalty Rate Override` with the
  exact `(agreement, branch, campus)` is active on `on_date`.
- `"branch_override"` — a matching override with that `(agreement, branch)`
  and `campus IS NULL` is active.
- `"agreement_default"` — neither override matched; falls back to
  `MYS Franchise Agreement.default_royalty_rate`.

**Notes**

- Effective-date gating: an override matches only if `effective_from ≤ on_date`,
  `is_active = 1`, and (if set) `effective_to ≥ on_date`.
- The function ignores cancelled / draft agreements — caller's responsibility
  to pass an Active agreement.
- The most recent `effective_from` wins when multiple overrides match. This
  is enforced by `order_by effective_from DESC limit 10`.

**Example**

```python
from myschools.api.royalty import resolve_royalty_rate

rate, src = resolve_royalty_rate(
    agreement="MYS-FA-BR014-2026-0001",
    branch="BR014",
    campus="BR014-Junior",
    on_date="2026-05-31",
)
# → (5.0, "campus_override")
```

---

### `get_branch_collection_for_period(branch, year, month) → {campus: amount}`

Sums submitted `Fees` (Frappe Education) for a branch over a month, grouped
by `student.mys_campus`.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `branch` | `str` | name of a `MYS Branch` |
| `year` | `int` | e.g. `2026` |
| `month` | `int` | `1..12` |

**Returns**

`dict[str, float]` mapping campus name → total `grand_total` of submitted
Fees in the period.

If the `Fees` table doesn't exist (fresh install before any fee records),
returns `{}`.

**SQL**

Filters: `student.mys_branch = ?`, `fees.docstatus = 1`,
`fees.posting_date BETWEEN first_of_month AND last_of_month`.

---

### `generate_monthly_royalty_invoices(year=None, month=None, dry_run=False) → list[dict]`

The headline routine: generate (or preview) royalty invoices for every Active,
submitted `MYS Franchise Agreement` for the given period.

**Parameters**

| Name | Type | Default | Description |
|---|---|---|---|
| `year` | `int` or `None` | previous month's year | |
| `month` | `int` or `None` | previous month | |
| `dry_run` | `bool` | `False` | if true, runs `validate()` on the invoice but doesn't insert |

**Returns**

A list of result dicts, one per agreement processed. Possible shapes:

```python
# created
{"agreement": "MYS-FA-BR014-...", "branch": "BR014", "invoice": "MYS-RI-...",
 "royalty_amount": 415000.0, "effective_rate": 6.38}

# skipped (already invoiced)
{"agreement": "...", "skipped": "already_exists", "invoice": "MYS-RI-..."}

# skipped (no campuses)
{"agreement": "...", "skipped": "no_campuses"}

# dry_run preview
{"agreement": "...", "branch": "...", "total_collection": 6500000,
 "royalty_amount": 415000, "effective_rate": 6.38, "would_create": True}
```

**Behaviour**

1. Resolves the target period (defaults to previous month so the scheduled
   job runs cleanly on day 1).
2. Pulls every `MYS Franchise Agreement` with `status = "Active"` and
   `docstatus = 1`.
3. For each:
   - Skips if a `MYS Royalty Invoice` already exists for
     `(agreement, period_year, period_month)` with `docstatus < 2`.
   - Loads collections via `get_branch_collection_for_period`.
   - Loads campuses for the branch; skips if there are none.
   - Builds a `MYS Royalty Invoice` (draft):
     - Header: `agreement`, `franchisee`, `branch`, `company`, `period_*`,
       `invoice_date = today`, `due_date = today + grace_days` (default 10),
       `auto_generated = 1`, `generated_by = session.user`.
     - Campus lines: one per campus, with `collection_amount` from the
       Fees rollup and `rate_percent / rate_source` from
       `resolve_royalty_rate` on the **billing_date** (last day of the period).
   - Inserts (unless `dry_run`).
4. Commits after the loop.

**Triggering it manually**

```bash
# previous month
bench --site myschools.localhost execute \
  "myschools.api.royalty.generate_monthly_royalty_invoices"

# specific period
bench --site myschools.localhost execute \
  "myschools.api.royalty.generate_monthly_royalty_invoices" \
  --kwargs "{'year': 2026, 'month': 5}"

# dry-run / preview
bench --site myschools.localhost execute \
  "myschools.api.royalty.generate_monthly_royalty_invoices" \
  --kwargs "{'year': 2026, 'month': 5, 'dry_run': True}"
```

---

### `scheduled_monthly_royalty_run() → None`

The thin wrapper invoked by the scheduler. Calls
`generate_monthly_royalty_invoices()` with no args (so it bills the previous
month) and logs the results. Exceptions are logged to the error log via
`frappe.log_error` and then re-raised so the scheduler marks the job failed.

**Cron**: `0 3 1 * *` (03:00 PKT on day 1 of every month). Registered in
[`hooks.py`](../../frappe-bench/apps/myschools/myschools/hooks.py) under
`scheduler_events.cron`.

---

## Permission query functions

These return SQL `WHERE` fragments that Frappe appends to list/report queries
for the relevant DocType. All four follow the same pattern:

- If the user has a **global** role (System Manager / Administrator /
  Chief Executive / HO Dept Head), return `""` (no filter).
- If the user has **none** scope, return `<doctype>.branch = '__none__'`
  (returns zero rows).
- Otherwise, return `<doctype>.branch IN (...)` with the user's branches
  (one branch for branch-tier users, all cluster branches for cluster-tier).

User scope resolution lives in
[`api/permissions.py`](../../frappe-bench/apps/myschools/myschools/api/permissions.py) `_user_scope(user)`.

| Function | DocType | Wired in `hooks.py` as |
|---|---|---|
| `royalty_invoice_query(user)` | `MYS Royalty Invoice` | `permission_query_conditions."MYS Royalty Invoice"` |
| `royalty_payment_query(user)` | `MYS Royalty Payment` | `... "MYS Royalty Payment"` |
| `franchise_agreement_query(user)` | `MYS Franchise Agreement` | `... "MYS Franchise Agreement"` |
| `rate_override_query(user)` | `MYS Royalty Rate Override` | `... "MYS Royalty Rate Override"` |

---

## Private helpers

### `_lookup_override(agreement, branch, campus, on_date) → float | None`

Internal — finds the most recent active `MYS Royalty Rate Override` matching
the inputs, checks `effective_to` boundary, returns `rate_percent` or `None`.
Called from `resolve_royalty_rate`.
