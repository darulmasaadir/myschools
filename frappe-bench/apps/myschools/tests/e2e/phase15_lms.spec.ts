/**
 * Phase 15 — LMS integration (browser regression).
 *
 * Surfaces the phase added (spec-completeness audit):
 *  - Desk list for LMS Course (branch role can open, seeded row visible)
 *  - Upstream /lms SPA loads for teacher and shows seeded course card
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect } from "@playwright/test";
import { loadSeed, loginAs } from "./fixtures";

const seed = loadSeed();
const director = "e2e_director@mys.local";

test.describe("Phase 15 — LMS", () => {
  test.skip(!seed.users[director], "run seed_e2e.main first");
  test.skip(!seed.branch, "run seed_e2e.main first (branch seed)");

  test("Branch director can open LMS Course desk list", async ({ page }) => {
    await loginAs(page, director, seed.users[director].password);
    await page.goto("/app/lms-course/view/list");
    await expect(
      page.locator(".list-row-container, .result, .no-result").first(),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page.locator("body")).not.toContainText(
      /Not Permitted|do not have access/i,
    );
    await expect(page.locator(".page-head .title-text")).toContainText(
      /Course/i,
      { timeout: 15_000 },
    );
    if (seed.lms_course?.course) {
      await expect(page.locator(".list-row-container")).toContainText(
        "E2E Portal Math LMS",
      );
    }
  });

  test("Teacher sees seeded course on upstream /lms SPA", async ({ page }) => {
    test.skip(!seed.teacher?.user, "run seed_e2e.main first (teacher seed)");
    const teacher = seed.teacher!.user;
    await loginAs(page, teacher, seed.users[teacher].password);
    const response = await page.goto("/lms");
    expect(response?.status()).toBeLessThan(400);
    await expect(page.locator("body")).not.toContainText(
      /Not Permitted|does not exist/i,
    );
    await expect(page.locator("body")).toContainText("Learning", {
      timeout: 15_000,
    });
    if (seed.lms_course?.course) {
      await expect(page.locator("body")).toContainText(
        "E2E Portal Math LMS",
        { timeout: 15_000 },
      );
    }
  });
});
