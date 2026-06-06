/**
 * Phase 8e — MYS Payment Settings single (browser regression).
 */
import { test, expect, Page } from "@playwright/test";
import { setFormValue } from "./fixtures";

async function loginAdmin(page: Page) {
	await page.goto("/login");
	await page.fill('input[name="login_email"], input#login_email', "Administrator");
	await page.fill('input[name="login_password"], input#login_password', "admin");
	await page.locator('button.btn-login, button:has-text("Login")').first().click();
	await page.waitForURL(/\/app(\/|$)/, { timeout: 20_000 });
	await expect(page.locator(".navbar, .standard-sidebar").first()).toBeVisible({
		timeout: 15_000,
	});
}

async function saveSingle(page: Page) {
	await page.keyboard.press("Control+s");
	await page.waitForFunction(() => !(window as any).cur_frm?.is_dirty(), undefined, {
		timeout: 20_000,
	});
}

test.describe("Phase 8e — MYS Payment Settings", () => {
	test("Administrator opens settings, defaults to Stub, saves", async ({ page }) => {
		await loginAdmin(page);
		await page.goto("/app/mys-payment-settings");
		await page.waitForFunction(() => Boolean((window as any).cur_frm?.doc), undefined, {
			timeout: 15_000,
		});
		await setFormValue(page, "payment_provider", "Stub");
		await saveSingle(page);
		const provider = await page.evaluate(() => (window as any).cur_frm.doc.payment_provider);
		expect(provider).toBe("Stub");
	});

	test("switching to JazzCash reveals JazzCash fields", async ({ page }) => {
		await loginAdmin(page);
		await page.goto("/app/mys-payment-settings");
		await page.waitForFunction(() => Boolean((window as any).cur_frm?.doc), undefined, {
			timeout: 15_000,
		});
		await setFormValue(page, "payment_provider", "JazzCash");
		await expect(page.locator('[data-fieldname="jazzcash_merchant_id"]').first()).toBeVisible({
			timeout: 10_000,
		});
		await setFormValue(page, "payment_provider", "Stub");
		await saveSingle(page);
	});
});
