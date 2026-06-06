/**
 * Phase 9 — Teacher portal (browser regression).
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect } from "@playwright/test";
import { loadSeed, loginAs } from "./fixtures";

const seed = loadSeed();
const teacher = "e2e_teacher@mys.local";

function teacherPassword() {
	return seed.users[teacher]?.password ?? "mys-e2e-teacher";
}

test.describe("Phase 9 — Teacher portal", () => {
	test.skip(!seed.teacher?.student_group, "run seed_e2e.main first (teacher seed)");

	test("Teacher dashboard, classes, roster, and schedule load", async ({ page }) => {
		await loginAs(page, teacher, teacherPassword());
		await page.goto("/teacher");
		await expect(page.locator("h1")).toContainText("Teacher Dashboard");
		await expect(page.locator(".mys-portal")).toContainText("My classes");

		await page.goto("/teacher/classes");
		await expect(page.locator("h1")).toContainText("My Classes");
		await expect(page.locator(".mys-portal__table")).toContainText(seed.teacher!.student_group);

		await page.goto(`/teacher/class?group=${encodeURIComponent(seed.teacher!.student_group)}`);
		await expect(page.locator("h1")).toContainText("E2E Teacher Class");
		await expect(page.locator(".mys-portal__table tbody tr").first()).toBeVisible();

		await page.goto("/teacher/schedule");
		await expect(page.locator("h1")).toContainText("My Schedule");
	});

	test("Branch Director cannot access teacher portal", async ({ page }) => {
		const director = "e2e_director@mys.local";
		test.skip(!seed.users[director], "run seed_e2e.main first");
		await loginAs(page, director, seed.users[director].password);
		await page.goto("/teacher");
		await expect(page.locator("body")).toContainText(/do not have access|Not Permitted|403/i);
	});
});
