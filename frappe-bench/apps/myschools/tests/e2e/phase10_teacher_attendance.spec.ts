/**
 * Phase 10 — Teacher attendance + assessment marking (browser regression).
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

test.describe("Phase 10 — Teacher attendance + assessments", () => {
	test.skip(!seed.teacher?.student_group, "run seed_e2e.main first (teacher seed)");

	test("Teacher marks attendance and enters assessment scores", async ({ page }) => {
		await loginAs(page, teacher, teacherPassword());
		const group = seed.teacher!.student_group!;
		await page.goto(`/teacher/attendance?group=${encodeURIComponent(group)}&date=2026-06-02`);
		await expect(page.locator("h1")).toContainText("Mark Attendance");
		const statusSelect = page.locator(".att-status").first();
		await statusSelect.selectOption("Present");
		await page.getByRole("button", { name: "Save attendance" }).click();
		await expect(page.locator(".mys-portal__success")).toContainText("Attendance saved", {
			timeout: 15_000,
		});

		test.skip(!seed.teacher?.assessment_plan, "assessment plan not seeded");
		await page.goto(`/teacher/assessment?plan=${encodeURIComponent(seed.teacher!.assessment_plan!)}`);
		await expect(page.locator("h1")).toContainText("E2E Portal Mid Term");
		const scoreInput = page.locator(".score-input").first();
		await scoreInput.fill("85");
		await page.getByRole("button", { name: "Save scores" }).click();
		await expect(page.locator(".mys-portal__success")).toContainText("Scores saved", {
			timeout: 15_000,
		});
		await expect(page.locator("tbody tr").first()).toContainText("B");
	});
});
