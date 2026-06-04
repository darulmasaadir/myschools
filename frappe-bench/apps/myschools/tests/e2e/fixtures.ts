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
	posting_date_2: string;
	due_date_2: string;
	student_count: number;
	run: string;
	fee_structure: string | null;
	default_fee_structure: string | null;
	sample_student: string | null;
	company: string | null;
	program_enrollment: string | null;
	fee_category: string;
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

/**
 * Set a desk form field via the form's own API (cur_frm.set_value), which runs
 * the same validate / fetch_from / depends_on logic as UI entry but without
 * fighting Frappe's awesomplete/datepicker widgets (those are upstream, not our
 * code). Format-agnostic for dates (pass ISO yyyy-mm-dd).
 */
export async function setFormValue(page: Page, fieldname: string, value: string) {
	await page.waitForFunction(() => Boolean((window as any).cur_frm?.doc), undefined, {
		timeout: 15_000,
	});
	await page.evaluate(
		({ fn, val }) => (window as any).cur_frm.set_value(fn, val),
		{ fn: fieldname, val: value },
	);
}

/**
 * Save the current desk form via the Save keyboard shortcut and wait until the
 * doc is persisted (no longer new, not dirty). Surfaces any blocking msgprint
 * dialog as a readable failure instead of a bare timeout.
 */
export async function saveForm(page: Page) {
	await page.keyboard.press("Control+s");
	try {
		await page.waitForFunction(
			() => {
				const f = (window as any).cur_frm;
				return Boolean(f && !f.is_new() && !f.is_dirty());
			},
			undefined,
			{ timeout: 20_000 },
		);
	} catch (e) {
		const dialog = await page
			.locator(".modal.show .modal-body, .msgprint")
			.first()
			.innerText()
			.catch(() => "");
		throw new Error(`saveForm: doc not persisted. Dialog: ${dialog || "(none)"}`);
	}
}

export { base as test, expect };
