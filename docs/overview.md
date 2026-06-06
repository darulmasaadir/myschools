# Overview

A plain-language introduction to MY School ERP — no code, no jargon.

## What is this?

**MY School ERP** is the operations system for **myschools.pk**, a Pakistani
school franchise network. It runs the day-to-day business of every school in
the network: enrolment, attendance, fees, staff, royalty billing back to the
head office, and the quality-control inspections head office uses to keep
standards consistent across campuses.

It is built on top of the open-source **Frappe** framework — the same engine
behind ERPNext — so the heavy lifting (database, forms, permissions, reporting,
APIs) is reused rather than re-invented. Our app, called `myschools`, is the
franchise-specific layer that sits on top.

## Who uses it?

The system is built for a four-tier organisation:

```
Head Office
   └── Cluster (regional cluster of branches — e.g. "Northern Punjab")
         └── Branch (one school site — e.g. "Upper Mall Lahore")
               └── Campus (Kids / Junior / Senior wing inside that school)
```

The people who use it, top to bottom:

| Tier | Role | What they do in the system |
|---|---|---|
| Head Office | Chief Executive, HO Dept Heads | See everything; configure global policy, royalty rates, roles |
| Cluster | Cluster Director, Academic Monitor, Audit Officer | See all branches in their cluster; book and review inspections |
| Branch | Branch Director, Principal, Admin, Accountant, Campus Incharge | Run their school: enrol students, pay staff, collect fees, respond to findings |
| Campus | Teachers, support staff | Mark attendance, enter assessments, communicate with guardians |
| External | Guardians, Students | Read-only portal: see their child's marks, attendance, fees |

A **Branch Admin** only ever sees their own school's data. A **Cluster
Director** sees every school in their cluster. **Head Office staff** see
everything. This is enforced by the system itself, not by trust — the database
filters out rows the user shouldn't see.

## Why does it exist?

The network had grown to dozens of branches across Pakistan, and three things
were getting harder:

1. **Royalty billing.** Each franchisee pays a percentage of monthly fee
   collection back to head office. The rate isn't uniform — newer campuses
   get ramp-up discounts, established branches negotiate flat-rate deals.
   Spreadsheets made auditing this painful and disputes common.
2. **Inspection consistency.** Cluster directors visit branches with paper
   checklists. Findings got lost between visits, action items had no owner,
   and there was no audit trail to show that a flagged issue was actually
   fixed.
3. **Data isolation.** Branches were starting to share data they shouldn't —
   one franchisee shouldn't see another's accounts. The old setup couldn't
   enforce that.

The system addresses all three:

- **Configurable royalty rates** at the agreement, branch, or campus level,
  with effective-date windows and per-invoice audit of *why* each rate was
  applied (campus override, branch override, or agreement default).
- **A five-doctype inspection workflow** — checklist template, visit,
  finding, corrective action — with auto-creation of findings for any
  Critical or Major item that fails inspection, and automatic verification
  closure when every corrective action is signed off.
- **Branch-scoped permissions** wired into every query, so a Branch Admin
  literally cannot list another branch's students or invoices.

## What's shipped today

The **authoritative roadmap is [roadmap.md](roadmap.md)** — phase status,
delivering PR, files. Read that for the full picture. The headline:

Tracked by status: ✅ shipped & tested · 🟡 partial · ⬜ planned.

- ✅ Franchise hierarchy (cluster / branch / campus / department doctypes)
- ✅ Royalty rate resolution + monthly invoice generation
- ✅ Inspection workflow (template, visit, finding, corrective action)
- ✅ Branch-scoped permissions across all custom doctypes
- ✅ Auto-generated student and staff IDs tied to the franchise tree
- ✅ Central Monitoring Dashboard (8 number cards + 3 charts, role-aware via permission queries)
- ✅ Role-aware ERP shell — branding (logo / favicon / brand CSS), 5 tier
  workspaces with `restrict_to_role`, role-aware login landing for all 10
  franchise roles, Module Profiles trimming the sidebar per tier
- ✅ Branded Print Formats — Royalty Invoice, Inspection Report, Fee Receipt,
  Franchise Agreement, all inheriting the `MYS Default` Letter Head
- ✅ Notifications & Communication wiring — 6 Email Template + 6 Notification
  fixtures (royalty generated/overdue, finding assigned/overdue, corrective
  action overdue, agreement expiring); outbound system emails mirrored into
  `MYS Communication Log`; provider-agnostic SMS adapter stub
- ✅ Formal workflows + list-view polish — Phase 5
- ✅ Setup Wizard, onboarding tours, Query Reports — Phase 6
- ✅ Portals (Guardian / Branch / Inspection — Frappe Web Forms + `www/`, not a custom SPA) — Phase 7 complete (PR #15 `9b02a81`)
- ✅ **Phase 8:** domain extensions complete (8a fee overrides/late fees/bulk billing · 8b student lifecycle · 8c SMS adapters · 8d HR/payroll scaffolding · 8e payment gateways — last PR #20 `802e6fc`)

The system is **live for one demo branch network** (BR001 + BR014, three
campuses each, one fully-submitted royalty invoice on file). Phase 8 domain
extensions (billing, lifecycle, comms gateways, HR, fee payments) are shipped;
production rollout to real franchisees is a deployment/ops decision, not a code gap.

## How is it built — briefly

Frappe is a Python/Flask/MariaDB ERP framework with a built-in front-end
("Desk"). It lets you define "DocTypes" (essentially database tables with a
form UI) in JSON. We use it that way:

- The **`myschools` app** in this repo defines roughly 17 custom DocTypes
  for the franchise hierarchy, royalty, and inspection workflows.
- All business rules are **Python controllers** on those DocTypes, plus a
  handful of API modules under `myschools/api/`.
- We **don't fork upstream apps.** Customisations to Student / Employee /
  Guardian etc. are added as Custom Fields, exported as fixtures, so we can
  run `bench update` and inherit upstream improvements.

For the technical picture, jump to [architecture.md](architecture.md).

## Where to next

- **What's actually in the database?** → [data-model.md](data-model.md)
- **How does a royalty invoice happen month-on-month?** → [processes/royalty-billing.md](processes/royalty-billing.md)
- **How does an inspection close out?** → [processes/inspection-workflow.md](processes/inspection-workflow.md)
- **I want to develop on this codebase.** → [development.md](development.md)
