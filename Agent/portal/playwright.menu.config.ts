import { defineConfig } from "@playwright/test"

const appUrl = process.env.APP_URL ?? "http://127.0.0.1:4173"

export default defineConfig({
  testDir: "./tests/visual",
  testMatch: /menu-layout\.spec\.ts/,
  outputDir: "./test-results/playwright-menu",
  timeout: 120_000,
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: appUrl,
    channel: "chrome",
    viewport: { width: 1440, height: 900 },
    screenshot: "off",
  },
  webServer: [
    {
      command: "npm run dev -- --host 127.0.0.1 --port 4173",
      url: appUrl,
      reuseExistingServer: true,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
})
