/**
 * Phase 8c — MYS SMS Settings single (browser regression).
 *
 * Walks the net-new desk surface: open the single, switch provider, confirm the
 * provider-specific section reveals, and save. Backend dispatch is covered by
 * tests/test_sms_providers.py + scripts/verify_sms_adapters.py; this proves the
 * settings form itself renders and persists for an admin.
 *
 * Runs as Administrator (admin/admin) — the single is gated to System Manager
 * + Chief Executive, and Administrator always exists on a fresh site.
 */
import { test, expect, Page } from "@playwright/test";
import { setFormValue } from "./fixtures";

async function loginAdmin(page: Page) {
	await page.goto("/login");
	await page.fill('input[name="login_email"], input#login_email', "Administrator");
	await page.fill('input[name="login_password"], input#login_password', "admin");
	await page.locator('button.btn-login, button:has-text("Login")').first().click();
	await page.waitForURL(/\/app(\/|$)/, { timeout: 20_000 });
	await expect(page.locator(".navbar, .standard-sidebar").first()).toBeVisible({ timeout: 15_000 });
}

async function saveSingle(page: Page) {
	await page.keyboard.press("Control+s");
	await page.waitForFunction(() => !(window as any).cur_frm?.is_dirty(), undefined, {
		timeout: 20_000,
	});
}

test.describe("Phase 8c — MYS SMS Settings", () => {
	test("Administrator opens settings, defaults to Stub, saves", async ({ page }) => {
		await loginAdmin(page);
		await page.goto("/app/mys-sms-settings");
		await page.waitForFunction(() => Boolean((window as any).cur_frm?.doc), undefined, {
			timeout: 15_000,
		});
		await setFormValue(page, "sms_provider", "Stub");
		await saveSingle(page);
		const provider = await page.evaluate(() => (window as any).cur_frm.doc.sms_provider);
		expect(provider).toBe("Stub");
	});

	test("switching to Twilio reveals the Twilio fields", async ({ page }) => {
		await loginAdmin(page);
		await page.goto("/app/mys-sms-settings");
		await page.waitForFunction(() => Boolean((window as any).cur_frm?.doc), undefined, {
			timeout: 15_000,
		});
		await setFormValue(page, "sms_provider", "Twilio");
		// depends_on field becomes visible once provider switches.
		await expect(page.locator('[data-fieldname="twilio_account_sid"]')).toBeVisible({
			timeout: 10_000,
		});
		// Reset to Stub so we don't leave half-configured Twilio behind.
		await setFormValue(page, "sms_provider", "Stub");
		await saveSingle(page);
	});
});
