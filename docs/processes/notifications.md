# Process: Notifications & Communication Log

*Audience: anyone wiring a new alert/reminder, adding a channel (SMS/WhatsApp),
or debugging "why didn't the franchisee get an email when X happened?"*

The notification layer turns the franchise data engine into something operators
actually use day-to-day: when a royalty invoice is generated, when a finding is
assigned, when an agreement is about to expire, the right humans get pinged —
and every system-generated email is mirrored into one audit log
(`MYS Communication Log`) so HO admins don't have to trawl Frappe's
`Communication` doctype.

> **Fixtures**: [`myschools/fixtures/email_template.json`](../../frappe-bench/apps/myschools/myschools/fixtures/email_template.json) · [`myschools/fixtures/notification.json`](../../frappe-bench/apps/myschools/myschools/fixtures/notification.json) ·
> **Source of truth**: [`myschools/scripts/build_notifications.py`](../../frappe-bench/apps/myschools/myschools/scripts/build_notifications.py) ·
> **API helpers**: [`myschools/api/notifications.py`](../../frappe-bench/apps/myschools/myschools/api/notifications.py) ·
> **Tests**: [`myschools/tests/test_notifications.py`](../../frappe-bench/apps/myschools/myschools/tests/test_notifications.py)

---

## 1. What ships

### 1.1 Six Email Template + Notification pairs

Each row below is **one Email Template + one Notification** that share the same
subject + HTML body. The Email Templates also stand alone — operators can
manually fire any of them from the desk's "Send Email" dialog.

| Name                              | Doctype                   | Event       | Triggered when                                          | Recipients                                                       |
| --------------------------------- | ------------------------- | ----------- | ------------------------------------------------------- | ---------------------------------------------------------------- |
| MYS - Royalty Invoice Generated   | `MYS Royalty Invoice`     | Submit      | `doc.docstatus == 1`                                    | Chief Executive, HO Dept Head, Branch Director, Branch Accountant |
| MYS - Royalty Invoice Overdue     | `MYS Royalty Invoice`     | Days After  | 1 day after `due_date`, status ∈ Unpaid/Partial/Overdue | Chief Executive, HO Dept Head, Branch Director, Branch Accountant |
| MYS - Inspection Finding Assigned | `MYS Inspection Finding`  | Submit      | on submit                                               | Branch Director, Branch Principal, Audit Officer + `reported_by` |
| MYS - Inspection Finding Overdue  | `MYS Inspection Finding`  | Days After  | 1 day after `due_date`, status ∈ Open/In Progress       | Branch Director, Branch Principal, Audit Officer                 |
| MYS - Corrective Action Overdue   | `MYS Corrective Action`   | Days After  | 1 day after `due_date`, status ∈ Planned/In Progress    | Branch Director, Branch Principal + `assigned_to`                |
| MYS - Franchise Agreement Expiring | `MYS Franchise Agreement` | Days Before | 30 days before `end_date`, status `Active`              | Chief Executive, HO Dept Head, Branch Director                   |

All templates inherit the MY Schools palette (primary `#0F7A4A`) and pull
context from the document itself via Jinja (`{{ doc.invoice_number }}`,
`{{ doc.branch }}`, etc.).

### 1.2 MYS Communication Log mirroring

