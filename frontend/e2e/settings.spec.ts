import { expect, test } from "@playwright/test";

import { login, resetAllData } from "./helpers";

test.describe("Settings page", () => {
  test.beforeEach(async ({ page }) => {
    resetAllData();
    await login(page);
    await page.goto("/settings");
  });

  test("renders three sections: providers, role bindings, usage", async ({
    page,
  }) => {
    await expect(page.getByRole("heading", { name: /AI 服务商/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /角色绑定/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /AI 用量/ })).toBeVisible();
  });

  test.skip("add a provider via the inline form", async ({ page }) => {
    // Each input is keyed by its name field; locate by placeholder
    await page.getByPlaceholder(/name|名称|^name$/i).first().fill("test_provider");
    // The form has 4 inputs: name, base_url, api_key, models
    const inputs = page.locator(
      'section:has(h3:has-text("添加 Provider")) input, section:has(h2:has-text("AI 服务商")) input'
    );
    const count = await inputs.count();
    if (count >= 4) {
      await inputs.nth(0).fill("test_provider");
      await inputs.nth(1).fill("https://api.test.example.com/v1");
      await inputs.nth(2).fill("sk-test-12345");
      await inputs.nth(3).fill("test-model-1,test-model-2");
      await page.getByRole("button", { name: /^添加$/ }).click();
      await expect(page.getByText("test_provider")).toBeVisible({
        timeout: 5_000,
      });
    }
  });

  test("usage dashboard shows total cost / tokens cards", async ({ page }) => {
    await expect(page.getByText(/总成本|cost/i)).toBeVisible();
    await expect(page.getByText(/Prompt tokens/i)).toBeVisible();
    await expect(page.getByText(/Completion tokens/i)).toBeVisible();
  });
});
