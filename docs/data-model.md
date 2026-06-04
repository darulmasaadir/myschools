# Data Model

Field-level reference for every custom DocType in the `myschools` app, plus the
custom fields we add to upstream Frappe / ERPNext / Education doctypes.

> **How to read this**: each table shows fieldname, type, target (for `Link`
> and `Table`), and `*` for required. Schema lives in
> `frappe-bench/apps/myschools/myschools/my_school_erp/doctype/<doctype>/<doctype>.json` —
> this doc paraphrases it for humans; the JSON is the source of truth.

---

## 1. Franchise hierarchy

### MYS Cluster

Top tier under Head Office. Autoname = `cluster_code` (e.g. `CL01`).

| Field | Type | Target | Notes |
|---|---|---|---|
| `cluster_code` | Data | | * unique, e.g. `CL01` |
| `cluster_name` | Data | | * e.g. "Northern Punjab" |
| `region` | Data | | |
| `is_active` | Check | | |
| `cluster_director` | Link | Employee | |
| `academic_monitor` | Link | Employee | |
| `audit_officer` | Link | Employee | |
| `description` | Small Text | | |

### MYS Branch

A single school site within a cluster. Autoname = `branch_code`. Linked to an
ERPNext `Company` for multi-Company accounting isolation.

| Field | Type | Target | Notes |
|---|---|---|---|
| `branch_code` | Data | | * e.g. `BR014` |
| `branch_name` | Data | | * |
| `cluster` | Link | MYS Cluster | * |
| `company` | Link | Company | Cluster sub-company; bridges to ERPNext books |
| `is_active` | Check | | |
| `opening_date` | Date | | |
| `address_line_1`, `city`, `province` | Data | | |
| `phone`, `email` | Data | | |
| `branch_director`, `branch_principal`, `branch_admin`, `branch_accountant` | Link | Employee | |

### MYS Campus

Kids / Junior / Senior wing of a branch. Autoname = `{branch}-{campus_type}`
(e.g. `BR014-Junior`).

| Field | Type | Target | Notes |
|---|---|---|---|
| `campus_type` | Select | Kids / Junior / Senior | * |
| `branch` | Link | MYS Branch | * |
| `is_active` | Check | | |
| `campus_incharge` | Link | Employee | |
| `phone`, `email` | Data | | |
| `max_students`, `current_strength` | Int | | |

### MYS Department

Head Office / Cluster / Branch-tier departments (Monitoring, Academic, Finance,
Training, Administration, Marketing, IT). Autoname = `dept_name`.

| Field | Type | Target | Notes |
|---|---|---|---|
| `dept_name` | Data | | * |
| `tier` | Select | Head Office / Cluster / Branch | * |
| `head_of_department` | Link | Employee | |
| `is_active` | Check | | |
| `mandate` | Small Text | | |

---

## 2. Royalty

### MYS Franchise Owner

The franchisee (a person or entity). Autoname = `OWN-{####}`.

| Field | Type | Target | Notes |
|---|---|---|---|
| `owner_name` | Data | | * |
| `status` | Select | Active / Inactive / Suspended / Terminated | |
| `cnic` | Data | | Pakistani national ID — synthetic data only in tests |
| `ntn` | Data | | Tax ID |
| `phone`, `email` | Data | | |
| `user` | Link | User | For portal login |
| `address`, `city`, `province` | Data / Small Text | | |

### MYS Franchise Agreement (submittable)

The contract that binds an Owner to a Branch + Company. Carries the default
royalty rate. Autoname = `MYS-FA-{branch}-{YYYY}-{####}`.

| Field | Type | Target | Notes |
|---|---|---|---|
| `franchisee` | Link | MYS Franchise Owner | * |
| `branch` | Link | MYS Branch | * |
| `company` | Link | Company | Cluster sub-company |
| `status` | Select | Draft / Active / Expired / Terminated / Renewed | |
| `start_date`, `end_date` | Date | | start is * |
| `default_royalty_rate` | Percent | | * the agreement-level fallback rate |
| `royalty_base` | Select | Gross Fee / Net Fee / Tuition / Gross Revenue | |
| `billing_day` | Int | | day-of-month invoice is dated |
| `grace_days` | Int | | days from invoice → due |
| `security_deposit`, `franchise_fee` | Currency | | |
| `deposit_received` | Check | | |
| `currency` | Link | Currency | |
| `agreement_terms` | Text Editor | | |
| `agreement_document` | Attach | | scanned PDF |

