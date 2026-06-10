"""Role x surface verification for Phase 16 PWA (run via bench execute).

  bench --site SITE execute myschools.scripts.verify_pwa_surfaces.run

Asserts:
  1. Web manifest is valid and names MY School.
  2. Service worker route returns JavaScript with Service-Worker-Allowed header.
  3. Guardian portal HTML links the manifest and registers portal_pwa.js.
"""

from __future__ import annotations

from pathlib import Path

import frappe

from myschools.api.pwa import MANIFEST_PATH, SW_ROUTE, ServiceWorkerPageRenderer, load_manifest

GUARDIAN = "e2e_guardian@mys.local"


def run():
	failures: list[str] = []
	_check_manifest(failures)
	_check_service_worker_renderer(failures)
	_check_guardian_portal_markup(failures)

	if failures:
		print("FAILED —", len(failures), "issue(s):")
		for item in failures:
			print(f"  ✗ {item}")
		frappe.throw("PWA role x surface verification failed")
	print(f"OK — PWA surfaces verified (manifest, {SW_ROUTE}, guardian portal)")


def _check_manifest(failures: list[str]) -> None:
	try:
		manifest = load_manifest()
	except Exception as exc:
		failures.append(f"manifest load failed: {exc}")
		return
	if manifest.get("name") != "MY School":
		failures.append(f"manifest name unexpected: {manifest.get('name')!r}")
	if manifest.get("start_url") != "/portal":
		failures.append(f"manifest start_url unexpected: {manifest.get('start_url')!r}")
	if not manifest.get("icons"):
		failures.append("manifest missing icons")


def _check_service_worker_renderer(failures: list[str]) -> None:
	renderer = ServiceWorkerPageRenderer(SW_ROUTE)
	if not renderer.can_render():
		failures.append(f"{SW_ROUTE}: ServiceWorkerPageRenderer.can_render returned False")
		return
	response = renderer.render()
	if "javascript" not in (response.mimetype or ""):
		failures.append(f"{SW_ROUTE}: unexpected mimetype {response.mimetype!r}")
	if response.headers.get("Service-Worker-Allowed") != "/":
		failures.append(f"{SW_ROUTE}: missing Service-Worker-Allowed header")


def _check_guardian_portal_markup(failures: list[str]) -> None:
	path = Path(frappe.get_app_path("myschools", "templates", "pages", "mys_portal_base.html"))
	html = path.read_text(encoding="utf-8")
	if MANIFEST_PATH not in html:
		failures.append("portal base template missing manifest link")
	if "portal_pwa.js" not in html:
		failures.append("portal base template missing portal_pwa.js")
	if 'name="theme-color"' not in html:
		failures.append("portal base template missing theme-color meta")
