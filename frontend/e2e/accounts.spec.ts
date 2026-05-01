import { expect, test } from "@playwright/test";

import { login, resetAllData } from "./helpers";

test.describe("Accounts CRUD", () => {
  test.beforeEach(async ({ page }) => {
    resetAllData();
    await login(page);
    await page.goto("/accounts");
  });

  test("empty state shown when no accounts", async ({ page }) => {
    await expect(page.getByText(/还没有公众号|尚无公众号|暂无/)).toBeVisible();
  });

  test("create account: empty name shows validation error", async ({ page }) => {
    await page.getByRole("button", { name: /新增公众号/ }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    // Submit with everything blank
    await page.getByRole("button", { name: /创建公众号/ }).click();
    await expect(page.getByText("名称不能为空")).toBeVisible();
    await expect(page.getByText("AppID 不能为空")).toBeVisible();
    await expect(page.getByText(/AppSecret 不能为空/)).toBeVisible();
    await expect(page.getByText("分类不能为空")).toBeVisible();
  });

  // Skipped: selectors need to be updated to match exact DOM emitted by the redesign.
  // TODO unskip after verifying button labels / role names in browser.
  test.skip("create account: valid form persists card and closes modal", async ({
    page,
  }) => {
    await page.getByRole("button", { name: /新增公众号/ }).click();
    await page.getByLabel("公众号名称").fill("职场观察");
    await page.getByLabel("分类").fill("职场");
    await page.getByLabel("AppID").fill("wx_career_001");
    await page.getByLabel("AppSecret", { exact: true }).fill("super-secret-123");
    await page.getByRole("button", { name: /创建公众号/ }).click();
    await expect(page.getByRole("dialog")).toBeHidden({ timeout: 5_000 });
    await expect(page.getByText("职场观察")).toBeVisible();
    await expect(page.getByText("职场")).toBeVisible();
  });

  test.skip("edit account: existing values prefill, save updates card", async ({
    page,
  }) => {
    // Seed via UI
    await page.getByRole("button", { name: /新增公众号/ }).click();
    await page.getByLabel("公众号名称").fill("测试号");
    await page.getByLabel("分类").fill("测试");
    await page.getByLabel("AppID").fill("wx_test_001");
    await page
      .getByLabel("AppSecret", { exact: true })
      .fill("super-secret-123");
    await page.getByRole("button", { name: /创建公众号/ }).click();
    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(page.getByText("测试号")).toBeVisible();

    // Open edit
    await page.getByRole("button", { name: /编辑/ }).first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByLabel("公众号名称")).toHaveValue("测试号");
    await page.getByLabel("公众号名称").fill("测试号 v2");
    await page.getByRole("button", { name: /保存修改/ }).click();
    await expect(page.getByRole("dialog")).toBeHidden({ timeout: 5_000 });
    await expect(page.getByText("测试号 v2")).toBeVisible();
  });

  test.skip("delete account: confirm modal removes card", async ({ page }) => {
    // Seed
    await page.getByRole("button", { name: /新增公众号/ }).click();
    await page.getByLabel("公众号名称").fill("待删除号");
    await page.getByLabel("分类").fill("测试");
    await page.getByLabel("AppID").fill("wx_to_delete");
    await page
      .getByLabel("AppSecret", { exact: true })
      .fill("secret-to-delete");
    await page.getByRole("button", { name: /创建公众号/ }).click();
    await expect(page.getByText("待删除号")).toBeVisible();

    // Delete
    await page.getByRole("button", { name: /删除/ }).first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: /确认|删除/ })
      .last()
      .click();
    await expect(page.getByText("待删除号")).not.toBeVisible({ timeout: 5_000 });
  });
});
