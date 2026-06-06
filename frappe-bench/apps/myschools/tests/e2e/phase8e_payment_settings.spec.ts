/**
 * Phase 8e — payment gateways (browser regression).
 *
 * Two surfaces:
 *  1. MYS Payment Settings single — provider select + depends_on credential fields.
 *  2. The full fee-payment happy path — initiate_fee_payment through the REAL
 *     whitelisted endpoint in a live desk session, follow the Stub provider's
 *     redirect (guest callback web page), then assert the MYS Communication Log
 *     audit row landed (channel=Payment, status=Sent, gateway=stub). This is the
 *     end-to-end path a payer's "Pay now" would drive, not just the settings form.
 *
 * Pre-req for the happy-path test: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect, Page } from "@playwright/test";
import { loadSeed, setFormValue } from "./fixtures";

const seed = loadSeed();

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

test.describe("Phase 8e — fee payment happy path (Stub)", () => {
	test.skip(!seed.payment?.fees, "run seed_e2e.main first (no submitted Fees in seed)");

	test("initiate_fee_payment dispatches, redirects, and writes the audit log", async ({
		page,
	}) => {
		const fees = seed.payment!.fees;
		const branch = seed.payment!.branch;

		await loginAdmin(page);

		// Force the Stub provider so the path is deterministic regardless of prior tests.
		await page.goto("/app/mys-payment-settings");
		await page.waitForFunction(() => Boolean((window as any).cur_frm?.doc), undefined, {
			timeout: 15_000,
		});
		await setFormValue(page, "payment_provider", "Stub");
		await saveSingle(page);

		// 1. Drive the REAL whitelisted endpoint from the live desk session
		//    (same request path, CSRF + cookies, that a "Pay now" button would use).
		const dispatch = await page.evaluate(async (feesName) => {
			const r = await (window as any).frappe.call({
				method: "myschools.api.payments.initiate_fee_payment",
				args: { fees: feesName },
			});
			return r.message;
		}, fees);

		expect(dispatch.ok).toBe(true);
		expect(dispatch.gateway).toBe("stub");
		expect(dispatch.payment_url).toContain("stub_payment_complete");
		expect(dispatch.log).toBeTruthy();

		// 2. Follow the provider redirect — the Stub guest callback web page.
		await page.goto(dispatch.payment_url);
		await expect(page.locator("body")).toContainText("No funds were collected", {
			timeout: 15_000,
		});

		// 3. Assert the audit trail row exists and is correctly scoped.
		const logRow = await page.evaluate(async (logName) => {
			const r = await (window as any).frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "MYS Communication Log",
					filters: { name: logName },
					fieldname: ["channel", "status", "gateway", "branch"],
				},
			});
			return r.message;
		}, dispatch.log);

		expect(logRow.channel).toBe("Payment");
		expect(logRow.status).toBe("Sent");
		expect(logRow.gateway).toBe("stub");
		expect(logRow.branch).toBe(branch);
	});
});
