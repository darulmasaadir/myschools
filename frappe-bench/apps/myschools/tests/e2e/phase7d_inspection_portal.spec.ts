/**
 * Phase 7d — Inspection portal + admission enquiry (browser regression).
 *
 * Codifies the manual PR #15 matrix: monitor happy path, fail→finding,
 * audit access, branch director denial, guest admission validation.
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect, Page } from "@playwright/test";
import { loadSeed, loginAs, loginPortal } from "./fixtures";

const seed = loadSeed();
const monitor = "e2e_monitor@mys.local";
const audit = "e2e_audit@mys.local";
const director = "e2e_director@mys.local";

function monitorPassword() {
	return seed.users[monitor].password;
}

async function acceptConfirm(page: Page) {
	page.once("dialog", (d) => d.accept());
}

test.describe("Phase 7d — Inspection portal", () => {
	test.skip(!seed.branch || !seed.checklist_template, "run seed_e2e.main first");

	test("Academic Monitor dashboard and new visit form load", async ({ page }) => {
		await loginPortal(page, monitor, monitorPassword());
		await expect(page.locator("h1")).toContainText("Inspection Dashboard");
		await page.goto("/inspection/visits/new");
		await expect(page.locator("#new-visit-form")).toBeVisible();
		expect(await page.locator("#branch option").count()).toBeGreaterThanOrEqual(2);
	});

	test("Monitor happy path: create → template → pass all → submit", async ({ page }) => {
		await loginPortal(page, monitor, monitorPassword(), "/inspection/visits/new");
		await page.selectOption("#branch", seed.branch!);
		await page.selectOption("#visit_type", "Routine");
		await page.locator("#create-visit-btn").click();
		await page.waitForURL(/\/inspection\/visit\?name=/, { timeout: 20_000 });
		await expect(page.locator(".mys-portal__tag:has-text('Draft')")).toBeVisible();

		await page.selectOption("#template-select", seed.checklist_template!);
		await page.locator("#apply-template-form button[type='submit']").click();
		await page.waitForURL(/saved=1|name=/, { timeout: 20_000 });
		await expect(page.locator(".mys-portal__check-item")).toHaveCount(2);

		for (const sel of await page.locator(".check-result").all()) {
			await sel.selectOption("Pass");
		}
		await acceptConfirm(page);
		await page.locator("#submit-visit").click();
		await page.waitForURL(/submitted=1/, { timeout: 20_000 });
		await expect(page.locator(".mys-portal__tag:has-text('Submitted')")).toBeVisible();
	});

	test("Monitor fail Critical creates open finding on submit", async ({ page }) => {
		await loginPortal(page, monitor, monitorPassword());
		const beforeText = await page.locator(".mys-portal__summary").textContent();
		const beforeMatch = beforeText?.match(/(\d+)\s+open findings/);
		const beforeCount = beforeMatch ? parseInt(beforeMatch[1], 10) : 0;

		await page.goto("/inspection/visits/new");
		await page.selectOption("#branch", seed.branch!);
		await page.selectOption("#visit_type", "Routine");
		await page.locator("#create-visit-btn").click();
		await page.waitForURL(/\/inspection\/visit\?name=/, { timeout: 20_000 });

		await page.selectOption("#template-select", seed.checklist_template!);
		await page.locator("#apply-template-form button[type='submit']").click();
		await page.waitForLoadState("networkidle");

		const results = page.locator(".check-result");
		await results.nth(0).selectOption("Fail");
		await results.nth(1).selectOption("Pass");
		await acceptConfirm(page);
		await page.locator("#submit-visit").click();
		await page.waitForURL(/submitted=1/, { timeout: 20_000 });

		await page.goto("/inspection");
		const afterText = await page.locator(".mys-portal__summary").textContent();
		const afterMatch = afterText?.match(/(\d+)\s+open findings/);
		const afterCount = afterMatch ? parseInt(afterMatch[1], 10) : 0;
		expect(afterCount).toBeGreaterThan(beforeCount);
	});

	test("Audit Officer can open inspection visits list", async ({ page }) => {
		await loginPortal(page, audit, seed.users[audit].password, "/inspection/visits");
		await expect(page.locator("h1")).toContainText(/visits/i);
		await expect(page.locator(".mys-portal__nav")).toBeVisible();
	});

	test("Branch Director is denied on /inspection", async ({ page }) => {
		await loginAs(page, director, seed.users[director].password);
		await page.goto("/inspection");
		await expect(
			page.getByText(/do not have access|Not Permitted|Not allowed/i).first(),
		).toBeVisible({ timeout: 15_000 });
	});
});

test.describe("Phase 7d — Admission enquiry (guest)", () => {
	test("requires parent name and phone in the UI", async ({ page }) => {
		await page.goto("/admission-enquiry");
		await page.locator("#submit-btn").click();
		await expect(page.locator("#form-error")).toBeVisible();
		await expect(page.locator("#form-error")).toContainText(/parent name and phone/i);
	});

	test("guest submission succeeds", async ({ page }) => {
		await page.goto("/admission-enquiry");
		await page.fill("#parent_name", "E2E Parent");
		await page.fill("#phone", "03009998877");
		await page.fill("#message", "Playwright admission smoke");
		await page.locator("#submit-btn").click();
		await expect(page.locator("#form-success")).toBeVisible({ timeout: 15_000 });
		await expect(page.locator("#ref")).toContainText(/COMM-/);
	});
});