### MYS Royalty Rate Override

A rule that overrides the agreement default for a (branch, optional campus,
date range). Used to wire ramp-up discounts or negotiated flat rates.
**Resolution: campus override > branch override > agreement default.**

| Field | Type | Target | Notes |
|---|---|---|---|
| `agreement` | Link | MYS Franchise Agreement | * |
| `branch` | Link | MYS Branch | * |
| `campus` | Link | MYS Campus | optional — `null` means "all campuses" |
| `rate_percent` | Percent | | * |
| `effective_from` | Date | | * |
| `effective_to` | Date | | optional — open-ended if blank |
| `is_active` | Check | | |
| `notes` | Small Text | | |

### MYS Royalty Invoice (submittable)

One per (agreement, period) — monthly billing run produces these. Autoname =
`MYS-RI-{branch}-{period_year}{period_month}`.

| Field | Type | Target | Notes |
|---|---|---|---|
| `agreement` | Link | MYS Franchise Agreement | * |
| `franchisee` | Link | MYS Franchise Owner | denormalised |
| `branch` | Link | MYS Branch | * |
| `company` | Link | Company | |
| `status` | Select | Draft / Unpaid / Partial / Paid / Overdue / Cancelled | |
| `period_year` (e.g. `2026`), `period_month` (e.g. `05`) | Data | | * |
| `invoice_date`, `due_date` | Date | | |
| `campus_lines` | Table | MYS Royalty Invoice Campus Line | |
| `total_collection`, `applicable_rate`, `royalty_amount`, `paid_amount`, `outstanding_amount` | Currency / Percent | | computed |
| `auto_generated`, `generated_by` | Check / Data | | set by the monthly job |

### MYS Royalty Invoice Campus Line (child table)

One row per campus per invoice. Records the rate, the source, and the resulting
royalty amount per campus.

| Field | Type | Target | Notes |
|---|---|---|---|
| `campus` | Link | MYS Campus | |
| `campus_type` | Data | | denormalised for reporting |
| `collection_amount` | Currency | | fees collected this period |
| `rate_percent` | Percent | | resolved rate at submission time |
| `royalty_amount` | Currency | | collection × rate |
| `rate_source` | Data | | `campus_override`, `branch_override`, or `agreement_default` — *why* this rate |

### MYS Royalty Payment (submittable)

Records a franchisee payment against an invoice. On submit, the parent invoice's
`paid_amount` is updated.

| Field | Type | Target | Notes |
|---|---|---|---|
| `royalty_invoice` | Link | MYS Royalty Invoice | * |
| `branch`, `company` | Link | MYS Branch, Company | |
| `payment_date` | Date | * | |
| `paid_amount` | Currency | * | |
| `payment_method` | Select | Bank Transfer / Cheque / Cash / Online | |

---

## 3. Inspection

### MYS Inspection Checklist Template

A reusable checklist tied to a visit type. Autoname = `CKT-{visit_type}-{####}`.

| Field | Type | Target | Notes |
|---|---|---|---|
| `template_name` | Data | | * |
| `visit_type` | Select | Academic Monitoring / Financial Audit / Facility / Complaint / Routine | * |
| `version` | Data | | e.g. `v1`, `v2.1` |
| `is_active` | Check | | inactive templates can't be applied to new visits |
| `description` | Small Text | | |
| `items` | Table | MYS Inspection Checklist Item | * |

### MYS Inspection Checklist Item (child table)

The reusable definition rows that live on a template.

| Field | Type | Target | Notes |
|---|---|---|---|
| `item_text` | Small Text | | * |
| `category` | Select | Safety / Facility / Cleanliness / Academic / Staff / Compliance / Financial / Other | * |
| `severity` | Select | Critical / Major / Minor | * — drives auto-finding behaviour |
| `weight` | Float | | * — used in weighted score |
| `max_score` | Int | | * |

### MYS Inspection Visit (submittable)

The actual visit. Autoname = `INSP-{YYYY}-{####}`. On submit, automatically
creates findings for failed Critical / Major items.

