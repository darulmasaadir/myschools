# Deployment — Frappe Cloud staging for CEO review

How to stand up a **staging** site on Frappe Cloud so MY School leadership can
walk the shipped product (desk + portals + PWA) without touching production
data.

> **Audience:** implementer / DevOps. For local dev setup see
> [development.md](development.md). For what's shipped see
> [roadmap.md](roadmap.md).

---

## 1. What staging is for

| Goal | Staging delivers |
|---|---|
| CEO / franchise leadership review | Believable demo school (3 branches, students, fees, royalty, inspection, portals) |
| Sales / training dry-runs | Same seed, repeatable |
| Pre-production smoke | Fresh-install path + review seed before a production cut |

Staging is **not** production. It uses a shared review password, demo PII, and
can be wiped and re-seeded at any time.

---

## 2. Frappe Cloud plan (initial recommendation)

Use a **Sites** plan with a **Private Bench** — not a Server VM — for a
single CEO-review site. Pricing reference:
[frappe.io/cloud/pricing](https://frappe.io/cloud/pricing).

### Why not the $5 / $10 tiers?

`myschools` is a **custom app**. Frappe Cloud's cheapest shared-bench tiers only
allow marketplace apps; custom-app deployment requires a **Private Bench**, which
starts at **$25/mo** on the Sites family. See
[Frappe Cloud shared hosting](https://frappe.io/cloud/shared-hosting) (Shared vs
Private comparison).

### Recommended tier

| Choice | Recommendation |
|---|---|
| **Plan family** | **Sites** (not Servers). Servers ($20+/mo VM) pay off when you host multiple sites/benches; one throwaway review site is cheaper on Sites. |
| **Tier** | **$38/mo** — 3 CPU-hr/day, **1.5 GB DB**, 37.5 GB storage. Safer headroom for six apps + demo seed. **$25/mo** works if DB stays under ~850 MB after install (check Analytics). |
| **Bench type** | **Private** (mandatory for `myschools`) |
| **Region** | **AWS Mumbai** (`ap-south-1`) — lowest latency to Lahore reviewers |
| **Provider** | **AWS**, not Hetzner — Hetzner is cheaper but EU-only; fine for dev, sluggish for a live PK demo |

Sites tier limits (Private bench eligible from $25 upward):

| Plan | CPU / day | DB | Storage |
|---|---|---|---|
| $25/mo | 2.0 hr | 1.0 GB | 25 GB |
| **$38/mo** | **3.0 hr** | **1.5 GB** | **37.5 GB** |
| $50/mo | 4.0 hr | 2.0 GB | 50 GB |

### Billing model (important for short reviews)

Frappe Cloud bills **per active day**, not upfront for the full month:

- Daily rate = plan price ÷ 30 (e.g. $38 ÷ 30 ≈ **$1.27/day**).
- You are charged for **each calendar day the site exists**, regardless of how
  many hours the CEO actually clicks around.
- Charges accumulate and are invoiced at **month-end** (card or prepaid credit
  wallet) — choosing $38 does **not** charge $38 immediately.
- **Delete the site** to stop billing. Idle sites still accrue ~$1.27/day.

**Example — 2-day CEO review on $38:**

```text
2 days × ($38 / 30) ≈ $2.54 total
```

Then delete the site (see §10) → $0 further charges.

**Payment tip for throwaway demos:** load a small **prepaid credit** balance
($5–10) so a short review cannot surprise you at month-end.

Upgrade path: when production goes live, clone the **app pin set** from staging
to a second production site on the same bench (or a larger plan), not the
database.

---

## 3. App pins (must match CI)

These branches are what CI installs today (see
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml)). Pin the **same**
refs on Frappe Cloud or you risk "works in CI, breaks on staging."

| App | Branch / tag | Notes |
|---|---|---|
| `frappe` | `version-15` | Bench base |
| `erpnext` | `version-15` | Required by `myschools` |
| `education` | `version-15.2` | SIS / Fees engine |
| `hrms` | `version-15` | Staff / Employee |
| `payments` | `version-15` | Fee gateway stubs (Phase 8e) |
| `lms` | `v2.55.0` | Upstream LMS SPA (`/lms`) |
| **`myschools`** | `develop` (then release tags) | This repo — install **last** |