The custom `Communication` `after_insert` hook
([`hooks.py:51-53`](../../frappe-bench/apps/myschools/myschools/hooks.py#L51-L53))
mirrors **outbound, system-generated emails tied to an MYS doctype (or Fees)**
into `MYS Communication Log`. The rule set in
[`api/notifications.log_outbound_email`](../../frappe-bench/apps/myschools/myschools/api/notifications.py):

- `communication_type == "Communication"` (no automated bounces, no comments)
- `sent_or_received == "Sent"` (no inbound mail)
- `reference_doctype` starts with `MYS ` **or** equals `Fees`

Everything else (inbound mail, non-MYS references, drafts) is skipped — Frappe's
own `Communication` doctype already captures those, and we don't want the audit
log to double up.

The mirror resolves the referenced doc's `branch` / `campus` automatically, so
the log row carries the franchise context (and `scope` is set to `Branch` when
a branch is found, `Individual` otherwise).

### 1.3 SMS / email adapters (Phase 8c)

`MYS SMS Settings` (single) selects the active SMS provider:

| Provider | Gateway key | Behaviour |
| -------- | ----------- | --------- |
| Stub (default) | `stub` | Log-only — no HTTP call |
| Twilio | `twilio` | REST API via Account SID + Auth Token |
| HTTP Gateway | `http` | POST/GET to a vendor URL (Jazz / Easypaisa / custom) |
| Frappe SMS Settings | `frappe-sms` | Delegates to core `SMS Settings` |

`api/notifications.send_sms(recipient, message, doctype=None, name=None)` routes
through `api/sms_providers.dispatch_sms`, writes `MYS Communication Log` with
`gateway`, `recipient_phone`, and `provider_reference`, and returns
`{ok, log, gateway, reference}`. Failed dispatches log `status=Failed` then throw.

`api/notifications.send_email_message(recipient, subject, message, …)` sends via
`frappe.sendmail` and logs `gateway=frappe-email`. Notification-fired emails
continue to mirror through `log_outbound_email` with the same gateway field.

---

## 2. How an alert actually fires

Frappe's `Notification` doctype is condition-based: on every triggering event
(Submit / Days After / Days Before / etc.) it evaluates the row's Python
`condition` against the document, and if truthy, renders the Jinja `message`
and sends to each `Notification Recipient` row.

```
        ┌─────────────────────┐
        │  Doc event fires    │   e.g. MYS Royalty Invoice.submit
        └──────────┬──────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ Notification matches │   document_type + event match,
        │   + condition true   │   condition Python evaluates truthy
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  Recipients resolved │   receiver_by_role  → all users w/ that role
        │                      │   receiver_by_document_field → doc.<field>
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  frappe.sendmail     │   Communication row written → after_insert
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────────────┐
        │ log_outbound_email mirrors   │   only if ref doctype is MYS or Fees
        │ into MYS Communication Log   │
        └──────────────────────────────┘
```

For `Days After` / `Days Before` events, Frappe's hourly scheduler scans
matching docs and fires the notification — no extra cron needed from us.

---

## 3. How to add a new alert

The single source of truth is
[`scripts/build_notifications.py`](../../frappe-bench/apps/myschools/myschools/scripts/build_notifications.py).
**Never** hand-edit the JSON fixtures — they're regenerated wholesale.

1. Add a dict to the `NOTIFICATIONS` list in the builder. Fields:
   - `name` — `"MYS - <Human Title>"`
   - `doctype` — the doc type the alert is tied to
   - `event` — `Submit` / `Days After` / `Days Before` / `Value Change` / etc.
   - `subject` — Jinja-templated, mirrored to both Email Template and Notification
   - `body_paragraphs` — list of HTML paragraphs (the builder wraps them in the
     standard MYS-branded container)
   - `condition` — Python expression evaluated against `doc`
   - `recipients_roles` and/or `recipients_doc_fields`
   - Optional: `date_changed`, `days_in_advance`, `attach_print`
2. Regenerate fixtures:
   ```bash
   cd frappe-bench
   bench --site myschools.localhost execute myschools.scripts.build_notifications.main
   ```
   This rewrites `fixtures/email_template.json` and `fixtures/notification.json`.
3. Add an entry to `EXPECTED_NAMES` and `EXPECTED_NOTIFICATION_META` in
   `tests/test_notifications.py` so the fixture-import tests cover it.
4. Migrate locally: `bench --site myschools.localhost migrate` — the new
   Notification + Email Template are upserted.
5. Smoke-test: trigger the underlying doc event and verify the email lands +
   the mirror row appears in `MYS Communication Log`.

---

## 4. Why mixed-mode recipients

`MYS - Inspection Finding Assigned` is the canonical example: it pings three
**roles** (Branch Director, Branch Principal, Audit Officer) *and* the specific
user named in the doc's `reported_by` field. Two `Notification Recipient` rows
on the same Notification — one with `receiver_by_role`, one with
`receiver_by_document_field` — handle both. This pattern shows up wherever
"the right operators for that tier" + "the one human who's owning this item"
both need to know.

---

## 5. Why the audit-log mirror lives outside Frappe's `Communication`

Frappe's `Communication` doctype already stores every outbound email — so why
duplicate? Three reasons:

1. **Franchise-scoped queries.** `MYS Communication Log` carries `branch` /
   `campus` / `scope` columns, so a Branch Director can filter to "everything
   the system has ever sent about my branch" with a single list view filter.
   `Communication` doesn't have those columns.
2. **Cross-channel audit.** Email, SMS, and (Phase 8) WhatsApp / push all land
   in the same table with a `channel` column. One audit query covers them all.
3. **Permission isolation.** `MYS Communication Log` is permission-scoped to
   the MYS roles via the same `permission_query_conditions` pattern; the
   underlying `Communication` doctype isn't.

---

## 6. What's intentionally not here yet

- **Real SMS gateway.** Stub today; Phase 8 plugs in Jazz / Easypaisa / Twilio
  behind the same `send_sms()` signature.
- **WhatsApp / Push.** The `channel` column on `MYS Communication Log` already
  accepts `WhatsApp` and `Push`, but no adapters ship yet.
- **Per-branch role routing.** Today notifications fire to *all* users with a
  given role globally. Per-branch filtering (Branch Director of THIS branch
  only) is a Phase 8 enhancement — Frappe's `Notification Recipient` doesn't
  support it natively, so it'll need a `Method`-event Notification calling a
  helper that resolves "users with this role + access to this doc's branch."

---

## 7. Quick troubleshooting

| Symptom                                          | Likely cause / fix                                                                                              |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| Notification didn't fire on Submit               | Check `condition` evaluates truthy against the doc (`doc.docstatus`, `doc.status`); test in `bench console`.   |
| Days-After overdue never triggers                | Frappe runs the scheduler hourly. Check `bench --site … scheduler resume` and `bench schedule` background log. |
| Email went out but no mirror in Communication Log | `reference_doctype` on the Communication is missing or not an MYS doctype. Check what `frappe.sendmail` passed. |
| New alert fired twice                            | Both `New` and `Save` events match on first insert. Use `Submit` for submittable docs, or `Value Change`.       |
| Manual "Send Email" doesn't see the template     | Email Template `enabled=1`? Frappe's UI also filters by language; templates ship as `en`.                       |
