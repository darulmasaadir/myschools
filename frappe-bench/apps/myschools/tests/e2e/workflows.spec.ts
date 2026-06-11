/**
 * Phase-5 workflow e2e — exercises the role gating and form actions that
 * unit tests cannot prove: that the Frappe desk *renders* the right
 * workflow menu and the right primary-action buttons for each role.
 *
 * Pre-req: run `bench --site <site> execute myschools.scripts.seed_e2e.main`
 * once before invoking this spec — it ensures the test users + a
 * Resolved finding + an overdue invoice exist.
 */
import { test, expect, Page } from "@playwright/test";
import { loadSeed, loginAs } from "./fixtures";

const seed = loadSeed();

/**
 * Frappe v15 groups workflow actions under the "Actions" split-button when
 * there is more than one transition out of the current state. With a single
 * transition, the action surfaces as a primary button instead. The helper
 * opens whichever surface exists, so the assertion downstream can just look
 * for the label text. Returns true if the menu was opened, false if no
 * Actions button is present (i.e. user has zero transitions).
 */
async function openWorkflowActions(page: Page): Promise<boolean> {
	// Wait for the form to render its workflow state pill — the marker that
	// the form-controller's `make_workflow_button` pass has finished.
	await expect(page.locator(".indicator-pill, .indicator").first()).toBeVisible({
		timeout: 15_000,
	});
	// The split-button label is literally "Actions" in the page-actions area.
	const actionsBtn = page
		.locator(".page-actions button.btn-primary:has-text('Actions'), .page-actions button:has-text('Actions')")
		.first();
	if (await actionsBtn.isVisible().catch(() => false)) {
		await actionsBtn.click();
		// Give the dropdown a beat to mount its children.
		await page.waitForTimeout(300);
		return true;
	}
	return false;
}

test.describe("Phase 5 — Workflows in the desk", () => {
	test.skip(!seed.finding, "no Resolved finding seeded — run seed_e2e.main");

	test("Audit Officer sees Verify on a Resolved finding", async ({ page }) => {
		test.setTimeout(90_000);
		await loginAs(page, "e2e_audit@mys.local", seed.users["e2e_audit@mys.local"].password);
		await page.goto(`/app/mys-inspection-finding/${seed.finding}`);
		await openWorkflowActions(page);
		// "Verify" surfaces either as a primary button or as a dropdown item.
		// Either way it lives in an .actions-btn-group / dropdown / page-actions.
		await expect(
			page
				.locator(
					".page-actions a:has-text('Verify'), .page-actions button:has-text('Verify'), .dropdown-menu.show a:has-text('Verify')",
				)
				.first(),
		).toBeVisible({ timeout: 10_000 });
	});

	test("Branch Director does NOT see Verify on the same finding", async ({ page }) => {
		await loginAs(page, "e2e_director@mys.local", seed.users["e2e_director@mys.local"].password);
		await page.goto(`/app/mys-inspection-finding/${seed.finding}`);
		// Wait for the workflow pill so the form is fully bootstrapped before
		// we measure absence.
		await expect(page.locator(".indicator-pill, .indicator").first()).toBeVisible({
			timeout: 15_000,
		});
		// Open the Actions menu if it exists, so any dropdown items get mounted.
		await openWorkflowActions(page);
		await page.waitForTimeout(500);
		// "Verify" must not be present in any actionable surface.
		const verifyCount = await page
			.locator(
				".page-actions a:has-text('Verify'), .page-actions button:has-text('Verify'), .dropdown-menu.show a:has-text('Verify')",
			)
			.count();
		expect(verifyCount).toBe(0);
	});
});

test.describe("Phase 5 — Finding form custom action", () => {
	test.skip(!seed.finding, "no finding seeded");

	test('"Create Corrective Action" is hidden on Resolved finding', async ({ page }) => {
		await loginAs(page, "Administrator", "admin");
		await page.goto(`/app/mys-inspection-finding/${seed.finding}`);
		await expect(page.locator(".indicator-pill, .indicator").first()).toBeVisible({
			timeout: 15_000,
		});
		// The form-JS gates "Create Corrective Action" to status in (Open, In Progress).
		// On Resolved the custom button is skipped — assert it's absent everywhere.
		await openWorkflowActions(page);
		await page.waitForTimeout(500);
		const createCABtn = await page
			.locator(
				"button:has-text('Create Corrective Action'), a:has-text('Create Corrective Action')",
			)
			.count();
		expect(createCABtn).toBe(0);
	});
});

test.describe("Phase 5 — Royalty Invoice Send Reminder", () => {
	test.skip(!seed.invoice, "no overdue invoice seeded");

	test('"Send Reminder" surfaces on overdue Royalty Invoice', async ({ page }) => {
		test.setTimeout(90_000);
		await loginAs(page, "Administrator", "admin");
		await page.goto(`/app/mys-royalty-invoice/${seed.invoice}`);
		await expect(page.locator(".indicator-pill, .indicator").first()).toBeVisible({
			timeout: 15_000,
		});
		// Custom form buttons are grouped under an "Actions" split-button. Click it
		// so the menu mounts its items, then assert "Send Reminder" is present.
		const actionsBtn = page.locator("button:has-text('Actions')").first();
		await expect(actionsBtn).toBeVisible({ timeout: 10_000 });
		await actionsBtn.click();
		await page.waitForTimeout(300);
		await expect(
			page
				.locator(".dropdown-menu.show a:has-text('Send Reminder'), a:has-text('Send Reminder')")
				.first(),
		).toBeVisible({ timeout: 10_000 });
	});
});

test.describe("Phase 5 — List view polish", () => {
	test("Finding list view loads and renders status indicators", async ({ page }) => {
		test.setTimeout(90_000);
		await loginAs(page, "Administrator", "admin");
		await page.goto("/app/mys-inspection-finding");
		// The list container always mounts; wait for it.
		await expect(page.locator(".frappe-list, .layout-main-section .result").first()).toBeVisible({
			timeout: 45_000,
		});
		// Status pills render inline on each row — at least one should be there
		// because the seed created a Resolved finding.
		await expect(page.locator(".indicator-pill, .indicator").first()).toBeVisible({
			timeout: 15_000,
		});
	});

	test("Royalty Invoice list view loads", async ({ page }) => {
		test.setTimeout(90_000);
		await loginAs(page, "Administrator", "admin");
		await page.goto("/app/mys-royalty-invoice");
		await expect(page.locator(".frappe-list, .layout-main-section .result").first()).toBeVisible({
			timeout: 45_000,
		});
	});
});
