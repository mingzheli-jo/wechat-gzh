import { expect, test } from "@playwright/test";

import { resetAllData } from "./helpers";

test.describe("Auth", () => {
  test.beforeAll(() => {
    resetAllData();
  });

  test("login page renders the split-screen brand panel", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /微信公众号/ })).toBeVisible();
    await expect(page.getByLabel("用户名")).toHaveValue("admin");
  });

  test("wrong password keeps user on /login with error message", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.fill("input#password", "WRONG");
    await page.click("button[type=submit]");
    await expect(page.getByText("用户名或密码错误")).toBeVisible({
      timeout: 5_000,
    });
    expect(page.url()).toContain("/login");
  });

  test("correct password redirects to /library", async ({ page }) => {
    await page.goto("/login");
    await page.fill("input#password", "hunter2");
    await page.click("button[type=submit]");
    await page.waitForURL(/\/library/, { timeout: 10_000 });
    const token = await page.evaluate(() => localStorage.getItem("token"));
    expect(token).toBeTruthy();
  });

  test("missing token on protected route redirects back to /login", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.evaluate(() => localStorage.removeItem("token"));
    await page.goto("/accounts");
    await page.waitForURL(/\/login/, { timeout: 5_000 });
  });

  test("logout button clears token and returns to /login", async ({ page }) => {
    await page.goto("/login");
    await page.fill("input#password", "hunter2");
    await page.click("button[type=submit]");
    await page.waitForURL(/\/library/);
    await page.getByRole("button", { name: /退出/ }).click();
    await page.waitForURL(/\/login/, { timeout: 5_000 });
    const token = await page.evaluate(() => localStorage.getItem("token"));
    expect(token).toBeFalsy();
  });
});
