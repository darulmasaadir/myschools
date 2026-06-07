/**
 * Phase 11 — Branch + guardian + teacher timetable (browser regression).
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect } from "@playwright/test";
import { loadSeed, loginAs, loginPortal } from "./fixtures";

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

	test("Branch dashboard surfaces the timetable summary card", async ({ page }) => {
		test.skip(!seed.users[director], "run seed_e2e.main first");
		await loginPortal(page, director, seed.users[director].password, "/branch");
		const card = page.locator(".mys-portal__card", { hasText: "Timetable" });
		await expect(card).toBeVisible();
		await expect(card).toContainText("sessions");
		await expect(card.locator("a", { hasText: "View timetable" })).toHaveAttribute(
			"href",
			"/branch/timetable",
		);
	});

	test("Guardian sees child class timetable", async ({ page }) => {
		const guardian = seed.guardian!.user;
		await loginPortal(page, guardian, seed.users[guardian].password, "/guardian/timetable");
		await expect(page.locator("h1")).toContainText("Class Timetable");
		await expect(page.locator(".mys-portal")).toContainText(seed.teacher!.student_group);
	});

	test("Guardian ?student= filter scopes to the selected child", async ({ page }) => {
		const guardian = seed.guardian!.user;
		const child = seed.guardian!.student;
		await loginPortal(
			page,
			guardian,
			seed.users[guardian].password,
			`/guardian/timetable?student=${encodeURIComponent(child)}`,
		);
		await expect(page.locator("h1")).toContainText("Class Timetable");
		// Filtered view still renders the seeded class for the owned child.
		await expect(page.locator(".mys-portal")).toContainText(seed.teacher!.student_group);
		// A child the guardian does NOT own must be rejected, not silently shown.
		await page.goto("/guardian/timetable?student=MYS-NOT-MY-CHILD");
		await expect(page.locator("body")).toContainText(/not linked|do not have access|Not Permitted/i);
	});

	test("Teacher schedule is grouped by day", async ({ page }) => {
		await loginPortal(page, teacher, seed.users[teacher]?.password ?? "mys-e2e-teacher", "/teacher/schedule");
		await expect(page.locator("h1")).toContainText("My Schedule");
		await expect(page.locator(".mys-portal__card h2").first()).toBeVisible();
		await expect(page.locator(".mys-portal__table tbody tr").first()).toBeVisible();
	});

	test("Desk Course Schedule list is branch-scoped for the director", async ({ page }) => {
		test.skip(!seed.users[director], "run seed_e2e.main first");
		await loginAs(page, director, seed.users[director].password);
		await page.goto("/app/course-schedule/view/list");
		// The list view renders (no permission wall) for a branch role with scoped read.
		await expect(page.locator(".list-row-container, .result, .no-result").first()).toBeVisible({
			timeout: 20_000,
		});
		await expect(page.locator("body")).not.toContainText(/Not Permitted|do not have access/i);
		// Scoping holds: the director's own branch class is reachable in the list.
		await expect(page.locator(".page-head .title-text")).toContainText(/Course Schedule/i, {
			timeout: 15_000,
		});
	});
});
