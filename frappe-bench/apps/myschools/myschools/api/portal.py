"""MY School website portal routing helpers.

Phase 7 portals are Frappe `www/` pages + Web Forms (no custom SPA). This module
holds the role → landing-path map used by `/portal` and future portal pages.
"""

from __future__ import annotations

import frappe

# First matching role wins (ordered: parent/guardian before staff portals).
PORTAL_ROUTE_BY_ROLE: tuple[tuple[str, str], ...] = (
	("Guardian", "/guardian"),
	("Audit Officer", "/inspection"),
	("Academic Monitor", "/inspection"),
	("Teacher", "/teacher"),
	("Branch Director", "/branch"),
	("Branch Principal", "/branch"),
	("Branch Admin", "/branch"),
	("Branch Accountant", "/branch"),
	("Campus Incharge", "/branch"),
)


def get_portal_redirect(roles: list[str] | set[str] | None) -> str | None:
	"""Return the portal home path for the highest-priority portal role present."""
	role_set = set(roles or [])
	for role, path in PORTAL_ROUTE_BY_ROLE:
		if role in role_set:
			return path
	return None


def redirect_to_portal_home() -> None:
	"""Send the current session user to their portal slice, or raise PermissionError."""
	dest = get_portal_redirect(frappe.get_roles())
	if not dest:
		frappe.throw("You do not have access to the MY School portal.", frappe.PermissionError)
	frappe.local.flags.redirect_location = dest
	raise frappe.Redirect


def redirect_guest_to_login() -> None:
	frappe.local.flags.redirect_location = "/login?redirect-to=/portal"
	raise frappe.Redirect
