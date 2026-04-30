import { expect, test } from "@playwright/test";

const BASE = "http://localhost";

test.describe("Stage 1 smoke", () => {
  test("login page loads", async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await expect(page.locator("h1")).toHaveText("登录");
    await expect(page.getByPlaceholder("用户名")).toHaveValue("admin");
  });

  test("login with admin/hunter2 redirects to /accounts", async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByPlaceholder("密码").fill("hunter2");
    await page.getByRole("button", { name: "登录" }).click();
    await page.waitForURL(`${BASE}/accounts`, { timeout: 10_000 });
    await expect(page.locator("h1")).toHaveText("公众号");
    const token = await page.evaluate(() => localStorage.getItem("token"));
    expect(token).toBeTruthy();
  });

  test("wrong password shows error and stays on /login", async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByPlaceholder("密码").fill("WRONG");
    await page.getByRole("button", { name: "登录" }).click();
    await expect(page.getByText("用户名或密码错误")).toBeVisible({
      timeout: 5_000,
    });
    expect(page.url()).toBe(`${BASE}/login`);
  });

  test("missing token redirects /accounts to /login", async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.evaluate(() => localStorage.removeItem("token"));
    await page.goto(`${BASE}/accounts`);
    await page.waitForURL(`${BASE}/login`, { timeout: 5_000 });
  });

  test("authed user can create + list + delete account via API", async ({
    request,
  }) => {
    const login = await request.post(`${BASE}/api/auth/login`, {
      form: { username: "admin", password: "hunter2" },
    });
    expect(login.ok()).toBeTruthy();
    const token = (await login.json()).access_token as string;
    const auth = { Authorization: `Bearer ${token}` };

    const created = await request.post(`${BASE}/api/accounts`, {
      headers: auth,
      data: {
        name: "smoke-test-账号",
        wechat_appid: "wx_smoke_001",
        wechat_secret: "secret-plaintext-12345",
        category: "测试",
      },
    });
    expect(created.status()).toBe(201);
    const created_body = await created.json();
    expect(created_body.name).toBe("smoke-test-账号");
    expect(created_body).not.toHaveProperty("wechat_secret");
    const id = created_body.id as string;

    const list = await request.get(`${BASE}/api/accounts`, { headers: auth });
    expect(list.ok()).toBeTruthy();
    const items = (await list.json()) as Array<{ id: string; name: string }>;
    expect(items.find((x) => x.id === id)?.name).toBe("smoke-test-账号");

    const patched = await request.patch(`${BASE}/api/accounts/${id}`, {
      headers: auth,
      data: { name: "renamed" },
    });
    expect((await patched.json()).name).toBe("renamed");

    const deleted = await request.delete(`${BASE}/api/accounts/${id}`, {
      headers: auth,
    });
    expect(deleted.status()).toBe(204);

    const gone = await request.get(`${BASE}/api/accounts/${id}`, {
      headers: auth,
    });
    expect(gone.status()).toBe(404);
  });
});
