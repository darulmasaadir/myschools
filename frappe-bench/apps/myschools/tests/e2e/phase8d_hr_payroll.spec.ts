/**
 * Phase 8d — HR / payroll desk surfaces (browser regression).
 *
 * Proves branch-scoped Employee visibility for a Branch Director (live
 * frappe.client.get_list in a real desk session — same leak discipline as
 * scripts/verify_hr_surfaces.py) and that hrms Payroll Entry exposes the
 * franchise `mys_branch` field on the desk form.
 *
 * Company alignment on Payroll Entry is covered by test_identity.py (server
 * validate hook); this spec walks what a user actually sees in the browser.
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect, Page } from "@playwright/test";
import { loadSeed, loginAs } from "./fixtures";

const seed = loadSeed();
const director = "e2e_director@mys.local";

function directorPassword() {
	return seed.users[director].password;
}

function branchName(): string {
	return seed.bulk_fee?.branch ?? seed.branch ?? "BR014";
}

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

test.describe("Phase 8d — HR / payroll", () => {
	test.skip(!seed.bulk_fee?.branch && !seed.branch, "run seed_e2e.main first (branch)");

	test("Branch Director Employee list is branch-scoped (no cross-branch leak)", async ({
		page,
	}) => {
		const branch = branchName();
		await loginAs(page, director, directorPassword());
		// Land on the desk Employee list so frappe bootstraps in the page context.
		await page.goto("/app/employee");
		await page.waitForFunction(() => Boolean((window as any).frappe?.session?.user), undefined, {
			timeout: 15_000,
		});

		const leaked = await page.evaluate(async (expectedBranch) => {
			const r = await (window as any).frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "Employee",
					fields: ["name", "mys_branch"],
					limit_page_length: 0,
				},
			});
			const rows: { name: string; mys_branch: string | null }[] = r.message ?? [];
			return rows
				.filter((row) => row.mys_branch && row.mys_branch !== expectedBranch)
				.map((row) => row.name);
		}, branch);

		expect(leaked, `cross-branch employees visible to director: ${leaked.join(", ")}`).toEqual(
			[],
		);
	});

	test("Administrator opens Payroll Entry and sets MYS Branch", async ({ page }) => {
		const branch = branchName();
		await loginAdmin(page);
		await page.goto("/app/payroll-entry/new");
		await page.waitForFunction(() => Boolean((window as any).cur_frm?.doc), undefined, {
			timeout: 15_000,
		});
		await expect(page.locator('[data-fieldname="mys_branch"]').first()).toBeVisible({
			timeout: 10_000,
		});
		await page.evaluate(
			({ fn, val }) => (window as any).cur_frm.set_value(fn, val),
			{ fn: "mys_branch", val: branch },
		);
		const onForm = await page.evaluate(() => (window as any).cur_frm.doc.mys_branch);
		expect(onForm).toBe(branch);
	});
});
