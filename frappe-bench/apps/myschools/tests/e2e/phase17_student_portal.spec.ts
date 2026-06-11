/**
 * Phase 17c — Student portal.
 *
 * Surfaces the phase added (spec-completeness audit):
 *  - /student landing (profile)
 *  - /student/fees
 *  - /student/attendance
 *  - /student/timetable
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect } from "@playwright/test";
import { loadSeed, loginPortal } from "./fixtures";

const seed = loadSeed();
const student = "e2e-student@mys.local";

test.describe("Phase 17 — Student portal", () => {
  test.skip(!seed.student_portal?.user, "run seed_e2e.main first (student portal seed)");

  const studentPassword = () =>
    seed.users[student]?.password ?? "mys-e2e-student";

  test("Student lands on profile page", async ({ page }) => {
    await loginPortal(page, student, studentPassword(), "/student");
    await expect(page.locator("h1")).toContainText("My Profile");
    await expect(page.getByRole("link", { name: "Fees" })).toBeVisible();
  });

  test("Student fees page renders", async ({ page }) => {
    await loginPortal(page, student, studentPassword(), "/student/fees");
    await expect(page.locator("h1")).toContainText("Fees");
  });

  test("Student attendance page renders", async ({ page }) => {
    await loginPortal(page, student, studentPassword(), "/student/attendance");
    await expect(page.locator("h1")).toContainText("Attendance");
  });

  test("Student timetable page renders", async ({ page }) => {
    await loginPortal(page, student, studentPassword(), "/student/timetable");
    await expect(page.locator("h1")).toContainText("Class Timetable");
  });
});
