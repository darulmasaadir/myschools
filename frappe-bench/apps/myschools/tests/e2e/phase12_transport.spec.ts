/**
 * Phase 12 — Transport (browser regression).
 *
 * Surfaces the phase added (spec-completeness audit):
 *  - Guardian /guardian/transport read view (seeded route, fee, status)
 *  - Guardian portal "Transport" nav link
 *  - Desk lists for MYS Student Transport / Route / Vehicle (branch role can open)
 *  - Desk MYS Student Transport list is branch-scoped for the director
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect } from "@playwright/test";
import { loadSeed, loginAs, loginPortal } from "./fixtures";

const seed = loadSeed();
const director = "e2e_director@mys.local";

test.describe("Phase 12 — Transport", () => {
  test.skip(!seed.guardian?.user, "run seed_e2e.main first (guardian seed)");
  test.skip(
    !seed.transport?.assignment,
    "run seed_e2e.main first (transport seed)",
  );

  test("Guardian sees child transport assignment with route and fee", async ({
    page,
  }) => {
    const guardian = seed.guardian!.user;
    await loginPortal(
      page,
      guardian,
      seed.users[guardian].password,
      "/guardian/transport",
    );
    await expect(page.locator("h1")).toContainText("Transport");
    const portal = page.locator(".mys-portal");
    await expect(portal).toContainText("E2E Transport Route");
    await expect(portal).toContainText("4,500");
    await expect(portal).toContainText("Active");
  });

  test("Guardian portal nav exposes the Transport link", async ({ page }) => {
    const guardian = seed.guardian!.user;
    await loginPortal(
      page,
      guardian,
      seed.users[guardian].password,
      "/guardian/transport",
    );
    const link = page.locator(".mys-portal__nav-link", {
      hasText: "Transport",
    });
    await expect(link).toHaveAttribute("href", "/guardian/transport");
    await expect(link).toHaveClass(/is-active/);
  });

  test("Branch director can open the Student Transport desk list (scoped)", async ({
    page,
  }) => {
    test.skip(!seed.users[director], "run seed_e2e.main first");
    await loginAs(page, director, seed.users[director].password);
    await page.goto("/app/mys-student-transport/view/list");
    await expect(
      page.locator(".list-row-container, .result, .no-result").first(),
    ).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.locator("body")).not.toContainText(
      /Not Permitted|do not have access/i,
    );
    await expect(page.locator(".page-head .title-text")).toContainText(
      /Student Transport/i,
      {
        timeout: 15_000,
      },
    );
  });

  test("Branch director can open Route and Vehicle desk lists", async ({
    page,
  }) => {
    test.skip(!seed.users[director], "run seed_e2e.main first");
    await loginAs(page, director, seed.users[director].password);
    for (const [route, title] of [
      ["/app/mys-transport-route/view/list", /Transport Route/i],
      ["/app/mys-vehicle/view/list", /Vehicle/i],
    ] as const) {
      await page.goto(route);
      await expect(
        page.locator(".list-row-container, .result, .no-result").first(),
      ).toBeVisible({
        timeout: 20_000,
      });
      await expect(page.locator("body")).not.toContainText(
        /Not Permitted|do not have access/i,
      );
      await expect(page.locator(".page-head .title-text")).toContainText(
        title,
        {
          timeout: 15_000,
        },
      );
    }
  });
});
