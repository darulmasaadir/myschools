/**
 * Phase 14 — Document Mgmt (browser regression).
 *
 * Surfaces the phase added (spec-completeness audit):
 *  - Desk list for MYS Document (branch role can open, seeded row visible)
 *  - Desk create flow: branch role creates Document with title/branch/expiry
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect } from "@playwright/test";
import { loadSeed, loginAs, setFormValue, saveForm } from "./fixtures";

const seed = loadSeed();
const director = "e2e_director@mys.local";

test.describe("Phase 14 — Document Mgmt", () => {
  test.skip(!seed.users[director], "run seed_e2e.main first");
  test.skip(!seed.branch, "run seed_e2e.main first (branch seed)");

  test("Branch director can open MYS Document desk list", async ({ page }) => {
    await loginAs(page, director, seed.users[director].password);
    await page.goto("/app/mys-document/view/list");
    await expect(
      page.locator(".list-row-container, .result, .no-result").first(),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page.locator("body")).not.toContainText(
      /Not Permitted|do not have access/i,
    );
    await expect(page.locator(".page-head .title-text")).toContainText(
      /Document/i,
      { timeout: 15_000 },
    );
    if (seed.document?.document) {
      await expect(page.locator(".list-row-container")).toContainText(
        "E2E Compliance Certificate",
      );
    }
  });

  test("Branch director creates a Document via desk form", async ({ page }) => {
    const branch = seed.branch!;
    const run = Date.now().toString().slice(-6);
    const title = `E2E Desk Cert ${run}`;
    const expiry = new Date();
    expiry.setDate(expiry.getDate() + 60);
    const expiryIso = expiry.toISOString().slice(0, 10);

    await loginAs(page, director, seed.users[director].password);
    await page.goto("/app/mys-document/new");
    await setFormValue(page, "title", title);
    await setFormValue(page, "branch", branch);
    await setFormValue(page, "category", "Certificate");
    await setFormValue(page, "expiry_date", expiryIso);
    await saveForm(page);

    const persisted = await page.evaluate(() => {
      const d = (window as any).cur_frm.doc;
      return {
        name: d.name as string,
        branch: d.branch as string,
        status: d.status as string,
        title: d.title as string,
      };
    });
    expect(persisted.name).toMatch(/^DOC-/);
    expect(persisted.branch).toBe(branch);
    expect(persisted.status).toBe("Active");
    expect(persisted.title).toBe(title);
  });
});
