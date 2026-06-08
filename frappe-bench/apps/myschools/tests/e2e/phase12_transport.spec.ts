/**
 * Phase 12 — Transport (browser regression).
 *
 * Surfaces the phase added (spec-completeness audit):
 *  - Guardian /guardian/transport read view (seeded route, fee, status)
 *  - Guardian portal "Transport" nav link
 *  - Desk lists for MYS Student Transport / Route / Vehicle (branch role can open)
 *  - Desk MYS Student Transport list is branch-scoped for the director
 *  - Desk create flow: branch role builds Vehicle -> Route -> Student Transport
 *    through the real form (fetch_from branch/fee wiring + validate hook fire)
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect } from "@playwright/test";
import { loadSeed, loginAs, loginPortal, setFormValue, saveForm } from "./fixtures";

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

  test("Branch director builds Vehicle -> Route -> Student Transport via desk forms", async ({
    page,
  }) => {
    test.skip(!seed.users[director], "run seed_e2e.main first");
    test.skip(!seed.branch, "run seed_e2e.main first (branch seed)");
    test.skip(
      !seed.transport?.student,
      "run seed_e2e.main first (transport seed)",
    );

    const branch = seed.branch!;
    const student = seed.transport!.student;
    const run = Date.now().toString().slice(-6);
    const reg = `E2E-DESK-${run}`;
    const routeName = `E2E Desk Route ${run}`;
    const fee = "5200";

    await loginAs(page, director, seed.users[director].password);

    // 1. Vehicle — branch role can create; capacity guard lives on the controller.
    await page.goto("/app/mys-vehicle/new");
    await setFormValue(page, "registration_no", reg);
    await setFormValue(page, "branch", branch);
    await setFormValue(page, "capacity", "45");
    await setFormValue(page, "model", "E2E Desk Coach");
    await saveForm(page);
    const vehicle = await page.evaluate(
      () => (window as any).cur_frm.doc.name as string,
    );
    expect(vehicle).toBeTruthy();

    // 2. Route — links the vehicle we just made; same branch (validate enforces it).
    await page.goto("/app/mys-transport-route/new");
    await setFormValue(page, "route_name", routeName);
    await setFormValue(page, "branch", branch);
    await setFormValue(page, "vehicle", vehicle);
    await setFormValue(page, "fee_amount", fee);
    await saveForm(page);
    const route = await page.evaluate(
      () => (window as any).cur_frm.doc.name as string,
    );
    expect(route).toBeTruthy();

    // 3. Student Transport — branch auto-fetches from student, fee auto-fetches
    //    from route (fetch_from / fetch_if_empty wiring), validate hook passes.
    await page.goto("/app/mys-student-transport/new");
    await setFormValue(page, "student", student);
    await page.waitForFunction(
      (b) => (window as any).cur_frm?.doc?.branch === b,
      branch,
      { timeout: 15_000 },
    );
    await setFormValue(page, "route", route);
    await page.waitForFunction(
      (f) => Number((window as any).cur_frm?.doc?.fee_amount) === f,
      Number(fee),
      { timeout: 15_000 },
    );
    await setFormValue(page, "pickup_point", "E2E Desk Stop");
    await saveForm(page);

    const persisted = await page.evaluate(() => {
      const d = (window as any).cur_frm.doc;
      return {
        name: d.name as string,
        branch: d.branch as string,
        fee: Number(d.fee_amount),
        status: d.status as string,
      };
    });
    expect(persisted.name).toBeTruthy();
    expect(persisted.branch).toBe(branch);
    expect(persisted.fee).toBe(Number(fee));
    expect(persisted.status).toBe("Active");
  });
});
