# MY School ERP — documentation

This folder is the system's documentation. The repo root has the user-facing
landing page ([../README.md](../README.md)); everything that's longer than a
landing page lives here.

## I am evaluating the system — what is this?

Start with **[overview.md](overview.md)**. It explains what MY School ERP is, who
uses it, why we built it on Frappe, and what's shipped vs. planned. No code.

For the **phase-by-phase customisation status** (what's shipped, what's in flight,
what's planned, with PRs and commits cited), see **[roadmap.md](roadmap.md)** —
that doc is the single source of truth before starting any new piece of work.

## I am a school operator using the product

You probably want a process walkthrough:

- **[processes/billing-model.md](processes/billing-model.md)** — why student
  billing uses Education **`Fees`** (not Fee Schedule → Sales Invoice), what
  MY School reads for royalty/portals/late fees, and the 8a-2/8a-3/8a-4 follow-ups.
- **[processes/royalty-billing.md](processes/royalty-billing.md)** — how monthly
  royalty invoices come to exist, how the rate is computed, what to do when a
  franchisee disputes a number. Royalty collection is summed from submitted **`Fees`**.
- **[processes/inspection-workflow.md](processes/inspection-workflow.md)** — how
  to run an inspection from booking to verification, what auto-creates findings,
  how corrective actions close out.
- **[processes/central-dashboard.md](processes/central-dashboard.md)** — what the
  Central Monitoring Dashboard shows, how it's scoped per role, where the JSON
  fixtures live, and how the three custom-method endpoints work.
- **[processes/navigation-and-roles.md](processes/navigation-and-roles.md)** —
  where each of the 10 franchise roles lands on login, which modules they see
  in the sidebar, and how to add a new role or workspace.
- **[processes/print-formats.md](processes/print-formats.md)** — the four branded
  PDF layouts (Royalty Invoice, Inspection Report, Fee Receipt, Franchise
  Agreement), how they get picked as default, and how to add a new one.
- **[processes/notifications.md](processes/notifications.md)** — six Email
  Template + Notification pairs, the `MYS Communication Log` audit trail, and
  how a new alert/reminder gets wired in.
- **[processes/workflows.md](processes/workflows.md)** — the two formal Frappe
  Workflows (Inspection Finding, Royalty Invoice), role-gated transitions, and
  the `update_after_submit` / `allow_on_submit` / `db.set_value` rules every
  workflow contributor will hit.
- **[processes/setup-and-onboarding.md](processes/setup-and-onboarding.md)** —
  the first-time-install operator journey: the MYS Setup Wizard slide, the
  `MYS Franchise Setup` Module Onboarding card, the four Query Reports
  (Royalty Aging / Fee Collection by Branch / Findings by Branch & Severity /
  Branch Health Scorecard), and the headless-install `is_setup_complete` trap.

## I am a developer onboarding to the codebase

Read in this order:

1. **[overview.md](overview.md)** — context.
2. **[architecture.md](architecture.md)** — system architecture (stack,
   hierarchy, modules, royalty rate resolution, inspection workflow,
   permissions, scheduled jobs, repo layout).
3. **[data-model.md](data-model.md)** — DocType-by-DocType field reference.
4. **[development.md](development.md)** — bench bootstrap, running tests
   (Frappe + Playwright), branching, commit conventions, releasing,
   debugging tips.
5. **[deployment.md](deployment.md)** — Frappe Cloud staging runbook, app pins,
   review seed, post-deploy smoke.
6. **[api/royalty.md](api/royalty.md)** and **[api/inspection.md](api/inspection.md)** —
   function reference for the two core APIs.

## I am writing or reviewing a PR

- **[../CONTRIBUTING.md](../CONTRIBUTING.md)** — branching, commits, PR workflow.
- **[../CHANGELOG.md](../CHANGELOG.md)** — Keep-a-Changelog log; update under
  `[Unreleased]` in the same PR as the change.
- **[development.md](development.md#documentation-policy)** — when to update which doc.

## Layout

```
docs/
├── README.md                       ← this nav index
├── overview.md                     ← non-technical: what / who / why
├── roadmap.md                      ← phase-by-phase status, single source of truth
├── architecture.md                 ← technical: how it's built
├── data-model.md                   ← DocType field reference
├── development.md                  ← dev onboarding + workflows
├── deployment.md                   ← Frappe Cloud staging + review seed
├── processes/
│   ├── royalty-billing.md          ← operator-facing: monthly royalty cycle
│   ├── inspection-workflow.md      ← operator-facing: inspection lifecycle
│   ├── central-dashboard.md        ← central monitoring dashboard reference
│   ├── navigation-and-roles.md     ← role landing pages, workspaces, module profiles
│   ├── print-formats.md            ← branded PDF layouts (Royalty Invoice / Inspection Report / Fee Receipt / Franchise Agreement)
│   ├── notifications.md            ← email templates + notifications + Communication Log
│   ├── workflows.md                ← Frappe Workflows on Finding + Royalty Invoice
│   └── setup-and-onboarding.md     ← Setup Wizard / Module Onboarding / Query Reports
└── api/
    ├── royalty.md                  ← myschools.api.royalty function reference
    └── inspection.md               ← myschools.api.inspection function reference
```

## Conventions in these docs

- **Status legend**: ✅ shipped & tested · 🟡 partial · ⬜ planned.
- **Code references** use markdown links pointing at real paths in the repo —
  click-through should always work. If a link 404s, the doc is stale; file an
  issue.
- **Diagrams** are ASCII-only on purpose. They survive plain-text review and
  copy into terminal output.
- **Dates** are written `YYYY-MM-DD` (ISO) to avoid PK/US ambiguity.
- **Audience tags** at the top of each process doc (e.g. *Audience: Branch
  Accountant, Cluster Director*) signal who the doc is written for.
