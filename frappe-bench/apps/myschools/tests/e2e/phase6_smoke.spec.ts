/**
 * Phase 6 verification smoke — exercises the Setup Wizard slide asset, the
 * Module Onboarding card, the 4 Query Reports, and confirms the brand
 * assets serve. Run as Administrator (admin/admin).
 *
 * Run via:
 *   cd frappe-bench/apps/myschools
 *   npx playwright test /tmp/phase6_smoke.spec.ts --project=chromium
 */
import { test, expect, Page } from "@playwright/test";

async function login(page: Page) {
	await page.goto("/login");
	await page.fill('input[name="login_email"], input#login_email', "Administrator");
	await page.fill('input[name="login_password"], input#login_password', "admin");
	await page.locator('button.btn-login, button:has-text("Login")').first().click();
	await page.waitForURL(/\/app(\/|$)/, { timeout: 20_000 });
	await expect(page.locator(".navbar, .standard-sidebar").first()).toBeVisible({
		timeout: 15_000,
	});
}

test.describe("Phase 6 — Brand + Setup Wizard asset", () => {
	test("brand logo asset is served", async ({ request }) => {
		const res = await request.get("/assets/myschools/images/mys-logo.svg");
		expect(res.status()).toBe(200);
		expect(res.headers()["content-type"]).toMatch(/svg|image/);
	});

	test("setup_wizard.js bundle is served", async ({ request }) => {
		const res = await request.get("/assets/myschools/js/setup_wizard.js");
		expect(res.status()).toBe(200);
		const body = await res.text();
		expect(body).toContain("mys_franchise");
		expect(body).toContain("frappe.setup.add_slide");
	});
});

test.describe("Phase 6 — Module Onboarding card", () => {
	test("MYS Franchise Setup card renders", async ({ page }) => {
		await login(page);
		await page.goto("/app/module-onboarding/MYS Franchise Setup");
		// The form page renders the doc once it loads.
		await expect(page.locator(".page-title, .title-text").first()).toBeVisible({
			timeout: 20_000,
		});
		const text = await page.textContent("body");
		expect(text).toContain("MYS Franchise Setup");
	});
});

test.describe("Phase 6 — Query Reports render", () => {
	const reports = [
		"MYS Royalty Aging",
		"MYS Fee Collection by Branch",
		"MYS Findings by Branch and Severity",
		"MYS Branch Health Scorecard",
	];

	for (const name of reports) {
		test(`${name} loads without console error`, async ({ page }) => {
			const consoleErrors: string[] = [];
			page.on("console", (msg) => {
				if (msg.type() === "error") consoleErrors.push(msg.text());
			});
			await login(page);
			await page.goto(`/app/query-report/${encodeURI(name)}`);
			// The query-report shell mounts the title once the script is ready.
			// The data area (.report-wrapper) can stay hidden when the report
			// has zero rows, so assert on the title instead.
			await expect(page.locator(`.title-text:has-text("${name}")`).first()).toBeVisible({
				timeout: 25_000,
			});
			// Give the script-report shell a beat to finish wiring.
			await page.waitForTimeout(1000);
			// Filter out the harmless ones Frappe emits on every page.
			const real = consoleErrors.filter(
				(e) =>
					!e.includes("favicon") &&
					!e.includes("AbortError") &&
					!e.includes("Failed to load resource"),
			);
			expect(real, `console errors on ${name}: ${real.join(" | ")}`).toEqual([]);
		});
	}
});

test.describe("Phase 6 — Workspaces still render", () => {
	const workspaces = [
		"mys-head-office",
		"mys-cluster",
		"mys-branch",
		"mys-campus",
		"mys-inspection",
	];

	for (const ws of workspaces) {
		test(`/app/${ws} loads`, async ({ page }) => {
			await login(page);
			await page.goto(`/app/${ws}`);
			await expect(page.locator(".layout-main-section, .workspace").first()).toBeVisible({
				timeout: 20_000,
			});
		});
	}
});
