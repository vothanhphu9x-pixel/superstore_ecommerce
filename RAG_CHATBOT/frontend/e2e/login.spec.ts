import { expect, test } from "@playwright/test";

const email = process.env.E2E_STAFF_EMAIL;
const password = process.env.E2E_STAFF_PASSWORD;

test.beforeAll(() => {
  if (!email || !password) {
    throw new Error("E2E_STAFF_EMAIL and E2E_STAFF_PASSWORD are required");
  }
});

test("unauthenticated dashboard redirects to login", async ({ page }) => {
  await page.goto("/dashboard");

  await expect(page).toHaveURL(/\/login\?next=/);
  await expect(
    page.getByRole("heading", { name: "Staff sign in" }),
  ).toBeVisible();
});

test("staff can log in and log out through Next.js", async ({ page }) => {
  const directApiRequests: string[] = [];

  page.on("request", (request) => {
    if (new URL(request.url()).port === "8000") {
      directApiRequests.push(request.url());
    }
  });

  await page.goto("/login");
  await page.getByLabel("Email").fill(email!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Dashboard kinh doanh" }),
  ).toBeVisible();

  const staffCookie = (await page.context().cookies()).find(
    (cookie) => cookie.name === "superstore_staff",
  );

  expect(staffCookie).toBeDefined();
  expect(staffCookie?.httpOnly).toBe(true);
  expect(staffCookie?.sameSite).toBe("Lax");
  expect(directApiRequests).toEqual([]);

  await page.getByRole("button", { name: "Sign out" }).click();

  await expect(page).toHaveURL(/\/login$/);
  expect(
    (await page.context().cookies()).some(
      (cookie) => cookie.name === "superstore_staff",
    ),
  ).toBe(false);

  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?next=/);
});

test("wrong password does not create a session", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email!);
  await page.getByLabel("Password").fill(`${password}-wrong`);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(
    page.getByRole("alert").filter({ hasText: "Email or password is incorrect" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);

  const cookies = await page.context().cookies();
  expect(cookies.some((cookie) => cookie.name === "superstore_staff")).toBe(
    false,
  );
});

test("BFF rejects a cross-site POST", async ({ request }) => {
  const response = await request.post("/api/internal/staff/logout", {
    headers: {
      Origin: "http://untrusted.example",
    },
  });

  expect(response.status()).toBe(403);
});
