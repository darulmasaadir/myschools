/**
 * Phase 8a — MYS Bulk Fee Run desk + Generate Fees button (browser regression).
 *
 * Exercises frappe.call in mys_bulk_fee_run.js (not only the Python unit test).
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect } from "@playwright/test";
import { loadSeed, loginAs } from "./fixtures";

const seed = loadSeed();
const accountant = "e2e_accountant@mys.local";
const monitor = "e2e_monitor@mys.local";

function accountantPassword() {
	return seed.users[accountant].password;
}

function monitorPassword() {
	return seed.users[monitor].password;
}

test.describe("Phase 8a — Bulk Fee Run", () => {
	test.skip(!seed.bulk_fee?.run, "run seed_e2e.main first (bulk_fee.run)");

	test("Branch Accountant: Generate Fees on seeded draft", async ({ page }) => {
		const run = seed.bulk_fee!.run;
		await loginAs(page, accountant, accountantPassword());
		await page.goto(`/app/mys-bulk-fee-run/${encodeURIComponent(run)}`);
		await expect(page.locator(".indicator-pill, .indicator").first()).toBeVisible({
			timeout: 15_000,
		});
		const statusField = page.locator('.form-page [data-fieldname="status"]').first();
		const generateBtn = page.locator('button:has-text("Generate Fees")');
		if (await generateBtn.isVisible().catch(() => false)) {
			await generateBtn.click();
		}
		await expect(statusField).toContainText(/Completed|Partial/, { timeout: 30_000 });
		await expect(page.locator('.form-page [data-fieldname="summary"]').first()).toContainText(
			/Created:/,
		);

		await expect(
			page
				.locator('[data-fieldname="lines"] .grid-row')
				.filter({ hasText: "Created" })
				.first(),
		).toBeVisible({ timeout: 15_000 });
	});

	test("Academic Monitor is denied on Bulk Fee Run list", async ({ page }) => {
		await loginAs(page, monitor, monitorPassword());
		await page.goto("/app/mys-bulk-fee-run");
		await expect(
			page.locator("text=/Not permitted|Not allowed|Insufficient Permission|does not have access/i").first(),
		).toBeVisible({ timeout: 15_000 });
	});
});
