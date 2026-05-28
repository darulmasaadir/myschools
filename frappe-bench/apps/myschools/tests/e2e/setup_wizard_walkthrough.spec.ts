/**
 * Phase 6 — Setup Wizard walkthrough.
 *
 * Drives the wizard end-to-end as Administrator on a fresh, pre-setup
 * Frappe site:
 *   - language / region (Frappe stock slide)
 *   - first user (Frappe stock slide)
 *   - organization (ERPNext stock slide)
 *   - mys_franchise (our slide — optional cluster/branch/campus)
 *   - clicks Complete Setup
 *   - asserts the franchise tree got created server-side
 *
 * This proves the JS slide actually renders, that validate() doesn't block
 * a well-formed payload, that Frappe's setup_complete pipes our args
 * through to `create_first_franchise_tree`, and that the Python stage
 * persists the records.
 *
 * The test is env-gated because it requires a site whose
 * setup_complete = 0 — CI's bootstrapped sites have it pre-set to 1.
 * Run locally with:
 *
 *   MYS_WIZARD_TEST=1 MYS_BASE_URL=http://test_p4.localhost:8000 \
 *     npx playwright test tests/e2e/setup_wizard_walkthrough.spec.ts \
 *     --project=chromium
 *
 * If the target site already has setup_complete = 1 the test skips.
 */
import { test, expect, Page } from "@playwright/test";

const ENABLED = process.env.MYS_WIZARD_TEST === "1";

test.describe("Phase 6 — Setup Wizard walkthrough", () => {
	test.skip(!ENABLED, "MYS_WIZARD_TEST not set — wizard walkthrough is opt-in");

	test("Administrator walks all slides and the franchise tree is created", async ({ page }) => {
		test.setTimeout(180_000);

		// 1. Log in. Wizard auto-routes us to /app/setup-wizard.
		await page.goto("/login");
		await page.fill('input[name="login_email"], input#login_email', "Administrator");
		await page.fill('input[name="login_password"], input#login_password', "admin");
		await page.locator('button.btn-login, button:has-text("Login")').first().click();
		await page.waitForURL(/setup-wizard/, { timeout: 30_000 });

		// 2. Wait for the wizard to mount its first slide form.
		await page.waitForFunction(
			() =>
				!!(window as any).frappe?.wizard?.current_slide?.form &&
				(window as any).frappe.wizard.slides.length > 0,
			null,
			{ timeout: 30_000 },
		);

		// 3. Walk every slide. The wizard exposes `frappe.wizard.current_slide`
		//    and `.slides`; we drive it by name so slide order can change.
		const ANSWERS: Record<string, Record<string, string>> = {
			welcome: {
				language: "English",
				country: "Pakistan",
				timezone: "Asia/Karachi",
				currency: "PKR",
			},
			user: {
				full_name: "MYS Wizard Test User",
				email: "wizard-test@mys.local",
				password: "wizard-test-pw-123",
			},
			organization: {
				company_name: "MY School HO Wizard Test",
				company_abbr: "MSHW",
				fy_start_date: "2025-07-01",
				fy_end_date: "2026-06-30",
			},
			mys_franchise: {
				mys_cluster_code: "CLR-WIZARD",
				mys_cluster_name: "Wizard Cluster",
				mys_cluster_region: "Wizard Region",
				mys_branch_code: "BR-WIZ",
				mys_branch_name: "Wizard Branch",
				mys_campus_type: "Junior",
			},
		};

		const visited = new Set<string>();
		let mysSlideSeen = false;

		// Cap the loop — if it ever runs away the test should fail loud.
		for (let i = 0; i < 20; i++) {
			await page.waitForFunction(
				() => !!(window as any).frappe?.wizard?.current_slide?.form,
				null,
				{ timeout: 20_000 },
			);
			const slideName: string = await page.evaluate(
				() => (window as any).frappe.wizard.current_slide.name,
			);
			visited.add(slideName);
			if (slideName === "mys_franchise") mysSlideSeen = true;

			const answers = ANSWERS[slideName];
			if (answers) {
				await page.evaluate((values: Record<string, string>) => {
					const slide = (window as any).frappe.wizard.current_slide;
					for (const [fieldname, value] of Object.entries(values)) {
						const field = slide.form.get_field(fieldname);
						if (field) slide.form.set_value(fieldname, value);
					}
				}, answers);
			}

			const isLast: boolean = await page.evaluate(
				() =>
					(window as any).frappe.wizard.current_id ===
					(window as any).frappe.wizard.slides.length - 1,
			);

			if (isLast) {
				// Last slide → Complete Setup. The button name changes from
				// .next-btn to .complete-btn.
				const completeBtn = page.locator(".complete-btn").first();
				await expect(completeBtn).toBeVisible({ timeout: 10_000 });
				await completeBtn.click();
				break;
			}
			await page.locator(".next-btn").first().click();
			// The wizard re-renders the next slide; give it a beat to mount.
			await page.waitForTimeout(800);
		}

		// 4. After Complete Setup, Frappe redirects to /app (any non-wizard route).
		await page.waitForURL((url) => !/setup-wizard/.test(url.toString()), {
			timeout: 90_000,
		});
		await page.waitForLoadState("networkidle", { timeout: 60_000 }).catch(() => {});

		// Sanity: our slide was actually reached.
		expect(mysSlideSeen, `slides visited: ${[...visited].join(", ")}`).toBe(true);

		// 5. Assert backend state via authenticated REST.
		const apiBase = "/api/method/frappe.client.get_count";
		const getCount = async (doctype: string, name: string) => {
			const filters = JSON.stringify([["name", "=", name]]);
			const res = await page.request.get(
				`${apiBase}?doctype=${encodeURIComponent(doctype)}&filters=${encodeURIComponent(filters)}`,
			);
			expect(res.ok(), `GET ${doctype} ${name}: HTTP ${res.status()}`).toBe(true);
			const body = await res.json();
			return body.message as number;
		};

		expect(await getCount("MYS Cluster", "CLR-WIZARD")).toBe(1);
		expect(await getCount("MYS Branch", "BR-WIZ")).toBe(1);
		expect(await getCount("MYS Campus", "BR-WIZ-Junior")).toBe(1);

		// 6. Confirm setup_complete actually flipped.
		const sysRes = await page.request.get(
			"/api/method/frappe.client.get_single_value?doctype=System+Settings&field=setup_complete",
		);
		const sysBody = await sysRes.json();
		// Frappe returns 1 as either int 1 or string "1" depending on column type.
		expect(String(sysBody.message)).toBe("1");
	});
});
