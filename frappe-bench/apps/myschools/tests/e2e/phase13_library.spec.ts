/**
 * Phase 13 — Library (browser regression).
 *
 * Surfaces the phase added (spec-completeness audit):
 *  - Guardian /guardian/library read view (seeded loan, book title, status)
 *  - Guardian portal "Library" nav link
 *  - Desk lists for MYS Library Loan / Item (branch role can open)
 *  - Desk create flow: branch role builds Item -> Loan via desk forms
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect } from "@playwright/test";
import { loadSeed, loginAs, loginPortal, setFormValue, saveForm } from "./fixtures";

const seed = loadSeed();
const director = "e2e_director@mys.local";

test.describe("Phase 13 — Library", () => {
  test.skip(!seed.guardian?.user, "run seed_e2e.main first (guardian seed)");
  test.skip(!seed.library?.loan, "run seed_e2e.main first (library seed)");

  test("Guardian sees child library loan with book title and status", async ({
    page,
  }) => {
    const guardian = seed.guardian!.user;
    await loginPortal(
      page,
      guardian,
      seed.users[guardian].password,
      "/guardian/library",
    );
    await expect(page.locator("h1")).toContainText("Library");
    const portal = page.locator(".mys-portal");
    await expect(portal).toContainText("E2E Library Book");
    await expect(portal).toContainText("On Loan");
  });

  test("Guardian portal nav exposes the Library link", async ({ page }) => {
    const guardian = seed.guardian!.user;
    await loginPortal(
      page,
      guardian,
      seed.users[guardian].password,
      "/guardian/library",
    );
    const link = page.locator(".mys-portal__nav-link", { hasText: "Library" });
    await expect(link).toHaveAttribute("href", "/guardian/library");
    await expect(link).toHaveClass(/is-active/);
  });

  test("Branch director can open Library Loan and Item desk lists", async ({
    page,
  }) => {
    test.skip(!seed.users[director], "run seed_e2e.main first");
    await loginAs(page, director, seed.users[director].password);
    for (const [route, title] of [
      ["/app/mys-library-loan/view/list", /Library Loan/i],
      ["/app/mys-library-item/view/list", /Library Item/i],
    ] as const) {
      await page.goto(route);
      await expect(
        page.locator(".list-row-container, .result, .no-result").first(),
      ).toBeVisible({ timeout: 20_000 });
      await expect(page.locator("body")).not.toContainText(
        /Not Permitted|do not have access/i,
      );
      await expect(page.locator(".page-head .title-text")).toContainText(
        title,
        { timeout: 15_000 },
      );
    }
  });

  test("Branch director creates Library Item and issues a Loan via desk forms", async ({
    page,
  }) => {
    test.skip(!seed.users[director], "run seed_e2e.main first");
    test.skip(!seed.branch, "run seed_e2e.main first (branch seed)");
    test.skip(!seed.library?.student, "run seed_e2e.main first (library seed)");

    const branch = seed.branch!;
    const student = seed.library!.student;
    const run = Date.now().toString().slice(-6);
    const title = `E2E Desk Book ${run}`;
    const due = new Date();
    due.setDate(due.getDate() + 10);
    const dueIso = due.toISOString().slice(0, 10);

    await loginAs(page, director, seed.users[director].password);

    await page.goto("/app/mys-library-item/new");
    await setFormValue(page, "title", title);
    await setFormValue(page, "branch", branch);
    await setFormValue(page, "total_copies", "2");
    await setFormValue(page, "fine_per_day", "80");
    await saveForm(page);
    const item = await page.evaluate(
      () => (window as any).cur_frm.doc.name as string,
    );
    expect(item).toBeTruthy();

    await page.goto("/app/mys-library-loan/new");
    await setFormValue(page, "student", student);
    await page.waitForFunction(
      (b) => (window as any).cur_frm?.doc?.branch === b,
      branch,
      { timeout: 15_000 },
    );
    await setFormValue(page, "library_item", item);
    await setFormValue(page, "due_date", dueIso);
    await saveForm(page);

    const persisted = await page.evaluate(() => {
      const d = (window as any).cur_frm.doc;
      return {
        name: d.name as string,
        branch: d.branch as string,
        status: d.status as string,
      };
    });
    expect(persisted.name).toBeTruthy();
    expect(persisted.branch).toBe(branch);
    expect(persisted.status).toBe("On Loan");
  });
});
