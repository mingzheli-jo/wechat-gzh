import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 1,
  use: {
    baseURL: process.env.BASE_URL || "http://localhost",
    headless: true,
    navigationTimeout: 30_000,
    actionTimeout: 10_000,
  },
  reporter: [["list"]],
});
