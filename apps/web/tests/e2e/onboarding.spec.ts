import { expect, mockApi, test } from "./fixtures";

test("register and complete onboarding", async ({ page }) => {
  const calls = await mockApi(page, { user: null });
  await page.goto("/inbox");
  await expect(page).toHaveURL(/\/login$/);

  await page.getByRole("tab", { name: "Register" }).click();
  await page.getByLabel("Name").fill("Dana");
  await page.getByLabel("Email").fill("dana@example.com");
  await page.getByLabel("Password").fill("correct-horse");
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page).toHaveURL(/\/onboarding$/);
  await page.getByTestId("persona-fullstack").click();
  await expect(page.getByTestId("persona-fullstack")).toHaveAttribute("aria-checked", "true");
  await page.getByTestId("onboarding-next").click();

  await page.getByTestId("connect-marketplace").click();
  await expect(page.getByTestId("marketplace-status")).toContainText("Connected");
  await page.getByTestId("onboarding-next").click();

  await page.getByTestId("portfolio-input").setInputFiles({
    name: "case.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Case study\nShipped a Next.js storefront."),
  });
  await page.getByTestId("upload-portfolio").click();
  await expect(page.getByTestId("upload-list")).toContainText("case.md");
  await page.getByTestId("onboarding-next").click();

  await page.getByTestId("rate-floor").fill("50");
  await page.getByTestId("rate-target").fill("40");
  await expect(page.getByTestId("onboarding-next")).toBeDisabled();
  await page.getByTestId("rate-target").fill("85");
  await page.getByTestId("onboarding-next").click();

  await page.getByTestId("weekly-connects").fill("120");
  await page.getByTestId("onboarding-finish").click();

  await expect(page).toHaveURL(/\/inbox$/);
  await expect(page.getByTestId("job-row").first()).toBeVisible();

  const put = calls.find((c) => c.method === "PUT" && c.path === "/api/auth/onboarding");
  expect(put?.body).toMatchObject({
    persona: "fullstack",
    rates: { hourly_floor: 50, hourly_target: 85 },
    budgets: { weekly_connects: 120 },
  });
  expect(calls.some((c) => c.path === "/api/auth/portfolio")).toBeTruthy();
});
