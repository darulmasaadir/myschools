"""Phase 16 — portal PWA (manifest, service worker route, portal detection).

Run:
    bench --site SITE run-tests --app myschools --module myschools.tests.test_pwa
"""

import json
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from myschools.api.pwa import (
	MANIFEST_PATH,
	SW_ROUTE,
	ServiceWorkerPageRenderer,
	is_portal_path,
	load_manifest,
)


class TestPwaHelpers(FrappeTestCase):
	def test_is_portal_path_guardian_and_teacher(self):
		self.assertTrue(is_portal_path("/guardian"))
		self.assertTrue(is_portal_path("/guardian/fees"))
		self.assertTrue(is_portal_path("/student"))
		self.assertTrue(is_portal_path("/student/fees"))
		self.assertTrue(is_portal_path("/teacher/schedule"))
		self.assertTrue(is_portal_path("/branch/timetable"))
		self.assertTrue(is_portal_path("/inspection/visits"))
		self.assertTrue(is_portal_path("/portal"))

	def test_is_portal_path_rejects_desk_and_guest(self):
		self.assertFalse(is_portal_path("/app"))
		self.assertFalse(is_portal_path("/login"))
		self.assertFalse(is_portal_path("/admission-enquiry"))

	def test_manifest_has_required_install_fields(self):
		manifest = load_manifest()
		self.assertEqual(manifest["name"], "MY School")
		self.assertEqual(manifest["start_url"], "/portal")
		self.assertEqual(manifest["display"], "standalone")
		self.assertEqual(manifest["theme_color"], "#0f7a4a")
		self.assertTrue(manifest.get("icons"))

	def test_service_worker_renderer_matches_route(self):
		renderer = ServiceWorkerPageRenderer(SW_ROUTE)
		self.assertTrue(renderer.can_render())
		self.assertFalse(ServiceWorkerPageRenderer("guardian").can_render())

	def test_service_worker_renderer_returns_javascript(self):
		renderer = ServiceWorkerPageRenderer(SW_ROUTE)
		response = renderer.render()
		self.assertIn("javascript", response.mimetype or "")
		self.assertEqual(response.headers.get("Service-Worker-Allowed"), "/")
		self.assertIn(b"addEventListener", response.get_data())

	def test_portal_base_template_links_manifest(self):
		path = Path(frappe.get_app_path("myschools", "templates", "pages", "mys_portal_base.html"))
		html = path.read_text(encoding="utf-8")
		self.assertIn(MANIFEST_PATH, html)
		self.assertIn('name="theme-color"', html)
		self.assertIn("portal_pwa.js", html)

	def test_manifest_json_is_valid_on_disk(self):
		path = frappe.get_app_path("myschools", "public", "pwa", "manifest.json")
		with open(path, encoding="utf-8") as handle:
			data = json.load(handle)
		self.assertIn("short_name", data)