| Field | Type | Target | Notes |
|---|---|---|---|
| `branch` | Link | MYS Branch | * |
| `campus` | Link | MYS Campus | optional (branch-wide visits allowed) |
| `visit_type` | Select | (same as template) | * |
| `visit_date` | Date | | * |
| `inspector` | Link | Employee | * |
| `checklist_template` | Link | MYS Inspection Checklist Template | set by `apply_template_to_visit` |
| `areas_inspected` | Small Text | | |
| `checklist_results` | Table | MYS Inspection Checklist Result | snapshotted from template |
| `total_items`, `items_passed`, `items_failed`, `items_na` | Int | | auto-computed |
| `score_percent`, `weighted_score` | Percent | | auto-computed; N/A items excluded from denominator |
| `summary`, `recommendations` | Text Editor | | |
| `attachments` | Attach | | |
| `amended_from` | Link | MYS Inspection Visit | required by submittable lifecycle |

### MYS Inspection Checklist Result (child table)

The snapshot of each checklist item on a visit, with the inspector's result.

| Field | Type | Target | Notes |
|---|---|---|---|
| `item_text`, `category`, `severity` | (copy of item) | | snapshotted |
| `weight`, `max_score` | (copy of item) | | snapshotted |
| `result` | Select | Pass / Fail / N/A | |
| `score` | Int | | inspector's score; ≤ `max_score` |
| `notes` | Small Text | | per-item observation |
| `photo` | Attach Image | | |

### MYS Inspection Finding (submittable)

One issue raised by a visit — either auto-created from a failed Critical/Major
item or added manually. Autoname = `INSP-FIND-{YYYY}-{####}`.

| Field | Type | Target | Notes |
|---|---|---|---|
| `visit` | Link | MYS Inspection Visit | * |
| `branch`, `campus` | Link | MYS Branch, MYS Campus | branch is * |
| `severity` | Select | Critical / Major / Minor | * |
| `category` | Select | (same as item) | * |
| `status` | Select | Open / In Progress / Resolved / Verified | |
| `description` | Text | | * |
| `photo` | Attach Image | | |
| `reported_by` | Link | User | |
| `reported_on`, `due_date`, `resolved_on` | Date | | auto-create sets `due_date` = `visit_date + 7d` (Critical) or `+ 21d` (Major) |
| `resolution_notes` | Text | | |
| `amended_from` | Link | MYS Inspection Finding | |

### MYS Corrective Action

Concrete remedial tasks tied to a finding. **Not submittable** — uses a status
field so the workflow allows re-edits. When every action on a finding is
`Verified`, the finding's status auto-flips to `Verified`. Autoname =
`INSP-CA-{YYYY}-{####}`.

| Field | Type | Target | Notes |
|---|---|---|---|
| `finding` | Link | MYS Inspection Finding | * |
| `branch`, `campus` | Link | MYS Branch, MYS Campus | branch is * |
| `status` | Select | Planned / In Progress / Completed / Verified | * |
| `due_date` | Date | * | |
| `completion_date` | Date | | auto-set when status → Completed/Verified |
| `action_description` | Text | * | |
| `assigned_to` | Link | User | * |
| `evidence` | Attach | | |
| `verification_notes` | Small Text | | required to mark Verified |
| `verified_by`, `verified_on` | Link / Date | | auto-stamped on Verified |

---

## 4. Communication

### MYS Communication Log

Schema for outbound comms (Email / SMS / Push / In-App / WhatsApp). **No
gateways wired up yet** — currently a record-keeping table.

| Field | Type | Target | Notes |
|---|---|---|---|
| `channel` | Select | Email / SMS / Push / In-App / WhatsApp | * |
| `status` | Select | Queued / Sent / Delivered / Failed | |
| `sent_at` | Datetime | | |
| `sender` | Link | User | |
| `scope` | Select | Global / Cluster / Branch / Campus / Individual | * |
| `branch`, `campus` | Link | | conditional on scope |
| `recipient_role`, `recipient_user` | Link | Role, User | |
| `subject`, `body` | Data / Text Editor | | |

---

## 5. Custom fields on upstream DocTypes

Exported as fixtures (`fixtures` filter `name like '%-mys_%'`) so they reapply
on every `bench migrate`.

### Student (upstream `education.Student`)

| Field | Type | Target | Notes |
|---|---|---|---|
| `mys_cluster` | Link | MYS Cluster | |
| `mys_branch` | Link | MYS Branch | fetched from cluster |
| `mys_campus` | Link | MYS Campus | |
| `mys_student_id` | Data | | generated by `api/identity.py` before insert |

### Employee (upstream `frappe.Employee`)

