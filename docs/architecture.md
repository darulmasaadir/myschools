# MY School ERP — Architecture Notes

Source of truth for design decisions while we build the custom `myschools` Frappe app on top of `frappe/education` v15.

## 1. Stack

- **Framework:** Frappe v15 (Python 3.12, Node 20, MariaDB 10.6+, Redis)
- **Base apps installed:** `frappe`, `erpnext` (Education's hard dependency), `education`
- **Our custom app:** `myschools` (lives in `frappe-bench/apps/myschools/`) — all customisation goes here, upstream apps stay untouched so we can `git pull` them later.
- **Optional later:** `hrms` (richer payroll), `lms` (digital learning), `payments` (Razorpay / JazzCash gateway).

## 2. Franchise hierarchy

```
Head Office (Chief Executive + Dept Heads)
   └── Cluster (MYS-CL01, MYS-CL02, ...)
         └── Branch (BR001, BR014, ...)
               └── Campus (Junior / Kids / Senior)
                     └── Student / Teacher / Admin staff
                           └── Parent (Guardian) — read-only via portal
```

## 3. Custom DocTypes (in `myschools` app, module `MY School Franchise`)

| DocType | Naming | Key fields |
|---|---|---|
| `MYS Cluster` | `MYS-CL{##}` | cluster_code, cluster_name, region, cluster_director (Link Employee), academic_monitor, audit_officer |
| `MYS Branch` | `MYS-{cluster_code}-BR{###}` | branch_code, branch_name, cluster (Link), address, city, branch_director, branch_principal, branch_admin, branch_accountant |
| `MYS Campus` | `{branch}-{campus_type}` | campus_type (Junior/Kids/Senior), branch (Link), campus_incharge (Link Employee) |
| `MYS Department` | autoname field:dept_name | dept_name (Monitoring/Academic/Finance/Training/Admin), head_of_department |
| `MYS Inspection Visit` | `INSP-.YYYY.-.####` | branch, visit_date, inspector, scorecard (Table), summary, status |
| `MYS Communication Log` | `COMM-.YYYY.-.######` | sender, recipient_role, channel (SMS/Email/Push/In-App), subject, body, status, sent_at |

## 4. Custom fields on upstream DocTypes (via Customize Form / fixtures)

- `Student`: mys_cluster (Link), mys_branch (Link, fetch from cluster), mys_campus (Link), mys_student_id (Data, auto-generated as `MYS-{cluster_code}-{branch_code}-STU{######}`)
- `Employee`: mys_branch, mys_campus, mys_role_tier (Select: Head Office / Cluster / Branch / Campus), mys_staff_id (`MYS-{branch_code}-{role_code}{####}`)
- `Guardian`: mys_branch (so parent portal only sees their branch's students)

## 5. Role model

New roles (in addition to upstream Student / Instructor / Guardian / Education Manager):

- **Chief Executive** — global read on everything
- **HO Dept Head** — global read on their dept's reports
- **Cluster Director** — read/write within their cluster only
- **Academic Monitor**, **Audit Officer** — cluster-scoped, monitoring DocTypes only
- **Branch Director**, **Branch Principal**, **Branch Admin**, **Branch Accountant** — branch-scoped, role-specific perms
- **Campus Incharge** — campus-scoped
- **Parent (Guardian)** — existing role, scoped to own students

### Permission strategy
Branch / campus scoping is enforced with **Permission Query Conditions** (Python hooks in `myschools/permissions.py`). Each scoped role gets a filter like `student.mys_branch IN (current_user_branches())`.

## 6. ID generation logic

Implemented as a `before_insert` hook on Student / Employee:

```python
def set_mys_student_id(doc, method):
    cluster = frappe.get_doc("MYS Cluster", doc.mys_cluster)
    branch  = frappe.get_doc("MYS Branch",  doc.mys_branch)
    seq = frappe.db.count("Student", {"mys_branch": doc.mys_branch}) + 1
    doc.mys_student_id = f"MYS-{cluster.cluster_code}-{branch.branch_code}-STU{seq:06d}"
```

## 7. Modules-to-coverage map (PDF's 22 modules)

| # | Module | Coverage |
|---|---|---|
| 1 | Master Setup | Frappe core (Settings, DocType, Workspace) |
| 2 | Franchise Management | **Custom** — Cluster/Branch/Campus DocTypes |
| 3 | Student Information System | `education` Student + custom fields |
| 4 | HR / Staff Management | `erpnext` Employee + `hrms` (optional) |
| 5 | Campus Management | **Custom** — MYS Campus |
| 6 | Academic Management | `education` Program / Course / Topic |
| 7 | Examination System | `education` Assessment Plan / Result |
| 8 | Attendance System | `education` Student Attendance + `erpnext` Employee Attendance |
| 9 | Finance / Fee Management | `education` Fees + `erpnext` Accounts |
| 10 | Parent Portal | `education` Student Portal extended for guardians |
| 11 | Teacher Portal | `education` Instructor portal |
| 12 | Communication System | **Custom** — MYS Communication Log + Frappe email/SMS |
| 13 | Monitoring & Inspection | **Custom** — MYS Inspection Visit |
| 15 | Transport | `erpnext` Vehicle + Frappe Geo (or custom later) |
| 16 | Library | `erpnext` Stock or custom Library Member/Loan |
| 17 | LMS / Digital Learning | `frappe/lms` (install separately) |
| 18 | Document Management | Frappe File + folders per branch |
| 19 | Security / Role Control | Frappe Roles + Permission Query Conditions |
| 20 | Mobile App | `education` already has a frontend SPA; PWA-ready |
| 21 | Unique ID System | **Custom** — hook on Student/Employee |
| 22 | Reporting System | Frappe Report Builder + Frappe Insights (optional) |
