# Process: Student billing model — `Fees` as canonical

*Audience: developers, HO Finance, Branch Accountant. Decision record from the
Phase 8a investigation (2026-06-03). Supersedes any assumption that “Education
bulk billing” and MY School billing are the same object.*

> **Related:** [royalty-billing.md](royalty-billing.md) (royalty reads `tabFees`) ·
> [data-model.md §5](../data-model.md#fees-upstream-educationfees--phase-8a) ·
> [api/fees.py](../../frappe-bench/apps/myschools/myschools/api/fees.py) ·
> [roadmap.md § Phase 8](../roadmap.md#phase-8--domain-extensions-)

---

## 1. Decision (locked)

**Canonical student fee invoice for MY School is the Education `Fees` doctype.**

All franchise economics, portals, late fees, and reporting that depend on “fee
collection” must read and write **`Fees`** (submitted, `docstatus = 1`), not
ERPNext **`Sales Invoice`** created by Education’s **`Fee Schedule`** bulk tool.

**Do not** migrate royalty, dashboard, late fees, or portals to Sales Invoice —
that would fork the stack, break upgrade-safe alignment with Education’s
first-class `Fees` path, and duplicate GL semantics we already use.

---

## 2. Why — two paths in Education v15

Frappe Education ships **two** billing mechanisms. They are not interchangeable.

| Path | Operator entry | Produces | Used by MY School? |
|------|----------------|----------|-------------------|
| **A — `Fees`** | Desk → Fees (per student); API / scripts | `Fees` (GL-posting, `outstanding_amount`, `due_date`, `fee_structure`, `program_enrollment`) | **Yes — canonical** |
| **B — `Fee Schedule`** | Desk → Fee Schedule → “Create fees” | **`Sales Invoice`** or Sales Order (via `fee_schedule.create_fees()` → `create_sales_invoice`) | **No — out of scope** |

Path B is the stock “bulk by student group” tool. It never creates `Fees` rows.
There is no Education setting to redirect it to `Fees`.

Path A is first-class: `Fees` extends `AccountsController`, posts receivable +
income GL entries, supports payment requests, and exposes a student portal list.
MY School’s custom fields (`mys_late_fee_for`, `mys_late_fee_applied`) and Phase
8a late-fee job target **`tabFees` only**.

---

## 3. What MY School already depends on (`Fees` only)

| Surface | Location |
|---------|----------|
| Royalty collection roll-up | `api/royalty.py` → `tabFees` |
| Central dashboard “fees collected” | `api/dashboard.py` → `tabFees` |
| Late-fee automation (8a) | `api/fees.py` → overdue `tabFees` |
| Guardian portal | `/guardian/fees`, `api/guardian_portal.py` |
| Branch portal | `/branch/fees`, `api/branch_portal.py` |
| Print format | `MYS Fee Receipt` |
| Query report | `MYS Fee Collection by Branch` |
| Branch workspace | shortcuts to **Fees** + **Fee Structure** (not Fee Schedule) |
| Seeds / tests | `seed_education.py`, `test_royalty_from_fees.py`, `test_fees.py` |

If an operator bills via **Fee Schedule → Sales Invoice**, those invoices are
**invisible** to every row above. Royalty would under-report; late fees would not
run; portals would show gaps.

---

## 4. Gaps (honest)

1. **No bulk generator for `Fees`.** Education’s only bulk tool emits Sales
   Invoices. At scale, branches either create `Fees` one-by-one or need a
   custom bulk tool (roadmap **8a-4**).
2. **`resolve_fee_structure()` is API-only until wired** (roadmap **8a-3**).
   Overrides in `MYS Fee Structure Override` are stored and tested; new `Fees`
   rows do not yet default `fee_structure` from the resolver.
3. **Split-brain risk.** Fee Schedule / Sales Invoice are still reachable in a
   vanilla Education install if module profiles are not trimmed (roadmap **8a-2**).

Phase **8a** (overrides, late-fee policy, scheduler) is **correct on `Fees`**;
these gaps are follow-ups, not reasons to rework 8a.

---

## 5. Recommended follow-ups (roadmap)

| ID | What | Upgrade-safe approach |
|----|------|------------------------|
| **8a-2** | ✅ **Billing safety** — `Accounts` blocked on MYS Branch/Cluster module profiles; `restrict_split_brain_billing_paths()` denies franchise roles create on `Fee Schedule` / `Sales Invoice`. | `module_profile.json` + `setup/install.py`; tests in `test_billing_safety.py`. |
| **8a-3** | ✅ **Wire overrides** — `Fees.validate` → `apply_resolved_fee_structure_on_fees` sets `fee_structure` from `resolve_fee_structure()`; orange alert on mismatch with active override. | `hooks.py` `doc_events` + `test_fees.py`. |
| **8a-4** | **Bulk `Fees` generator** — custom DocType or whitelisted tool (student group + program + term → N submitted `Fees`), mirroring Fee Schedule ergonomics but emitting **`Fees`**. Reuse resolver from 8a-3. | New doctype/API in `myschools` app only. |

**Order:** 8a-2 (quick, reduces operational risk) → 8a-3 (makes overrides live) →
8a-4 (scale). Optional: role×surface test for override/policy doctype permissions
(Branch Director write, Accountant read, Monitor denied — already correct by JSON).

---

## 6. Operator guidance (until 8a-4 ships)

- Create and submit student invoices as **`Fees`**, linked to **Program
  Enrollment** and the correct **Fee Structure** (or rely on 8a-3 once shipped).
- **Do not** use **Fee Schedule → Create fees** for franchise billing; that
  path creates Sales Invoices MY School does not read.
- Configure **MYS Fee Structure Override** / **MYS Late Fee Policy** per branch
  (Branch Director or HO); late fees run daily at 06:00 via scheduler.

---

## 7. Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| Canonical = Sales Invoice | Rewrites royalty, dashboard, 8a late fees, both portals, print format, reports; fights Education’s explicit `Fees` portal and GL model. |
| Dual-read (Fees + SI) | Permanent complexity; two sources of truth for “collected this month.” |
| Fork `fee_schedule.py` | Banned (upgrade-safe); upstream changes would break us every `bench update`. |

---

## 8. Verification

- Unit: `tests/test_fees.py`, `tests/test_royalty_from_fees.py`
- Live scheduler: `scripts/verify_late_fees.py` (real `scheduled_apply_late_fees`)
- After 8a-3: add test that inserting `Fees` picks campus/branch override structure
- After 8a-4: e2e bulk run → N `Fees` visible in royalty roll-up for the period
