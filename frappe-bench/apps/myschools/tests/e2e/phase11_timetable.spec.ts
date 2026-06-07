/**
 * Phase 11 — Branch + guardian + teacher timetable (browser regression).
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect } from "@playwright/test";
import { loadSeed, loginPortal } from "./fixtures";

const seed = loadSeed();
const teacher = "e2e_teacher@mys.local";
const director = "e2e_director@mys.local";

test.describe("Phase 11 — Timetable portals", () => {
	test.skip(!seed.teacher?.student_group, "run seed_e2e.main first (teacher seed)");
	test.skip(!seed.guardian?.user, "run seed_e2e.main first (guardian seed)");

	test("Branch director sees branch timetable with seeded class", async ({ page }) => {
		test.skip(!seed.users[director], "run seed_e2e.main first");
		await loginPortal(page, director, seed.users[director].password, "/branch/timetable");
		await expect(page.locator("h1")).toContainText("Branch Timetable");
		await expect(page.locator(".mys-portal")).toContainText(seed.teacher!.student_group);
	});

	test("Guardian sees child class timetable", async ({ page }) => {
		const guardian = seed.guardian!.user;
		await loginPortal(page, guardian, seed.users[guardian].password, "/guardian/timetable");
		await expect(page.locator("h1")).toContainText("Class Timetable");
		await expect(page.locator(".mys-portal")).toContainText(seed.teacher!.student_group);
	});

	test("Teacher schedule is grouped by day", async ({ page }) => {
		await loginPortal(page, teacher, seed.users[teacher]?.password ?? "mys-e2e-teacher", "/teacher/schedule");
		await expect(page.locator("h1")).toContainText("My Schedule");
		await expect(page.locator(".mys-portal__card h2").first()).toBeVisible();
		await expect(page.locator(".mys-portal__table tbody tr").first()).toBeVisible();
	});
});