`myschools/hooks.py` declares:

```python
required_apps = ["erpnext", "education", "hrms", "payments", "lms"]
```

Frappe Cloud will refuse `install-app myschools` until all five upstream apps
are present.

### Install order (fresh site)

```text
erpnext → hrms → education → payments → lms → myschools
```

Then:

```bash
bench --site <site> migrate
```

`myschools` fixtures import on migrate (`after_migrate` / fixture sync) — no
manual "Import" step for workspaces, workflows, or print formats.

---

## 4. Frappe Cloud — step-by-step

### 4.1 Create the bench & site

1. Log in to [frappecloud.com](https://frappecloud.com) → **New Site**.
2. Choose a **Sites** plan — **$38/mo Private Bench** recommended (see §2).
3. Site name: `staging.myschools.pk` (or your review subdomain).
4. Frappe version: **v15**.
5. Connect the GitHub repo `darulmasaadir/myschools` (or your fork) and set the
   app path to `frappe-bench/apps/myschools` if prompted.

### 4.2 Add upstream apps

On the bench **Apps** screen (or via `bench get-app` in a Server SSH session),
add each upstream app at the pins in §3 **before** installing `myschools`.

Typical Frappe Cloud UI flow:

1. **Add App** → `erpnext` @ `version-15` → Install on site.
2. Repeat for `hrms`, `education`, `payments`, `lms` at the pinned branches.
3. **Add App** → `myschools` from your connected repo @ `develop`.
4. **Install** `myschools` on the staging site.
5. **Migrate** (UI button or `bench migrate`).

### 4.3 Build assets

After the first install or any JS/CSS change:

```bash
bench build --app myschools
```

Frappe Cloud usually runs this on deploy; if portal pages look unstyled, trigger
a **Rebuild Assets** from the site dashboard.

### 4.4 DNS (optional for first review)

Frappe Cloud provides a `*.frappe.cloud` URL immediately — sufficient for an
internal CEO walk. Point `staging.myschools.pk` CNAME at the FC hostname when
you want a branded URL.

---

## 5. Review seed (one command)

After a clean install + migrate, load believable demo data and print reviewer
logins:

```bash
bench --site staging.myschools.pk execute myschools.scripts.seed_staging_review.run
```

Custom password (recommended — rotate per review cycle):

```bash
bench --site staging.myschools.pk execute \
  myschools.scripts.seed_staging_review.run \
  --kwargs '{"password": "Demo@2026"}'
```

### What the seed chains (all idempotent)

| Step | Script | Creates |
|---|---|---|
| 1 | `seed_demo` | Franchise tree (3 clusters / 3 branches / campuses), Companies, royalty agreement + rate overrides |
| 2 | `seed_education` | Academic year/term, programs, ~30 students, submitted **Fees** |
| 3 | `demo_royalty_invoice` | Draft royalty invoices rolled up from real Fees (May 2026) |
| 4 | `seed_test_users` | One System User per franchise role |
| 5 | `seed_portal_teacher` | Teacher class + schedule + assessment, guardian children, transport, library loan, compliance document, LMS course |

The command ends with a printed **access guide** (URL, role, email, what to
click). Default password: `myschool-review`.

### Reviewer walk — quick reference

| Surface | Login | Password |
|---|---|---|
| CEO desk | `ceo@mys.local` | shared review password |
| Branch Director desk | `branch.dir@mys.local` | same |
| Branch Accountant | `accountant@mys.local` | same |
| Academic Monitor | `monitor@mys.local` | same |
| Teacher portal | `e2e_teacher@mys.local` | same |
| Guardian portal | `e2e_guardian@mys.local` | same |
| LMS (`/lms`) | `e2e_teacher@mys.local` | same |
| PWA install | Open `/guardian` or `/teacher` on phone → **Add to Home Screen** | — |

Full table is printed by the seed script; do not commit real passwords to git.

---

## 6. Post-deploy smoke

Run on the staging site after seeding:

```bash
# HTTP smoke (Administrator session)
bench --site staging.myschools.pk execute myschools.scripts.verify_http_battery.run

# Role × surface matrices
bench --site staging.myschools.pk execute myschools.scripts.verify_branch_desk_cards.run
bench --site staging.myschools.pk execute myschools.scripts.verify_pwa_surfaces.run
bench --site staging.myschools.pk execute myschools.scripts.verify_lms_surfaces.run
```

Manual (5b) — log in as `ceo@mys.local` and `e2e_guardian@mys.local`; confirm
desk cards render and guardian fees/timetable/transport/library pages load.

---

## 7. Deploying updates from `develop`

1. Merge feature PRs to `develop` (CI green on the merge commit).
2. On Frappe Cloud → **Deploy** → select the new `develop` commit (or tag).
3. `bench migrate` runs automatically on deploy.
4. If only Python/fixtures changed, re-run the review seed (idempotent) to
   refresh demo passwords after user rows change.
5. If JS/CSS/public assets changed, confirm **Rebuild Assets** ran.

**Do not** copy a dev-site database dump to staging — fixture drift and local
test users will leak. Always: fresh site → install apps → migrate → review seed.

---

## 8. Security & data hygiene

- **Shared password** — rotate via `--kwargs '{"password": "..."}'` each review
  cycle; revoke site access when review ends.
- **No real CNIC / child data** — seed uses synthetic emails (`@mys.local`,
  `@example.test`).
- **Email** — disable outbound email on staging (Frappe Cloud → Email Settings)
  or use a sink address so royalty/inspection notifications don't reach real
  inboxes.
- **Backups** — enable FC daily backups before inviting external reviewers.

---

## 9. Go / no-go before inviting the CEO

| Check | Command / action |
|---|---|
| All six apps installed | Site → Installed Apps lists `myschools` + five upstream |
| Migrate clean | No traceback in migrate log |
| Review seed printed guide | `seed_staging_review.run` exit 0 |
| HTTP battery | `verify_http_battery.run` exit 0 |
| CEO login works | Browser: `ceo@mys.local` → Central workspace |
| Guardian portal works | Browser: `e2e_guardian@mys.local` → fees + timetable |
| PWA manifest | `GET /assets/myschools/pwa/manifest.json` → 200 |
| CI on deployed commit | `develop` commit SHA matches what FC deployed |

---

## 10. Teardown after review (cost control)

When the CEO walk is done, **delete the site** — do not leave it running idle.
Billing stops only when the site no longer exists (see §2 billing model).

### 10.1 Optional backup (only if you need a snapshot)

The review environment is fully reproducible from code + `seed_staging_review`
(§5). A database backup is **optional** — skip it unless you have staging-only
changes you cannot recreate.

If you want a snapshot anyway:

1. Frappe Cloud dashboard → your site → **Backups**.
2. Click **Download** on the latest backup (or trigger **Backup Now** first).
3. Store the file locally; it is **not** needed to redeploy the demo.

### 10.2 Delete the site (stops billing)

1. Frappe Cloud dashboard → your site → **Settings** (or site actions menu).
2. **Delete Site** → confirm.

After deletion:

- No further daily charges for that site.
- The `*.frappe.cloud` URL and any custom DNS CNAME stop working.
- Demo users, seeded data, and review passwords are gone — by design.

**Do not** rely on "turning off" or ignoring the site; existence = billing.

### 10.3 Redeploy for a future review

Because the demo is seed-driven, spinning up again is cheap:

1. Create a new site on the same plan tier (§2, §4).
2. Install apps in order (§3).
3. Run `seed_staging_review.run` with a fresh password (§5).
4. Run post-deploy smoke (§6).

Total cost for another 2-day window: again ≈ **$2.54** on $38/mo — no standing
monthly fee between reviews.

### 10.4 Teardown checklist

| Step | Done? |
|---|---|
| CEO / reviewers finished | ☐ |
| Optional backup downloaded | ☐ |
| Outbound email already disabled (§8) | ☐ |
| Site deleted in Frappe Cloud | ☐ |
| Custom DNS CNAME removed (if used) | ☐ |
| Review password rotated / discarded | ☐ |

---

## 11. Production (later)

Production cut is a **separate** site with:

- Real companies / branches imported via setup wizard (not `seed_demo`)
- Real users provisioned individually (not `seed_test_users`)
- Payment gateway live keys (Phase 8e stubs → production credentials)
- Staging app pins promoted to a **release tag** on `myschools`

Document the production runbook in this file when that cut happens; until then,
treat staging as the only deployment target.
