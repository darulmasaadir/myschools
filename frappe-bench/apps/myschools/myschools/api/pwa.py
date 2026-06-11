"""Phase 16 — installable PWA shell for MY School portals.

Serves the service worker at ``/mys-pwa-sw.js`` via a custom page renderer so
the script is returned with ``application/javascript`` and a root scope header.
Portal pages link the web manifest and register the worker via ``portal_pwa.js``.
"""

from __future__ import annotations

import json
from pathlib import Path

import frappe
from werkzeug.wrappers import Response

SW_ROUTE = "mys-pwa-sw.js"
MANIFEST_PATH = "/assets/myschools/pwa/manifest.json"
PORTAL_PREFIXES = ("/guardian", "/teacher", "/student", "/branch", "/inspection", "/portal")


def is_portal_path(path: str | None) -> bool:
	"""Return True when *path* is a MY School portal route."""
	if not path:
		return False
	normalized = path if path.startswith("/") else f"/{path}"
	return any(normalized == prefix or normalized.startswith(f"{prefix}/") for prefix in PORTAL_PREFIXES)


def load_manifest() -> dict:
	"""Load the static web manifest (for tests and verification)."""
	path = Path(frappe.get_app_path("myschools", "public", "pwa", "manifest.json"))
	return json.loads(path.read_text(encoding="utf-8"))


def _sw_bytes() -> bytes:
	path = Path(frappe.get_app_path("myschools", "public", "pwa", "sw.js"))
	return path.read_bytes()


class ServiceWorkerPageRenderer:
	"""Frappe ``page_renderer`` hook — serves ``/mys-pwa-sw.js`` with correct headers."""

	__slots__ = ("http_status_code", "path")

	def __init__(self, path: str, http_status_code: int | None = None):
		self.path = path.strip("/ ")
		self.http_status_code = http_status_code or 200

	def can_render(self) -> bool:
		return self.path == SW_ROUTE

	def render(self) -> Response:
		response = Response(_sw_bytes(), mimetype="application/javascript; charset=utf-8")
		response.headers["Service-Worker-Allowed"] = "/"
		response.headers["Cache-Control"] = "no-cache"
		return response
