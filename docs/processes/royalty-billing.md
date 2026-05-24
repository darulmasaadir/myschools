# Process: Royalty Billing

*Audience: Branch Accountant, Cluster Director, HO Finance, anyone investigating
a disputed invoice.*

The monthly cycle that turns a branch's fee collection into a submitted royalty
invoice, a payment, and a settled ledger.

> **API reference**: [../api/royalty.md](../api/royalty.md) ·
> **Doctypes referenced**: [../data-model.md §2](../data-model.md#2-royalty)

---

## 1. Why this exists

Each franchisee pays a percentage of their monthly fee collection back to head
office. The rate isn't uniform — newer campuses get ramp-up discounts,
established branches negotiate flat-rate deals. Tracking that on spreadsheets
caused two recurring problems: (a) auditing a number meant re-deriving the rate
from email threads, and (b) franchisees disputed invoices because they couldn't
see *why* a particular rate applied.

Both are solved by storing the rate (and the *source* of the rate) on each
campus line of each invoice, locked at submission time.

---

## 2. The monthly cycle

```
[Day 1, 03:00 PKT]
   scheduled_monthly_royalty_run()
      │
      │ runs generate_monthly_royalty_invoices(year, month)
      │ defaults to PREVIOUS month
      │
      ↓
For every Active, submitted MYS Franchise Agreement:
   ┌─ skip if a MYS Royalty Invoice already exists for (agreement, period)
   │
   │ collections = sum of submitted Fees in that branch for the period,
   │              grouped by student.mys_campus
   │
   │ for each MYS Campus under the branch:
   │     rate, source = resolve_royalty_rate(agreement, branch, campus, billing_date)
   │     append a MYS Royalty Invoice Campus Line:
   │         { campus, campus_type, collection_amount, rate_percent, rate_source }
   │
   └─ insert (DRAFT) MYS Royalty Invoice
```

The invoice is inserted as a **draft** — totals are computed, but nothing is
posted to the ledger yet. Submission is a human action so HO Finance can
sanity-check before locking the period.

---

## 3. Rate resolution

When the generator computes a campus line, it calls `resolve_royalty_rate`.
Resolution order on the billing date:

```
                  ┌──────────────────────────────┐
billing date ───→ │ campus override (matching     │ ─ found ──→ campus_override
                  │  agreement+branch+campus,     │
                  │  effective range, is_active)? │
                  └──────────┬───────────────────┘
                             │ not found
                             ↓
                  ┌──────────────────────────────┐
                  │ branch override (campus=null) │ ─ found ──→ branch_override
                  └──────────┬───────────────────┘
                             │ not found
                             ↓
                  ┌──────────────────────────────┐
                  │ agreement.default_royalty_rate│ ────────→ agreement_default
                  └──────────────────────────────┘
```

Each `MYS Royalty Rate Override` has `effective_from`, optional `effective_to`,
and `is_active`. Overrides can be **scheduled ahead of time** (just set
`effective_from` to a future date) and **retired without losing history** (set
`effective_to` or flip `is_active` off — historical invoices keep the rate
they had at submission).

### Example: BR014 in May 2026

```
Agreement MYS-FA-BR014-2026-0001 (default 7%):

  BR014-Kids     1,500,000  @ 7%  →  105,000     (agreement_default)
  BR014-Junior   2,000,000  @ 5%  →  100,000     (campus_override; ramp-up)
  BR014-Senior   3,000,000  @ 7%  →  210,000     (agreement_default)
                                    ---------
  Total collection                  6,500,000
  Total royalty                       415,000
  Effective weighted rate              6.38%
```

The 6.38% effective rate is stored on the invoice header (`applicable_rate`),
but the underlying mix is auditable from the campus lines.

---

## 4. Roles & actions

| Role | Can | Can't |
|---|---|---|
| **Branch Accountant** | View draft + submitted invoices for their branch; record payments | Submit, edit rates, edit overrides |
| **Cluster Director** | View invoices for every branch in their cluster | Submit, edit rates |
| **Branch Director** | View their branch's invoices and payments | Edit submitted invoices |
| **HO Finance / Chief Executive** | Submit invoices; create/edit overrides; manage agreements | — |
| **System Manager / Administrator** | Everything | — |

Branch scoping is enforced at the query layer
(see [royalty_invoice_query](../api/royalty.md#royalty_invoice_query) etc.),
so a Branch Accountant *literally cannot list* another branch's invoices,
even if they know the URL.

---

## 5. Submitting an invoice

1. Open the draft invoice (`MYS-RI-<branch>-<YYYYMM>`).
2. Review the **campus lines** — for each line:
   - Is `collection_amount` consistent with the Fees ledger?
     (Spot-check: filter `Fees` by student.mys_branch and posting_date.)
   - Is `rate_source` what you expect? If the line says `branch_override`
     but you expected `agreement_default`, check `MYS Royalty Rate Override`
     for an active row.
3. If a rate looks wrong, **don't edit the line**. Edit/inactivate the
   relevant override and **delete the draft** — re-run the generator:

   ```bash
   bench --site myschools.localhost execute \
     "myschools.api.royalty.generate_monthly_royalty_invoices" \
     --kwargs "{'year': 2026, 'month': 5}"
   ```

   The generator skips any branch that already has a submitted invoice; for
   drafts you must delete first.

4. Submit. The invoice is now immutable. `auto_generated`, `generated_by`,
   `applicable_rate`, `royalty_amount`, and `outstanding_amount` are locked.

---

## 6. Recording a payment

1. From the submitted invoice, click "Create → Royalty Payment" (or insert
   a new `MYS Royalty Payment`).
2. Fields: `royalty_invoice`, `payment_date`, `paid_amount`, `payment_method`.
3. Submit. On submit, the parent invoice's `paid_amount` is updated and
   `outstanding_amount = royalty_amount − paid_amount` recomputed.
4. Multiple partial payments are allowed; status flips to `Paid` only when
   `paid_amount ≥ royalty_amount`.

If a payment was recorded against the wrong invoice, **cancel** the payment
(don't delete) — cancellation rolls back the `paid_amount` change on the parent.

---

## 7. Disputed invoice — escalation script

A franchisee says the rate is wrong. Investigation steps:

1. Open the invoice. Look at each campus line's `rate_source`.
2. If `rate_source = campus_override` or `branch_override`, open the matching
   `MYS Royalty Rate Override` (filter: agreement, branch, campus, effective on
   the billing date). Confirm the override is what was agreed.
3. If `rate_source = agreement_default`, confirm the agreement's
   `default_royalty_rate`.
4. **The rate on the invoice is the rate that was active on the billing date.**
   Subsequent override edits don't retroactively change the past invoice —
   this is the audit guarantee. To correct a *future* invoice, edit the
   override. To correct a *submitted past* invoice, you must cancel +
   amend it (Frappe submittable lifecycle).

---

## 8. Common questions

**Q: Can the rate be 0%?**
Yes — set `rate_percent` to 0 on the override or default. The campus line is
generated with a 0 amount and `rate_source` shows where the 0 came from.

**Q: What happens if a branch has no campuses at the time of run?**
The generator logs `{"agreement": …, "skipped": "no_campuses"}` and moves on.
No invoice is created. Add campuses + rerun.

**Q: What about a campus that opened mid-month?**
The campus appears in the next month's invoice. The collection figure for the
*current* month will only include Fees with `posting_date` in that month, so a
campus that opened on the 20th simply has a small collection.

**Q: How do I preview without inserting?**

```bash
bench --site myschools.localhost execute \
  "myschools.api.royalty.generate_monthly_royalty_invoices" \
  --kwargs "{'year': 2026, 'month': 5, 'dry_run': True}"
```

Returns a list of `{would_create: True, total_collection, royalty_amount,
effective_rate}` entries per agreement — useful for monthly close.

**Q: Why is the effective rate 6.38% when no campus has a 6.38% override?**
Because it's the weighted average of the per-campus rates, weighted by each
campus's collection share. The invoice header shows the average; campus lines
show the truth.
