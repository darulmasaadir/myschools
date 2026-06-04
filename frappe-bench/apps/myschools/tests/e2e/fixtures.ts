import { test as base, expect, Page } from "@playwright/test";
import * as fs from "fs";

const STATE_FILE = process.env.MYS_STATE_FILE ?? "/tmp/mys_e2e_state.json";

export interface BulkFeeSeed {
	branch: string;
	student_group: string;
	program: string;
	academic_year: string;
	academic_term: string;
	posting_date: string;
	due_date: string;
	student_count: number;
	run: string;
}

export interface SeedState {
	users: Record<string, { password: string; roles: string[] }>;
	visit: string | null;
	finding: string | null;
	invoice: string | null;
	branch: string | null;
	checklist_template: string | null;
	bulk_fee: BulkFeeSeed | null;
}

export function loadSeed(): SeedState {
	if (!fs.existsSync(STATE_FILE)) {
		throw new Error(
			`E2E seed not found at ${STATE_FILE}. ` +
				`Run: bench --site <site> execute myschools.scripts.seed_e2e.main`,
		);
	}
	return JSON.parse(fs.readFileSync(STATE_FILE, "utf-8"));
}

/**
 * Frappe's login form posts to /api/method/login. We submit the form rather
 * than calling the API directly so the session cookie is set the same way
 * a real user's would be.
 */
export async function loginAs(page: Page, email: string, password: string) {
	await page.goto("/login");
	await page.fill('input[name="login_email"], input#login_email', email);
	await page.fill('input[name="login_password"], input#login_password', password);
	await page.locator('button.btn-login, button:has-text("Login")').first().click();
	// Frappe redirects to /app on success. Wait for the desk shell to render.
	await page.waitForURL(/\/app(\/|$)/, { timeout: 20_000 });
	// The sidebar / top navbar is the unambiguous signal we're in.
	await expect(page.locator(".navbar, .standard-sidebar, .layout-side-section").first()).toBeVisible({
		timeout: 15_000,
	});
}

/** Website portal login (inspection / admission). */
export async function loginPortal(
	page: Page,
	email: string,
	password: string,
	redirect = "/inspection",
) {
	await page.goto(`/login?redirect-to=${encodeURIComponent(redirect)}`);
	await page.fill('input[name="login_email"], input#login_email', email);
	await page.fill('input[name="login_password"], input#login_password', password);
	await page.locator('button.btn-login, button:has-text("Login")').first().click();
	await page.waitForURL((url) => url.pathname.startsWith(redirect.split("?")[0]), {
		timeout: 20_000,
	});
	await expect(page.locator(".mys-portal").first()).toBeVisible({ timeout: 15_000 });
}

/** Set a Frappe desk Link field (v15 combobox + listbox options). */
export async function setDeskLinkField(page: Page, fieldname: string, value: string) {
	const control = page.locator(`.frappe-control[data-fieldname="${fieldname}"]`);
	await control.scrollIntoViewIfNeeded();
	const input = control.locator('input, [role="combobox"]').first();
	await input.click();
	await input.fill(value);
	const option = page.getByRole("option", { name: value, exact: true });
	try {
		await option.click({ timeout: 3_000 });
	} catch {
		// Single-result link fields: keyboard select is more stable than portaled listboxes.
		await input.press("ArrowDown");
		await input.press("Enter");
	}
}

/** Set a Frappe desk Date field (YYYY-MM-DD). */
export async function setDeskDateField(page: Page, fieldname: string, isoDate: string) {
	const control = page.locator(`.frappe-control[data-fieldname="${fieldname}"]`);
	await control.scrollIntoViewIfNeeded();
	const input = control.locator("input").first();
	await input.click();
	await input.fill(isoDate);
	await input.press("Tab");
}

export async function saveDeskForm(page: Page) {
	await page.locator('.btn-primary[data-label="Save"], button:has-text("Save")').first().click();
	await page.waitForURL(/\/app\/mys-bulk-fee-run\/BFR-/, { timeout: 30_000 });
	await expect(page.locator(".indicator-pill, .indicator").first()).toBeVisible({
		timeout: 15_000,
	});
}

export { base as test, expect };
