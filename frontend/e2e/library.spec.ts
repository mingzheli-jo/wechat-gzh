import { expect, test } from "@playwright/test";

import { createAccountViaApi, getToken, login, resetAllData, sql } from "./helpers";

test.describe("Library", () => {
  test.beforeEach(async ({ page, request }) => {
    resetAllData();
    const token = await getToken(request);
    await createAccountViaApi(request, token, { name: "测试号" });
    await login(page);
    await page.goto("/library");
  });

  test("paste URLs and ingest creates pending items", async ({ page }) => {
    const fakeUrl = `https://mp.weixin.qq.com/s/playwright-fake-${Date.now()}`;
    await page.locator("textarea#urls").fill(fakeUrl);
    await page.getByRole("button", { name: /添加抓取/ }).click();
    await expect(page.getByText(fakeUrl)).toBeVisible({ timeout: 10_000 });
    // Status badge should appear (pending or processing or failed depending on timing)
    await expect(page.getByText(/待抓取|抓取中|失败|完成/).first()).toBeVisible();
  });

  test("multi-select shows floating action bar with selection count", async ({
    page,
  }) => {
    // Seed a 'done' library item via SQL so we can select it
    sql(
      "INSERT INTO library_items (id, source_url, original_title, original_content_text, status, tags, created_at, updated_at) VALUES (gen_random_uuid(), 'https://x/1', '测试文章', '测试内容', 'done', '[]'::jsonb, now(), now());"
    );
    await page.reload();
    // Find and check the row checkbox
    const checkbox = page.locator("input[type=checkbox]").first();
    await expect(checkbox).toBeEnabled();
    await checkbox.check();
    await expect(page.getByText(/选中.*1|当前选中.*1|1.*篇/)).toBeVisible();
  });

  test("trigger rewrite with no account selected leaves button disabled", async ({
    page,
  }) => {
    sql(
      "INSERT INTO library_items (id, source_url, original_title, original_content_text, status, tags, created_at, updated_at) VALUES (gen_random_uuid(), 'https://x/2', '测试文章2', '测试内容2', 'done', '[]'::jsonb, now(), now());"
    );
    await page.reload();
    await page.locator("input[type=checkbox]").first().check();
    const rewriteBtn = page.getByRole("button", { name: /开始改写/ });
    await expect(rewriteBtn).toBeDisabled();
  });
});
