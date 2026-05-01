import { expect, test } from "@playwright/test";

import {
  createAccountViaApi,
  getToken,
  login,
  resetAllData,
  sql,
} from "./helpers";

test.describe("Drafts list and detail", () => {
  test.beforeEach(async ({ page, request }) => {
    resetAllData();
    const token = await getToken(request);
    const accountId = await createAccountViaApi(request, token, {
      name: "测试号",
    });
    // Seed library_item + draft directly
    sql(
      "INSERT INTO library_items (id, source_url, original_title, original_content_text, status, tags, created_at, updated_at) VALUES ('11111111-1111-1111-1111-111111111111', 'https://x/article', '原标题', '原文内容', 'done', '[]'::jsonb, now(), now());"
    );
    sql(
      `INSERT INTO drafts (id, library_item_id, account_id, title, content_html, status, created_at, updated_at) VALUES ('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111', '${accountId}', '改写后的标题', '<p>改写后的正文</p>', 'reviewed', now(), now());`
    );
    await login(page);
  });

  test("drafts list shows the seeded draft", async ({ page }) => {
    await page.goto("/drafts");
    await expect(page.getByText("改写后的标题")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("draft detail loads title and body in editor", async ({ page }) => {
    await page.goto("/drafts/22222222-2222-2222-2222-222222222222");
    await expect(
      page.locator("input[value='改写后的标题'], input").first()
    ).toBeVisible({ timeout: 10_000 });
    const titleInput = page.locator("input").first();
    await expect(titleInput).toHaveValue("改写后的标题");
  });

  test("draft detail switches between edit and preview tabs", async ({
    page,
  }) => {
    await page.goto("/drafts/22222222-2222-2222-2222-222222222222");
    await page.getByRole("button", { name: /^预览$/ }).click();
    // After switching, the rendered HTML container should show the inner text
    await expect(page.getByText("改写后的正文")).toBeVisible();
    await page.getByRole("button", { name: /^编辑$/ }).click();
    // Back to textarea
    await expect(page.locator("textarea").first()).toBeVisible();
  });

  test.skip("editing the title and saving persists", async ({ page }) => {
    await page.goto("/drafts/22222222-2222-2222-2222-222222222222");
    const titleInput = page.locator("input").first();
    await titleInput.fill("新的标题");
    await page.getByRole("button", { name: /^保存$/ }).click();
    // Reload page to check persistence
    await page.reload();
    await expect(page.locator("input").first()).toHaveValue("新的标题");
  });
});