| Field | Type | Target | Notes |
|---|---|---|---|
| `mys_branch` | Link | MYS Branch | drives permission scope |
| `mys_campus` | Link | MYS Campus | |
| `mys_role_tier` | Select | HO / Cluster / Branch / Campus | |
| `mys_staff_id` | Data | | generated by `api/identity.py` |

### Guardian (upstream `education.Guardian`)

| Field | Type | Target | Notes |
|---|---|---|---|
| `mys_branch` | Link | MYS Branch | so parent portal only shows their branch |

### Fee Structure (upstream `education.Fee Structure`)

| Field | Type | Target | Notes |
|---|---|---|---|
| `income_account` | Link | Account | Workaround for upstream v15.5.3 bug: `Fees.income_account` declares `fetch_from: "fee_structure.income_account"` but the column was missing. Optional; leave blank to use the Company default. |

### Fees (upstream `education.Fees`) — Phase 8a

**Canonical billing document** for MY School — royalty, dashboards, portals, and
late-fee automation all read `tabFees`. Not Sales Invoice from Fee Schedule. See
[processes/billing-model.md](processes/billing-model.md).

| Field | Type | Target | Notes |
|---|---|---|---|
| `mys_late_fee_for` | Link | Fees | Parent invoice this late-fee row was generated from |
| `mys_late_fee_applied` | Check | | Set on parent after `apply_late_fees` creates the linked late invoice (idempotency) |

### MYS Fee Structure Override (Phase 8a)

| Field | Type | Notes |
|---|---|---|
| `branch` | Link → MYS Branch | * |
| `campus` | Link → MYS Campus | optional; campus row wins over branch-only row |
| `program` | Link → Program | * |
| `academic_year` | Link → Academic Year | * |
| `fee_structure` | Link → Fee Structure | * alternate structure for this scope |
| `effective_from` / `effective_to` | Date | active window |
| `is_active` | Check | |

Resolved by [`api/fees.resolve_fee_structure`](../frappe-bench/apps/myschools/myschools/api/fees.py): campus override → branch override → default `Fee Structure` for program/year/company.

### MYS Late Fee Policy (Phase 8a)

| Field | Type | Notes |
|---|---|---|
| `branch` | Link → MYS Branch | * |
| `grace_days` | Int | days after `due_date` before late fee applies |
| `late_fee_percent` | Percent | of outstanding on parent invoice |
| `late_fee_minimum` | Currency | floor for computed late amount |
| `fees_category` | Link → Fee Category | line item on generated late `Fees` |
| `effective_from` / `effective_to` | Date | |
| `is_active` | Check | |

Daily cron (`0 6 * * *`) calls `scheduled_apply_late_fees` → `apply_late_fees`.

---

## ID generation

- **Student**: `MYS-{cluster_code}-{branch_code}-STU{######}` →
  e.g. `MYS-CL03-BR014-STU000245`
- **Employee**: `MYS-{branch_code}-{role_code}{####}` →
  e.g. `MYS-BR014-TCH0056` (role codes: `TCH` teacher, `ADM` admin,
  `ACC` accountant, `PRN` principal, etc.)

Implemented in [`api/identity.py`](../frappe-bench/apps/myschools/myschools/api/identity.py)
via `before_insert` hooks on Student / Employee.

---

## Relationships diagram

```
MYS Cluster (CL01)
   ├── academic_monitor → Employee
   └── MYS Branch (BR014) — company → Company (cluster sub-company)
         ├── branch_principal → Employee
         ├── MYS Campus (BR014-Junior)
         ├── MYS Franchise Agreement (MYS-FA-BR014-2026-0001)
         │     ├── franchisee → MYS Franchise Owner (OWN-0023)
         │     └── MYS Royalty Rate Override (per branch / campus)
         │
         ├── MYS Royalty Invoice (MYS-RI-BR014-202605)
         │     ├── campus_lines → MYS Royalty Invoice Campus Line (rate_source recorded)
         │     └── MYS Royalty Payment (MYS-RP-0042) — many per invoice
         │
         └── MYS Inspection Visit (INSP-2026-0017) — visit_type, inspector
               ├── checklist_template → MYS Inspection Checklist Template
               ├── checklist_results → MYS Inspection Checklist Result (snapshot)
               └── MYS Inspection Finding (INSP-FIND-2026-0089) — auto-created for failed Critical/Major
                     └── MYS Corrective Action (INSP-CA-2026-0173) — many per finding
```
