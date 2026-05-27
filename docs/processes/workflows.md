# Process: Workflows & List View polish

*Audience: anyone adding a new state to an existing workflow, gating a
transition by a different role, or debugging "why can't this user advance
this Finding past Open?"*

Phase 5 converts the ad-hoc `status` enums on `MYS Inspection Finding` and
`MYS Royalty Invoice` into formal **Frappe Workflows** with role-gated
transitions. List- and form-JS layered on top surface the right badges and
shortcut buttons without users having to know which workflow action moves
which state.

> **Fixtures**: [`myschools/fixtures/workflow.json`](../../frappe-bench/apps/myschools/myschools/fixtures/workflow.json) ·
> [`myschools/fixtures/workflow_state.json`](../../frappe-bench/apps/myschools/myschools/fixtures/workflow_state.json) ·
> [`myschools/fixtures/workflow_action_master.json`](../../frappe-bench/apps/myschools/myschools/fixtures/workflow_action_master.json) ·
> **Source of truth**: [`myschools/scripts/build_workflows.py`](../../frappe-bench/apps/myschools/myschools/scripts/build_workflows.py) ·
> **Tests**: [`myschools/tests/test_workflows.py`](../../frappe-bench/apps/myschools/myschools/tests/test_workflows.py)

---

## 1. What ships

### 1.1 Two Workflows

| Workflow                            | Doctype                | State field | States                                              |
| ----------------------------------- | ---------------------- | ----------- | --------------------------------------------------- |
| `MYS Inspection Finding Workflow`   | MYS Inspection Finding | `status`    | Draft → Open → In Progress → Resolved → Verified (+ Cancelled) |
| `MYS Royalty Invoice Workflow`      | MYS Royalty Invoice    | `status`    | Draft → Unpaid (+ Partial / Paid / Overdue / Cancelled, set via `db.set_value`) |

Both bind to the existing `status` field rather than introducing a new
`workflow_state` column, so all downstream code (`permission_query_conditions`,
list filters, controller validation) keeps reading `status` and is unaware
the field is now workflow-driven.

### 1.2 Inspection Finding transitions

| From         | Action            | To           | Allowed roles                          |
| ------------ | ----------------- | ------------ | -------------------------------------- |
| Draft        | Submit            | Open         | Audit Officer, Branch Director, Branch Principal |
| Open         | Acknowledge       | In Progress  | Branch Director, Branch Principal       |
| In Progress  | Mark Resolved     | Resolved     | Branch Director, Branch Principal       |
| Resolved     | Verify            | Verified     | **Audit Officer only**                  |
| Resolved     | Reject Resolution | In Progress  | **Audit Officer only**                  |
| Open         | Cancel            | Cancelled    | Audit Officer                           |

The asymmetry — anyone in the branch can raise / acknowledge / resolve, but
only an Audit Officer can sign off Verified — is the whole point of putting
this on a workflow rather than leaving it on a free-form Select field.

### 1.3 Royalty Invoice transitions

| From    | Action  | To        | Allowed roles                       |
| ------- | ------- | --------- | ----------------------------------- |
| Draft   | Submit  | Unpaid    | HO Dept Head, Branch Accountant     |
| Unpaid  | Cancel  | Cancelled | Chief Executive, HO Dept Head       |
| Partial | Cancel  | Cancelled | Chief Executive                     |
| Overdue | Cancel  | Cancelled | Chief Executive                     |

**Payment-driven states (Partial / Paid / Overdue) are not reached via
workflow.** When a `MYS Royalty Payment` is submitted, the invoice
controller's `_refresh_status` calls `frappe.db.set_value` to update
`status` — that path bypasses workflow validation by design. A regression
test pins this behaviour: see
`TestRoyaltyWorkflowBypass::test_db_set_status_bypasses_workflow`.

### 1.4 List-view polish

- `mys_inspection_finding_list.js` — severity badges (Critical=red,
  Major=orange, Minor=grey) + status indicators.
- `mys_royalty_invoice_list.js` — status indicators (Unpaid=orange,
  Partial=blue, Paid=green, Overdue=red, Cancelled=grey).
- `mys_inspection_visit_list.js` — docstatus-based indicator (the Visit
  doctype itself has no `status` field yet — see "Deferred work" below).

### 1.5 Form actions

- **Finding form** — "Create Corrective Action" button on Open / In Progress
  Findings (the workflow itself provides Acknowledge / Mark Resolved /
  Verify / Reject Resolution / Cancel via the standard menu).
- **Royalty Invoice form** — "Send Reminder" button when the invoice is
  Overdue (or Unpaid past `due_date`). Calls
  `myschools.api.royalty.send_overdue_reminder` which renders the
  "MYS - Royalty Invoice Overdue" Email Template against the document and
  sends it to the franchisee's email immediately.

---

## 2. How to change a workflow

**Never edit the fixture JSON by hand.** The fixtures are regenerated from
[`scripts/build_workflows.py`](../../frappe-bench/apps/myschools/myschools/scripts/build_workflows.py).

To add a new state or transition:

1. Edit `build_workflows.py`.
2. Run `bench --site myschools.localhost execute myschools.scripts.build_workflows.main`.
   This rewrites the three fixture files.
