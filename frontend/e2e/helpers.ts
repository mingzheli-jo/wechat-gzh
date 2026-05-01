import { spawnSync } from "node:child_process";

import type { APIRequestContext, Page } from "@playwright/test";

const PG_CONTAINER = "wechat-batch-rewriter-postgres-1";

/**
 * Run SQL inside the dockerized Postgres container via stdin.
 * Avoids shell-escaping issues with quotes / semicolons on Windows.
 */
export function sql(statement: string): void {
  const result = spawnSync(
    "docker",
    [
      "exec",
      "-i",
      PG_CONTAINER,
      "psql",
      "-U",
      "postgres",
      "-d",
      "wechat_rewriter",
    ],
    { input: statement, encoding: "utf-8" }
  );
  if (result.status !== 0) {
    throw new Error(
      `psql failed (status ${result.status}):\n  stmt: ${statement}\n  stderr: ${result.stderr}`
    );
  }
}

/**
 * Reset all user-content tables (keep admin/accounts schema, but clear rows).
 * Drafts depend on review_reports via FK; delete in order.
 */
export function resetAllData(): void {
  sql(
    "DELETE FROM ai_usage; DELETE FROM images; DELETE FROM review_reports; UPDATE drafts SET review_report_id = NULL; DELETE FROM drafts; DELETE FROM library_items; DELETE FROM accounts; DELETE FROM role_bindings; DELETE FROM ai_providers;"
  );
}

/**
 * Log in via UI by going to /login and submitting the form.
 * Persists token in localStorage for subsequent navigation.
 */
export async function login(page: Page): Promise<void> {
  await page.goto("/login");
  await page.fill("input#username", "admin");
  await page.fill("input#password", "hunter2");
  await page.click("button[type=submit]");
  await page.waitForURL(/\/library/);
}

/**
 * Get a valid bearer token via the API (faster than UI login).
 */
export async function getToken(request: APIRequestContext): Promise<string> {
  const resp = await request.post("/api/auth/login", {
    form: { username: "admin", password: "hunter2" },
  });
  const body = (await resp.json()) as { access_token: string };
  return body.access_token;
}

/**
 * Seed an account directly via API. Returns the account id.
 */
export async function createAccountViaApi(
  request: APIRequestContext,
  token: string,
  overrides: Partial<{ name: string; category: string }> = {}
): Promise<string> {
  const resp = await request.post("/api/accounts", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: overrides.name ?? "测试号",
      wechat_appid: "wx_test",
      wechat_secret: "secret-1234567890",
      category: overrides.category ?? "测试",
      title_prompt: "",
      content_prompt: "",
      style_desc: "",
    },
  });
  const body = (await resp.json()) as { id: string };
  return body.id;
}
