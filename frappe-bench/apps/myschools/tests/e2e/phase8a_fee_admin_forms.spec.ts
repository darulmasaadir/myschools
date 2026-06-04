/**
 * Phase 8a — fee-admin desk forms (browser regression).
 *
 * Proves the override / late-fee-policy forms render and save for Branch
 * Director, and that Branch Principal is denied — the role × surface matrix
 * codified in scripts/verify_fee_admin_surfaces.py, walked in a real browser.
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect } from "@playwright/test";
import { loadSeed, loginAs, setFormValue, saveForm } from "./fixtures";

const seed = loadSeed();
const director = "e2e_director@mys.local";

function directorPassword() {
	return seed.users[director].password;
}

test.describe("Phase 8a — Fee admin forms", () => {
	test.skip(!seed.bulk_fee?.fee_structure, "run seed_e2e.main first (bulk_fee.fee_structure)");

	test("Branch Director creates a Fee Structure Override", async ({ page }) => {
		const bf = seed.bulk_fee!;
		await loginAs(page, director, directorPassword());
		await page.goto("/app/mys-fee-structure-override/new");
		await setFormValue(page, "branch", bf.branch);
		await setFormValue(page, "program", bf.program);
		await setFormValue(page, "academic_year", bf.academic_year);
		await setFormValue(page, "fee_structure", bf.fee_structure!);
		await setFormValue(page, "effective_from", bf.posting_date);
		await setFormValue(page, "is_active", "1");
		await saveForm(page);

		await expect(page).toHaveURL(/\/app\/mys-fee-structure-override\/FSO-/);
	});

	test("Branch Director creates a Late Fee Policy", async ({ page }) => {
		const bf = seed.bulk_fee!;
		await loginAs(page, director, directorPassword());
		await page.goto("/app/mys-late-fee-policy/new");
		await setFormValue(page, "branch", bf.branch);
		await setFormValue(page, "grace_days", "7");
		await setFormValue(page, "late_fee_percent", "5");
		await setFormValue(page, "fees_category", bf.fee_category);
		await setFormValue(page, "effective_from", bf.posting_date);
		await saveForm(page);

		await expect(page).toHaveURL(/\/app\/mys-late-fee-policy\/LFP-/);
	});

	test("Branch Accountant: Fees orange alert when fee structure mismatches override", async ({
		page,
	}) => {
		const bf = seed.bulk_fee!;
		test.skip(
			!bf.sample_student ||
				!bf.default_fee_structure ||
				!bf.fee_structure ||
				!bf.company ||
				!bf.program_enrollment,
			"seed_e2e fee override pair missing",
		);
		// Franchise test user (seed_test_users) — has Education/Fees desk access; e2e_accountant
		// is portal-scoped and cannot open /app/fees.
		await loginAs(page, "accountant@mys.local", "admin");
		await page.goto("/app/fees/new");
		await setFormValue(page, "student", bf.sample_student!);
		await setFormValue(page, "company", bf.company!);
		await setFormValue(page, "program", bf.program);
		await setFormValue(page, "program_enrollment", bf.program_enrollment!);
		await setFormValue(page, "academic_year", bf.academic_year);
		await setFormValue(page, "fee_structure", bf.default_fee_structure!);
		await setFormValue(page, "posting_date", bf.posting_date_2);
		await setFormValue(page, "due_date", bf.due_date_2);
		await saveForm(page);
		// Non-blocking frappe.msgprint(alert=True) — may render as toast or inline message.
		await expect(page.getByText(/does not match the active/i).first()).toBeVisible({
			timeout: 10_000,
		});
	});

	test("Branch Principal is denied on Fee Structure Override", async ({ page }) => {
		await loginAs(page, "principal@mys.local", "admin");
		await page.goto("/app/mys-fee-structure-override");
		await expect(
			page
				.locator("text=/Not permitted|Not allowed|Insufficient Permission|does not have access/i")
				.first(),
		).toBeVisible({ timeout: 15_000 });
	});
});
