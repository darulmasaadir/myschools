# API: `myschools.api.inspection`

Function reference for the inspection module.

> **Source**: [`api/inspection.py`](../../frappe-bench/apps/myschools/myschools/api/inspection.py) ·
> **Process**: [inspection-workflow.md](../processes/inspection-workflow.md) ·
> **Doctypes**: [data-model.md §3](../data-model.md#3-inspection)

---

## Public functions

### `apply_template_to_visit(visit, template) → int`

Snapshots a `MYS Inspection Checklist Template`'s items into a draft visit's
`checklist_results` table.

**`@frappe.whitelist()` exposed** — callable via REST / from the Desk client.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `visit` | `str` | name of a `MYS Inspection Visit` (must be `docstatus = 0`) |
| `template` | `str` | name of a `MYS Inspection Checklist Template` (must be `is_active`) |

**Returns**

`int` — number of rows added.

**Behaviour**

1. Loads the visit; raises if `docstatus != 0` ("Cannot apply template to a
   submitted visit").
2. Loads the template; raises if `is_active` is false.
3. **Clears** `visit.checklist_results` — calling this twice replaces, doesn't append.
4. Copies each item with snapshot fields:
   `item_text`, `category`, `severity`, `weight`, `max_score`. The
   inspector's fields (`result`, `score`, `notes`, `photo`) are left blank.
5. Sets `visit.checklist_template = template`.
6. Saves.

**Why snapshot?** A later revision of the template must not rewrite historical
visits. The snapshot is the visit's permanent record of "what was on the
checklist that day."

**Examples**

```bash
bench --site myschools.localhost execute \
  "myschools.api.inspection.apply_template_to_visit" \
  --kwargs "{'visit': 'INSP-2026-0017', 'template': 'CKT-Routine-0003'}"
```

```javascript
// from the Desk client
frappe.call({
  method: "myschools.api.inspection.apply_template_to_visit",
  args: { visit: cur_frm.doc.name, template: "CKT-Routine-0003" },
  callback: (r) => { cur_frm.reload_doc(); }
});
```

---

### `auto_create_findings_from_failed_results(visit) → list[str]`

Called from `MYS Inspection Visit.on_submit`. Creates one `MYS Inspection
Finding` per failed Critical/Major checklist item.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `visit` | `str` | name of the just-submitted visit |

**Returns**

`list[str]` of newly-created finding names. Empty list if findings already
exist for this visit (**idempotent**).

**Selection rules**

A checklist result row produces a finding only if:

- `row.result == "Fail"`, **and**
- `row.severity in ("Critical", "Major")`.

Minor failures are **deliberately skipped**. Inspectors should raise a manual
finding from the visit summary if a Minor item warrants follow-up — most
don't, and auto-creating them drowns the workflow.

**Created finding fields**

| Field | Value |
|---|---|
| `visit` | the visit |
| `branch`, `campus` | copied from visit |
| `severity`, `category` | copied from the failed row |
| `status` | `"Open"` |
| `description` | `f"{row.item_text}\n\nInspector notes: {row.notes or '(none)'}"` |
| `reported_on` | `visit.visit_date or today()` |
| `due_date` | `visit_date + 7d` (Critical) or **`+ 21d`** (Major) |

Findings are inserted with `ignore_permissions=True` — they need to be created
even if the visit submitter doesn't have direct insert rights on findings.

**Idempotency**

```python
existing = frappe.db.count("MYS Inspection Finding", {"visit": visit})
if existing:
    return []
```

A re-submit (cancel → amend → submit) on a visit that already has findings
**does not create more**. If the failed items have changed, decide manually
whether to invalidate the old findings.

---

## Permission query functions

Branch-scope filters wired into `hooks.py` under `permission_query_conditions`.
All three use the same internal helper `_scoped_query(doctype, field, user)`.

| Function | DocType | Returns |
|---|---|---|
| `finding_query(user)` | `MYS Inspection Finding` | `branch IN (…)` or `branch = '__none__'` |
| `corrective_action_query(user)` | `MYS Corrective Action` | `branch IN (…)` |
| `checklist_template_query(user)` | `MYS Inspection Checklist Template` | always `""` — templates are global reference data, no scope |

User scope resolution lives in
[`api/permissions.py`](../../frappe-bench/apps/myschools/myschools/api/permissions.py) `_user_scope(user)`.

---

## DocType controllers

API logic is split between this module and two DocType controllers — pointers
included here for completeness.

### `MYSInspectionVisit.validate`

[`my_school_erp/doctype/mys_inspection_visit/mys_inspection_visit.py`](../../frappe-bench/apps/myschools/myschools/my_school_erp/doctype/mys_inspection_visit/mys_inspection_visit.py)

- Validates that `campus.branch == visit.branch` when both are set.
- Calls `_compute_scores()` to recalculate `items_passed/failed/na`,
  `score_percent`, `weighted_score`. N/A items are excluded from the
  denominator. Recomputes on every save.

### `MYSInspectionVisit.on_submit`

Calls `auto_create_findings_from_failed_results(self.name)`.

### `MYSCorrectiveAction.validate`

[`my_school_erp/doctype/mys_corrective_action/mys_corrective_action.py`](../../frappe-bench/apps/myschools/myschools/my_school_erp/doctype/mys_corrective_action/mys_corrective_action.py)

- Auto-sets `completion_date` when status moves to Completed/Verified.
- When status flips to `Verified`:
  - Requires `verification_notes` (throws if missing).
  - Auto-stamps `verified_by = session.user` and `verified_on = today()` if
    unset.

### `MYSCorrectiveAction.on_update` — finding auto-flip

This is the key automation: when *every* Corrective Action linked to a finding
reaches `Verified`, the finding itself flips to `Verified`.

```python
def on_update(self):
    if self.status != "Verified":
        return
    open_actions = frappe.db.count(
        "MYS Corrective Action",
        {
            "finding": self.finding,
            "status": ["!=", "Verified"],
            "name": ["!=", self.name],
        },
    )
    if open_actions == 0:
        frappe.db.set_value("MYS Inspection Finding", self.finding, "status", "Verified")
```

Note the exclusion of `self.name` — without it the check sees its own
non-`Verified` previous state mid-transaction.

---

## Testing

All public functions are exercised by
[`myschools/tests/test_inspection.py`](../../frappe-bench/apps/myschools/myschools/tests/test_inspection.py)
— 9 integration tests covering:

- `apply_template_to_visit` snapshot fidelity and idempotency.
- Score math, including N/A skip.
- Branch/campus consistency validation.
- Auto-create scope (Critical/Major only) and idempotency.
- Corrective Action → Finding state machine (the auto-flip).
- Verification requires verification_notes.
