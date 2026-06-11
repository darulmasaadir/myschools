"""MY School franchise role model — single source of truth (Phase 17).

Maps the Software Infrastructure document hierarchy to Frappe roles, landing
pages, and ``FRANCHISE_ROLE_READS`` grants. Import from here instead of
duplicating role name strings across install, seeds, and verify scripts.
"""

from __future__ import annotations

# Legacy role replaced by HO_DEPT_HEAD_ROLES (Phase 17a). Kept for migration only.
LEGACY_HO_DEPT_HEAD = "HO Dept Head"

HO_DEPT_HEAD_ROLES: tuple[str, ...] = (
	"Finance Dept Head",
	"Academic Dept Head",
	"Monitoring Dept Head",
	"Administration Dept Head",
	"Training Dept Head",
)

CAMPUS_ADMIN_ROLE = "Campus Admin"

FRANCHISE_ROLES: list[str] = [
	"Chief Executive",
	*HO_DEPT_HEAD_ROLES,
	"Cluster Director",
	"Academic Monitor",
	"Audit Officer",
	"Branch Director",
	"Branch Principal",
	"Branch Admin",
	"Branch Accountant",
	"Campus Incharge",
	CAMPUS_ADMIN_ROLE,
	"Teacher",
]

# Desk roles with national (unscoped) data window — see api.permissions.GLOBAL_ROLES.
GLOBAL_DESK_ROLES: frozenset[str] = frozenset({"Chief Executive", *HO_DEPT_HEAD_ROLES})

# Canonical seed logins per role (dev / staging review).
ROLE_SEED_USER: dict[str, str] = {
	"Chief Executive": "ceo@mys.local",
	"Finance Dept Head": "finance.head@mys.local",
	"Academic Dept Head": "academic.head@mys.local",
	"Monitoring Dept Head": "monitoring.head@mys.local",
	"Administration Dept Head": "admin.head@mys.local",
	"Training Dept Head": "training.head@mys.local",
	"Cluster Director": "cluster.dir@mys.local",
	"Academic Monitor": "monitor@mys.local",
	"Audit Officer": "audit@mys.local",
	"Branch Director": "branch.dir@mys.local",
	"Branch Principal": "principal@mys.local",
	"Branch Admin": "branch.admin@mys.local",
	"Branch Accountant": "accountant@mys.local",
	"Campus Incharge": "campus@mys.local",
	CAMPUS_ADMIN_ROLE: "campus.admin@mys.local",
	"Teacher": "e2e_teacher@mys.local",
	"Guardian": "e2e_guardian@mys.local",
	"Student": "e2e-student@mys.local",
}

# Positive functionality grants per HO dept head (national read unless noted).
_HO_BASE = [
	"MYS Cluster",
	"MYS Branch",
	"MYS Campus",
	"MYS Communication Log",
]

HO_DEPT_ROLE_READS: dict[str, list[str]] = {
	"Finance Dept Head": [
		*_HO_BASE,
		"MYS Department",
		"MYS Franchise Owner",
		"MYS Franchise Agreement",
		"MYS Royalty Rate Override",
		"MYS Royalty Invoice",
		"MYS Royalty Payment",
		"MYS Bulk Fee Run",
		"MYS Fee Structure Override",
		"MYS Late Fee Policy",
		"Student",
		"Fees",
		"Fee Structure",
		"Employee",
		"Guardian",
	],
	"Academic Dept Head": [
		*_HO_BASE,
		"Student",
		"Guardian",
		"Fees",
		"Fee Structure",
		"Program",
		"Program Enrollment",
		"Student Group",
		"Course Schedule",
		"Instructor",
		"Room",
		"Student Attendance",
		"Assessment Plan",
		"Assessment Result",
		"MYS Inspection Visit",
		"MYS Inspection Finding",
	],
	"Monitoring Dept Head": [
		*_HO_BASE,
		"MYS Inspection Checklist Template",
		"MYS Inspection Visit",
		"MYS Inspection Finding",
		"MYS Corrective Action",
		"MYS Document",
		"Student",
	],
	"Administration Dept Head": [
		*_HO_BASE,
		"MYS Department",
		"MYS Franchise Owner",
		"MYS Document",
		"Employee",
		"Guardian",
		"Student",
		"MYS Student Transfer",
		"MYS Student Leaving",
	],
	"Training Dept Head": [
		*_HO_BASE,
		"LMS Course",
		"Program",
		"Instructor",
		"Employee",
		"Student",
		"Course Schedule",
	],
}

CAMPUS_ADMIN_READS: list[str] = [
	"MYS Campus",
	"MYS Branch",
	"MYS Communication Log",
	"Student",
	"Guardian",
	"Student Attendance",
	"Program Enrollment",
	"Student Group",
]

STUDENT_PORTAL_READS: list[str] = [
	"Student",
	"Fees",
	"Student Attendance",
	"Course Schedule",
	"Assessment Result",
	"MYS Communication Log",
]
