import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.MYS_BASE_URL ?? "http://myschools.localhost:8000";

export default defineConfig({
	testDir: "./tests/e2e",
	timeout: 60_000,
	expect: { timeout: 10_000 },
	fullyParallel: false,
	retries: process.env.CI ? 1 : 0,
	workers: 1,
	reporter: [["list"]],
	use: {
		baseURL: BASE_URL,
		ignoreHTTPSErrors: true,
		trace: "retain-on-failure",
		video: "retain-on-failure",
		viewport: { width: 1440, height: 900 },
	},
	projects: [
		{
			name: "chromium",
			use: { ...devices["Desktop Chrome"] },
		},
	],
});
