# Process: Inspection Workflow

*Audience: Cluster Director, Academic Monitor, Audit Officer, Branch Principal,
anyone closing out a finding.*

How to run an inspection from planning a visit to verifying that every issue
raised has been actioned.

> **API reference**: [../api/inspection.md](../api/inspection.md) ·
> **Doctypes referenced**: [../data-model.md §3](../data-model.md#3-inspection)

---

## 1. Why this exists

Cluster directors visit branches with paper checklists. The old system
("MYS Inspection Visit" alone) couldn't track follow-up: a flagged issue might
get fixed, or might not, but there was no audit trail to prove either.

The decomposed workflow ships five DocTypes that together answer the questions
*was this inspected?*, *did it pass?*, *what was raised?*, *who's fixing it?*,
and *has it been verified closed?*

---

## 2. The lifecycle

```
Checklist Template (versioned, per visit type)
   │
   │ apply_template_to_visit() snapshots items
   ↓
Inspection Visit (draft → submitted)
   │  ├── checklist_results[]  (snapshot of items + Pass/Fail/N/A + score)
   │  └── auto-computed: items passed/failed/N/A, score_percent, weighted_score
   │
   │ on submit → auto-create one Finding per failed Critical/Major item
   ↓
Inspection Finding (submittable: Open → In Progress → Resolved → Verified)
   │
   │ (one or many)
   ↓
Corrective Action (Planned → In Progress → Completed → Verified)
   │
   └─ when every Corrective Action on a Finding is Verified,
      the Finding flips to Verified automatically
```

Each arrow is a real transition you can audit:

- Templates are versioned, so you know which checklist was in force on a
  given visit date.
- Items are **snapshotted** onto the visit — revising the template later
  does not rewrite historical visits.
- Findings are submittable (locked once submitted) so the original issue
  description can't be quietly edited.
- Corrective Actions are intentionally **not** submittable — the status
  field needs to be edited several times (`Planned → In Progress → Completed
  → Verified`), which submittable would block.

---

## 3. Roles & actions

| Role | Can | Notes |
|---|---|---|
| **Audit Officer / Academic Monitor** | Create + submit Visit; create Finding manually | Cluster-scoped: see all branches in their cluster |
| **Cluster Director** | All of the above; verify Corrective Actions | Cluster-scoped |
| **Branch Director / Principal** | View visits/findings for their branch; create Corrective Actions; mark Completed | Branch-scoped |
| **Branch Admin** | View only | Branch-scoped |
| **System Manager / HO** | Manage templates; everything else | Global |

Cluster Director / Audit Officer / Academic Monitor get **cluster scope** —
they see every branch in their cluster.

Branch roles get **branch scope** — they see their branch only.

---

## 4. Setup: create a checklist template

One-time per visit type. Done by HO or the cluster team.

1. **New → MYS Inspection Checklist Template**.
2. Fields: `template_name` (e.g. "Routine Monthly v3"), `visit_type`
   (`Routine`), `version`, `is_active = ✓`, optional `description`.
3. Add items to the `items` table. Each item has:
   - `item_text` — what the inspector is checking.
   - `category` — Safety / Facility / Cleanliness / Academic / Staff /
     Compliance / Financial / Other.
   - `severity` — **Critical** / **Major** / **Minor**. This drives
     auto-finding behaviour: Critical and Major failures auto-create a
     finding; Minor failures need a manual one.
   - `weight` — multiplier in the weighted score (e.g. fire safety = 3.0,
     bulletin board = 0.5).
   - `max_score` — denominator for this item.
4. Save. Templates aren't submittable; they can be edited and a new version
   issued by bumping `version` and (optionally) deactivating the old one.

> **Versioning tip**: don't edit a template that's already been applied to
> visits. Create a new template with `version = v2`. Snapshotting protects old
> visits, but the template list stays cleaner with explicit versions.

---

## 5. Running a visit

1. **New → MYS Inspection Visit**.
2. Fields:
   - `branch`, optional `campus` (a visit may cover the whole branch),
   - `visit_type` (must match a template's visit_type),
   - `visit_date`, `inspector` (Employee),
   - `areas_inspected` (free text).
3. **Apply a template** — either through the form (link the
   `checklist_template`, then call the API) or via bench:

   ```bash
   bench --site myschools.localhost execute \
     "myschools.api.inspection.apply_template_to_visit" \
     --kwargs "{'visit': 'INSP-2026-0017', 'template': 'CKT-Routine-0003'}"
   ```

   This snapshots the template's items into `checklist_results`.

4. For each item, set `result` to **Pass / Fail / N/A** and (optionally)
   `score`, `notes`, `photo`. N/A items are excluded from the score
   denominator.

5. **Save** — totals (`items_passed/failed/na`, `score_percent`,
   `weighted_score`) recompute on every save. Fill in `summary` and
   `recommendations`.

6. **Submit**. On submit:
   - The visit is locked.
   - For every checklist row where `result == "Fail"` **and** `severity in
     ("Critical", "Major")`, a `MYS Inspection Finding` is auto-created with:
     - `status = Open`
     - `severity`, `category` copied from the row
     - `description = item_text + "\n\nInspector notes: " + notes`
     - `due_date = visit_date + 7 days` (Critical) or **`+ 21 days`** (Major)
     - `reported_on = visit_date`
   - **Minor** failures don't auto-create findings. If a Minor failure
     needs follow-up, create a finding manually from the visit's summary.

Auto-creation is **idempotent** — re-submitting (after a cancel/amend cycle)
won't create duplicates if findings already exist for the visit.

---

## 6. Acting on a finding

1. Open the finding (auto-created or manual).
2. Submit it (status auto-set to `Open`).
3. Triage: edit if needed, assign someone to lead the response, then move
   `status → In Progress`.
4. **Create one or more Corrective Actions**.
   - `New → MYS Corrective Action`. Fields: `finding`, `branch`,
     `action_description`, `assigned_to` (User), `due_date`, optional
     `evidence` (file/photo), `verification_notes` (required to verify).
   - Multiple actions per finding are normal — e.g. one finding "Exit
     signage missing" might have three actions (order signage, install,
     verify install).
5. The owner progresses each action: `Planned → In Progress → Completed`.
   On `Completed`, `completion_date` auto-populates.
6. Once the work is done, a verifier (Cluster Director / Audit Officer)
   sets `status = Verified` after filling `verification_notes`. `verified_by`
   and `verified_on` auto-stamp.
7. **When the last open Corrective Action on a finding is Verified, the
   finding's `status` flips to `Verified` automatically.** No manual close
   is needed — that's the only way a finding can reach Verified.

You can move a finding to `Resolved` manually (interim state) before all
actions are verified — but the system won't accept `Verified` until every
action is closed out.

---

## 7. Scoring

The visit shows two percentages:

- **`score_percent`** = `Σ score / Σ max_score` × 100, over non-N/A items.
  Simple completion percentage.
- **`weighted_score`** = `Σ (score × weight) / Σ (max_score × weight)` × 100.
  Heavier items pull the result more.

N/A items are excluded from both denominators. If every item is N/A, both
scores are 0 (not an error).

---

## 8. Common scenarios

**Q: The inspector noticed something not on the template.**
Add a Finding manually from the visit. The auto-create only handles failed
template items; manual findings have no template link.

**Q: A Minor item failed but it's actually serious in this case.**
Two options: (a) create a manual finding from the visit summary, or (b) edit
the template item's severity to Major and re-issue the template for next
time. Minor failures never auto-create findings by design — those tend to
be cosmetic, and 50 of them would drown the workflow.

**Q: We applied the wrong template.**
While the visit is a draft, re-call `apply_template_to_visit` with the right
template. This **replaces** the `checklist_results` table (clears + re-adds).
Any results entered for the previous template are lost.

**Q: Can a visit be amended after submit?**
Yes — Frappe submittable lifecycle. Cancel → Amend → re-submit creates a new
draft (`-1`, `-2` suffix), but **auto-created findings on the original visit
are not deleted**. Decide manually whether they're still valid.

**Q: How do I link findings across visits ("this is a repeat of last month's")?**
Not modelled explicitly. Reference the prior finding in the new finding's
`description`. If repeat findings become common, we can add a `prior_finding`
link field later.