3. Run `bench --site myschools.localhost migrate` to pick up the changes
   into the local DB.
4. Run `bench --site myschools.localhost execute myschools.scripts._smoke_inspect_workflows.main`
   to print the resulting state machine and visually confirm.
5. Add or update tests in
   [`tests/test_workflows.py`](../../frappe-bench/apps/myschools/myschools/tests/test_workflows.py).
6. Commit the **fixture JSONs and the script** together.

---

## 3. Critical Frappe behaviours you'll hit

### 3.1 `update_after_submit` skips `validate()`

When a submitted document is saved (e.g. an apply_workflow transition that
moves Open → In Progress), Frappe runs `before_update_after_submit` instead
of `validate`. The `MYS Inspection Finding` controller wires both paths to
the same private `_validate_resolution_state` helper so the "Verified
requires resolution_notes" guard still fires post-submit. If you add a
controller guard that needs to fire on workflow transitions, you must do
the same:

```python
def validate(self):
    self._guard()

def before_update_after_submit(self):
    self._guard()
```

### 3.2 `allow_on_submit: 1` is mandatory for workflow-touched fields

If your workflow drives a field whose value should change after the doc is
submitted (typically the state field, plus any companion fields like
`resolved_on` or `resolution_notes`), set `allow_on_submit: 1` in the
DocType JSON. Without it Frappe raises `UpdateAfterSubmitError` and the
workflow transition fails opaquely.

### 3.3 `db.set_value` bypasses workflow validation

This is a feature, not a bug. The Royalty Invoice payment auto-flip
relies on it: `_refresh_status` walks payment rows and calls
`frappe.db.set_value("MYS Royalty Invoice", name, "status", "Paid")`
without going through `doc.save()`. The workflow's transition rules are
not consulted, which is exactly what we want — there is no operator
"Mark Paid" button, the state flips when the money arrives.

If you ever need to enforce workflow rules on a `db.set_value` path,
move the call back to `doc.set("status", X); doc.save()`.

### 3.4 `WorkflowTransitionError` vs `WorkflowPermissionError`

Both inherit from `frappe.ValidationError`, but they fire for different
reasons:

- `WorkflowTransitionError` — the requested action isn't a valid transition
  from the current state for **any** of the user's roles. This is what a
  user with no MYS roles trying to Submit a Finding sees.
- `WorkflowPermissionError` — the action exists for the current state but
  the user doesn't have the gating role. This is what a Branch Director
  trying to Verify a Finding sees.

Tests asserting "user X cannot perform action Y" should accept both, since
which one fires depends on subtle session-state details:

```python
self.assertRaises((WorkflowPermissionError, WorkflowTransitionError))
```

---

## 4. Verification

### 4.1 Local

```bash
# Workflow definitions imported and active
bench --site myschools.localhost execute myschools.scripts._smoke_inspect_workflows.main

# Full state-machine walk (Draft -> Verified)
bench --site myschools.localhost execute myschools.scripts._smoke_workflow_e2e.main

# Unit + integration tests
bench --site myschools.localhost run-tests --app myschools --module myschools.tests.test_workflows
bench --site myschools.localhost run-tests --app myschools  # full suite, 74 pass
```

### 4.2 Browser (automated)

The browser pass is automated via Playwright — no manual click-through
is required. From `frappe-bench/apps/myschools/`:

```bash
# One-time per machine: install deps + the Chromium browser binary
npm install
npm run test:e2e:install

# Seed deterministic test data (users + Resolved finding + Overdue invoice)
bench --site myschools.localhost execute myschools.scripts.seed_e2e.main

# Run the spec
npm run test:e2e   # all 6 cases must pass
```

[`tests/e2e/workflows.spec.ts`](../../frappe-bench/apps/myschools/tests/e2e/workflows.spec.ts)
exercises what unit tests can't: that the Frappe desk actually *renders*
the workflow menu and the form-JS custom buttons for the right roles.
It catches DOM-level regressions (missing Workflow State records, JS
errors that blank the form) that backend tests are blind to.

### 4.3 Workflow State records — easy-to-miss gotcha

Every `state` referenced in `workflow.json` (including `Draft` and
`Cancelled`) must have a matching record in
[`workflow_state.json`](../../frappe-bench/apps/myschools/myschools/fixtures/workflow_state.json).
Frappe ships `Pending`/`Approved`/`Rejected` as defaults but **not**
`Draft` or `Cancelled`. If the records are missing, unit tests still
pass (they call `apply_workflow` which doesn't validate state-record
existence) but the form shows a blocking "Workflow State X not found"
modal on first open — the Playwright suite catches this; CLI tests
do not.

---

## 5. Deferred work

- **`MYS Inspection Visit` workflow.** Visit currently has no `status`
  field — only `visit_type` (Routine/Surprise/Follow-up) and
  `is_submittable: 1`. Adding a workflow requires first adding the field
  via doctype migration, which is a separate small PR.
- **Royalty Invoice manual Mark Paid.** Today the only path to Paid is via
  a submitted MYS Royalty Payment. If finance needs to record a
  reconciliation correction without a payment row, add a workflow action
  later — bigger UX decision than this PR's scope.
