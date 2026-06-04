/**
 * Phase 8a — MYS Bulk Fee Run desk + Generate Fees button (browser regression).
 *
 * Exercises frappe.call in mys_bulk_fee_run.js (not only the Python unit test).
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect, Page } from "@playwright/test";
import { loadSeed, loginAs, setFormValue, saveForm } from "./fixtures";

const seed = loadSeed();
const accountant = "e2e_accountant@mys.local";
const monitor = "e2e_monitor@mys.local";

function accountantPassword() {
	return seed.users[accountant].password;
}

function monitorPassword() {
	return seed.users[monitor].password;
}

async function generateAndExpectCreated(page: Page) {
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
		page.locator('[data-fieldname="lines"] .grid-row').filter({ hasText: "Created" }).first(),
	).toBeVisible({ timeout: 15_000 });
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
		await generateAndExpectCreated(page);
	});

	test("Branch Accountant: new run from blank → save → Generate Fees", async ({ page }) => {
		const bf = seed.bulk_fee!;
		await loginAs(page, accountant, accountantPassword());
		await page.goto("/app/mys-bulk-fee-run/new");
		await setFormValue(page, "branch", bf.branch);
		await setFormValue(page, "student_group", bf.student_group);
		await setFormValue(page, "academic_year", bf.academic_year);
		await setFormValue(page, "academic_term", bf.academic_term);
		// Distinct dates so this run bills fresh Fees instead of skipping rows the
		// seeded-draft spec already billed.
		await setFormValue(page, "posting_date", bf.posting_date_2);
		await setFormValue(page, "due_date", bf.due_date_2);
		await saveForm(page);

		// Company is fetched from Branch — proves fetch_from ran.
		await expect(page.locator('.form-page [data-fieldname="company"]')).toContainText(/\S/);
		await generateAndExpectCreated(page);
	});

	test("Academic Monitor is denied on Bulk Fee Run list", async ({ page }) => {
		await loginAs(page, monitor, monitorPassword());
		await page.goto("/app/mys-bulk-fee-run");
		await expect(
			page
				.locator("text=/Not permitted|Not allowed|Insufficient Permission|does not have access/i")
				.first(),
		).toBeVisible({ timeout: 15_000 });
	});
});
