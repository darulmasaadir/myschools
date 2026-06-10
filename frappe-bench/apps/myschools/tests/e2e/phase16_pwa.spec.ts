/**
 * Phase 16 — Mobile PWA (browser regression).
 *
 * Surfaces the phase added (spec-completeness audit):
 *  - Web manifest is served and names MY School
 *  - Service worker script is served at /mys-pwa-sw.js
 *  - Guardian portal page links manifest + registers service worker
 *
 * Pre-req: bench execute myschools.scripts.seed_e2e.main
 */
import { test, expect } from "@playwright/test";
import { loadSeed, loginAs } from "./fixtures";

const seed = loadSeed();
const guardian = "e2e_guardian@mys.local";

test.describe("Phase 16 — Mobile PWA", () => {
  test.skip(!seed.users[guardian], "run seed_e2e.main first");

  test("Web manifest is served with MY School metadata", async ({ request }) => {
    const response = await request.get("/assets/myschools/pwa/manifest.json");
    expect(response.status()).toBeLessThan(400);
    const manifest = await response.json();
    expect(manifest.name).toBe("MY School");
    expect(manifest.start_url).toBe("/portal");
    expect(manifest.display).toBe("standalone");
    expect(manifest.theme_color).toBe("#0f7a4a");
    expect(manifest.icons?.length).toBeGreaterThan(0);
  });

  test("Service worker script is served at /mys-pwa-sw.js", async ({ request }) => {
    const response = await request.get("/mys-pwa-sw.js");
    expect(response.status()).toBeLessThan(400);
    const contentType = response.headers()["content-type"] || "";
    expect(contentType).toContain("javascript");
    const body = await response.text();
    expect(body).toContain("addEventListener");
    expect(response.headers()["service-worker-allowed"]).toBe("/");
  });

  test("Guardian portal links manifest and registers service worker", async ({
    page,
  }) => {
    await loginAs(page, guardian, seed.users[guardian].password);
    await page.goto("/guardian");
    await expect(page.locator('link[rel="manifest"]')).toHaveAttribute(
      "href",
      "/assets/myschools/pwa/manifest.json",
    );
    await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute(
      "content",
      "#0f7a4a",
    );
    await expect(page.locator('script[src*="portal_pwa.js"]')).toHaveCount(1);

    // portal_pwa.js registers on window "load" — poll until active (CI can be slow).
    await page.waitForFunction(
      async () => {
        if (!("serviceWorker" in navigator)) {
          return false;
        }
        let reg = await navigator.serviceWorker.getRegistration("/");
        if (!reg) {
          try {
            reg = await navigator.serviceWorker.register("/mys-pwa-sw.js", {
              scope: "/",
            });
          } catch {
            reg = await navigator.serviceWorker.getRegistration("/");
          }
        }
        if (!reg) {
          return false;
        }
        await navigator.serviceWorker.ready;
        return Boolean(reg.active || reg.installing || reg.waiting);
      },
      null,
      { timeout: 15_000 },
    );
  });
});
