import { expect, test } from "@playwright/test";

test("login flow", async ({ page }) => {
  await page.goto("/login");
  await page.fill("input[placeholder='用户名']", "admin");
  await page.fill("input[placeholder='密码']", "hunter2");
  await page.click("button:has-text('登录')");
  await expect(page).toHaveURL(/\/library|\/accounts/);
});
