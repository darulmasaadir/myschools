"""Staging review seed — pure access-guide builder.

The full seed is exercised manually on a staging site (it chains the heavy
demo seeds); here we only lock down the credential table the reviewer relies
on, so a stray edit can't silently drop a login or break the password column.

Run:
    bench --site SITE run-tests --app myschools \\
        --module myschools.tests.test_seed_staging_review
"""

from frappe.tests.utils import FrappeTestCase

from myschools.scripts.seed_staging_review import (
	DEFAULT_PASSWORD,
	PORTAL_LOGINS,
	build_access_guide,
)


class TestStagingReviewGuide(FrappeTestCase):
	def test_guide_covers_every_review_surface(self):
		guide = build_access_guide("secret123")
		urls = {row["url"] for row in guide}
		for surface in ("/app", "/teacher", "/guardian", "/lms"):
			self.assertIn(surface, urls, f"review guide missing {surface}")

	def test_guide_includes_ceo_login(self):
		guide = build_access_guide(DEFAULT_PASSWORD)
		ceo = [row for row in guide if row["email"] == "ceo@mys.local"]
		self.assertEqual(len(ceo), 1)
		self.assertEqual(ceo[0]["role"], "Chief Executive")

	def test_password_propagates_to_every_row(self):
		guide = build_access_guide("Demo@2026")
		self.assertTrue(guide)
		self.assertTrue(all(row["password"] == "Demo@2026" for row in guide))

	def test_portal_logins_are_in_the_guide(self):
		emails = {row["email"] for row in build_access_guide(DEFAULT_PASSWORD)}
		for portal_user in PORTAL_LOGINS:
			self.assertIn(portal_user, emails)
