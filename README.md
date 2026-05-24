# MY School ERP

Custom multi-tier school-franchise ERP for **[myschools.pk](https://myschools.pk)**, built on the open-source **Frappe Framework** with the **Frappe Education** app, plus a custom `myschools` app for the franchise hierarchy (Head Office → Cluster → Branch → Campus).

## Quick start

```bash
cd frappe-bench
bench start                       # launches web, workers, socketio, redis
```

Then open: <http://myschools.localhost:8000/login>

- Username: `Administrator`
- Password: `admin`

## What's installed

| App | Version | Source |
|---|---|---|
| `frappe` | 15.108 | github.com/frappe/frappe (v15) |
| `erpnext` | 15.108 | github.com/frappe/erpnext (v15) |
| `education` | 15.5.3 | github.com/frappe/education (v15.2) |
| `myschools` | 0.0.1 | local — `frappe-bench/apps/myschools` |

## What our `myschools` app adds

- **11 custom DocTypes** across two clusters:

  **Franchise hierarchy**
  - `MYS Cluster` — top tier (`CL01`, `CL02`, …)
  - `MYS Branch` — a school site, belongs to a Cluster, linked to an ERPNext **Company** for multi-Company books
  - `MYS Campus` — Junior / Kids / Senior under a Branch
  - `MYS Department` — Head Office departments (Monitoring / Academic / Finance / Training / Administration / Marketing / IT)
  - `MYS Inspection Visit` — submittable monitoring/audit doc
  - `MYS Communication Log` — outbound communications audit

  **Royalty / franchise economics**
  - `MYS Franchise Owner` — the franchisee (CNIC, NTN, contact, linked User)
  - `MYS Franchise Agreement` — submittable; links Owner + Branch + Company; carries `default_royalty_rate`, royalty base, billing day, grace days, security deposit, franchise fee
  - `MYS Royalty Rate Override` — per-branch and optionally per-campus rate overrides with effective dates; **campus override > branch override > agreement default**
  - `MYS Royalty Invoice` — submittable monthly invoice with per-campus line items; auto-computes effective weighted rate
  - `MYS Royalty Payment` — submittable; syncs paid_amount back to the invoice on submit/cancel

- **Multi-Company architecture:** Head Office is a group Company; each cluster is its own Company parented under HO; every Branch is linked to its Company so financials are isolated per franchisee while still rolling up to HO.
- **Custom fields** added to upstream DocTypes (`Student`, `Employee`, `Guardian`) linking them to the franchise tree.
- **Auto ID generation:**
  - Student: `MYS-{cluster}-{branch}-STU{######}` (e.g. `MYS-CL03-BR014-STU000245`)
  - Staff:   `MYS-{branch}-{role-code}{####}` (e.g. `MYS-BR014-TCH0056`)
- **10 new roles:** Chief Executive, HO Dept Head, Cluster Director, Academic Monitor, Audit Officer, Branch Director, Branch Principal, Branch Admin, Branch Accountant, Campus Incharge.
- **Branch-scoped data isolation** via `permission_query_conditions` so a Branch Admin only ever sees their own branch's students/agreements/invoices; a Cluster Director sees all branches in their cluster.
- **Scheduled job:** `cron "0 3 1 * *"` runs `myschools.api.royalty.scheduled_monthly_royalty_run` on the 1st of every month to auto-generate royalty invoices for the previous period.

## Configurable royalty (the 7% is *not* fixed)

The royalty rate is fully configurable and can vary per branch or per campus.

Rate resolution order on the billing date:
  1. **Campus-level override** (e.g. BR014-Junior runs at 5% for the first year as a ramp-up incentive)
  2. **Branch-level override** (e.g. BR001 negotiated 6% across all campuses)
  3. **Agreement default** (e.g. 7%)

Each `MYS Royalty Invoice` carries per-campus line items; each line resolves
its own rate independently and records the `rate_source` (`campus_override`,
`branch_override`, or `agreement_default`), so audits show *why* a rate was
applied, not just the number.

Demo seed produces:

```
Agreement MYS-FA-BR014 (default 7%):
  BR014-Junior  ->  5%  (campus_override)
  BR014-Kids    ->  7%  (agreement_default)
  BR014-Senior  ->  7%  (agreement_default)

Agreement MYS-FA-BR001 (default 7%):
  BR001-Junior  ->  6%  (branch_override)
  BR001-Kids    ->  6%  (branch_override)
  BR001-Senior  ->  6%  (branch_override)
```

Sample demo invoice (PKR 6.5M collection across BR014, May 2026):

```
BR014-Kids     1,500,000  @ 7%  =  105,000
BR014-Junior   2,000,000  @ 5%  =  100,000     <-- campus override applied
BR014-Senior   3,000,000  @ 7%  =  210,000
                                 ---------
Total royalty                     415,000
Effective weighted rate            6.38%
```

Generate manually:

```bash
bench --site myschools.localhost execute myschools.scripts.demo_royalty_invoice.run
```

Or invoke the monthly generator directly (defaults to previous month):

```bash
bench --site myschools.localhost execute "myschools.api.royalty.generate_monthly_royalty_invoices" \
  --kwargs "{'year': 2026, 'month': 5}"
```

## Seeded demo data

```
CL01  Northern Punjab        BR001 Upper Mall Lahore     ── Kids / Junior / Senior
                             BR002 DHA Phase 5 Lahore
CL02  Central Punjab
CL03  Sindh                  BR014 Gulshan-e-Iqbal       ── Kids / Junior / Senior
```

Re-run anytime:

```bash
bench --site myschools.localhost execute myschools.scripts.seed_demo.run
```

## Repository layout

```
/Users/ali/projects/myschools/
├── docs/architecture.md          ← module-by-module design notes
├── README.md                     ← this file
└── frappe-bench/                 ← the runtime bench (do not commit verbatim)
    ├── apps/
    │   ├── frappe/               ← upstream, untouched
    │   ├── erpnext/              ← upstream, untouched
    │   ├── education/            ← upstream, untouched (Frappe Education)
    │   └── myschools/            ← OUR custom app — all customisation lives here
    │       └── myschools/
    │           ├── hooks.py
    │           ├── setup/install.py
    │           ├── api/identity.py
    │           ├── api/permissions.py
    │           ├── api/royalty.py          ← rate resolution + monthly job
    │           ├── scripts/seed_demo.py
    │           ├── scripts/demo_royalty_invoice.py
    │           └── my_school_erp/doctype/
    │               ├── mys_cluster/
    │               ├── mys_branch/                       ← linked to Company
    │               ├── mys_campus/
    │               ├── mys_department/
    │               ├── mys_inspection_visit/
    │               ├── mys_communication_log/
    │               ├── mys_franchise_owner/
    │               ├── mys_franchise_agreement/
    │               ├── mys_royalty_rate_override/
    │               ├── mys_royalty_invoice/
    │               ├── mys_royalty_invoice_campus_line/
    │               └── mys_royalty_payment/
    └── sites/myschools.localhost/
```

## Status against the PDF's 22 modules

| # | Module | Status |
|---|---|---|
| 1 | Master Setup | Frappe core |
| 2 | Franchise Management | done (custom) |
| 3 | Student Information System | done (Education) |
| 4 | HR / Staff Management | done (ERPNext Employee) + custom MYS fields |
| 5 | Campus Management | done (custom) |
| 6 | Academic Management | done (Education) |
| 7 | Examination System | done (Education Assessment) |
| 8 | Attendance System | done (Education) |
| 9 | Finance / Fee Management | done (Education Fees + ERPNext Accounts + multi-Company per franchise) |
| 9b | Royalty & Franchise Economics | done (Franchise Owner/Agreement/Rate Override/Royalty Invoice/Payment; configurable per-branch + per-campus rates) |
| 10 | Parent Portal | done (Education Student Portal + Guardian) |
| 11 | Teacher Portal | done (Education Instructor) |
| 12 | Communication System | scaffold (MYS Communication Log; wire up SMS/Email gateways next) |
| 13 | Monitoring & Inspection | scaffold (MYS Inspection Visit) |
| 15 | Transport | TODO — use ERPNext Vehicle or build MYS Route/Stop/Pickup |
| 16 | Library | TODO — adapt ERPNext Item/Stock or build Library Member/Loan |
| 17 | LMS / Digital Learning | TODO — install `frappe/lms` |
| 18 | Document Management | TODO — Frappe File + per-branch folders |
| 19 | Security / Role Control | done (roles + permission queries) |
| 20 | Mobile App | TODO — Education ships an SPA frontend; PWA-ize it for parents |
| 21 | Unique ID System | done (Student + Employee ID hooks) |
| 22 | Reporting System | partial (Frappe Report Builder works); add Insights or custom reports |

## Recreating from zero

If you ever wipe the bench:

```bash
# from /Users/ali/projects/myschools
bench init frappe-bench --python /opt/homebrew/bin/python3.12 --frappe-branch version-15 --no-backups
cd frappe-bench
bench get-app education --branch version-15.2
bench get-app erpnext --branch version-15

# install (note: needs MariaDB root password; we set 'frappe_root_2026' earlier)
bench new-site myschools.localhost \
  --mariadb-root-password 'frappe_root_2026' \
  --admin-password admin \
  --install-app erpnext --install-app education \
  --db-name myschools

# Then drop the existing apps/myschools/ symlink or directory and re-clone our app from git.
bench --site myschools.localhost install-app myschools
bench --site myschools.localhost migrate
bench --site myschools.localhost execute myschools.scripts.seed_demo.run
echo "y" | bench setup procfile
bench start
```
