/**
 * Phase 8b — student transfer + leaving desk forms (browser regression).
 *
 * Proves submittable lifecycle forms save/submit for Branch Director and that
 * Academic Monitor is denied — the role × surface matrix in
 * scripts/verify_student_lifecycle_surfaces.py, walked in a real browser.
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect } from "@playwright/test";
import { loadSeed, loginAs, setFormValue, saveForm, submitForm } from "./fixtures";

const seed = loadSeed();
const director = "e2e_director@mys.local";
const monitor = "e2e_monitor@mys.local";

function directorPassword() {
	return seed.users[director].password;
}

function monitorPassword() {
	return seed.users[monitor].password;
}

test.describe("Phase 8b — Student lifecycle", () => {
	test.skip(
		!seed.student_lifecycle?.transfer_student,
		"run seed_e2e.main first (student_lifecycle)",
	);

	test("Branch Director submits campus transfer", async ({ page }) => {
		const sl = seed.student_lifecycle!;
		await loginAs(page, director, directorPassword());
		await page.goto("/app/mys-student-transfer/new");
		await setFormValue(page, "student", sl.transfer_student);
		await page.waitForFunction(
			() => Boolean((window as any).cur_frm?.doc?.from_branch),
			undefined,
			{ timeout: 10_000 },
		);
		await setFormValue(page, "to_branch", sl.branch);
		await setFormValue(page, "to_campus", sl.campus_junior);
		await setFormValue(page, "transfer_date", sl.transfer_date);
		await setFormValue(page, "reason", "E2E campus promotion");
		await saveForm(page);
		await submitForm(page);

		await expect(page).toHaveURL(/\/app\/mys-student-transfer\/STR-TF-/);
		await expect(page.locator(".indicator-pill, .indicator").first()).toContainText(/Submitted/i);
	});

	test("Branch Director submits student leaving + leaving certificate print", async ({ page }) => {
		const sl = seed.student_lifecycle!;
		await loginAs(page, director, directorPassword());
		await page.goto("/app/mys-student-leaving/new");
		await setFormValue(page, "student", sl.leaving_student);
		await page.waitForFunction(
			() => Boolean((window as any).cur_frm?.doc?.branch),
			undefined,
			{ timeout: 10_000 },
		);
		await setFormValue(page, "leaving_date", sl.leaving_date);
		await setFormValue(page, "reason_for_leaving", "E2E graduation");
		await saveForm(page);
		await submitForm(page);

		await expect(page).toHaveURL(/\/app\/mys-student-leaving\/STR-LV-/);
		const match = page.url().match(/STR-LV-[^/?#]+/);
		expect(match, "submitted leaving doc name").toBeTruthy();
		const leavingName = match![0];

		await page.goto(
			`/printview?doctype=MYS+Student+Leaving&name=${encodeURIComponent(leavingName)}&format=MYS+Leaving+Certificate`,
		);
		await expect(page.getByText(/SCHOOL LEAVING CERTIFICATE/i).first()).toBeVisible({
			timeout: 15_000,
		});
		await expect(page.getByText(/E2E graduation/i).first()).toBeVisible({ timeout: 10_000 });
	});

	test("Academic Monitor is denied on Student Transfer list", async ({ page }) => {
		await loginAs(page, monitor, monitorPassword());
		await page.goto("/app/mys-student-transfer");
		await expect(
			page
				.locator("text=/Not permitted|Not allowed|Insufficient Permission|does not have access/i")
				.first(),
		).toBeVisible({ timeout: 15_000 });
	});
});
