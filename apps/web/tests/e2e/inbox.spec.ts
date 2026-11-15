import { expect, mockApi, test } from "./fixtures";

test("inbox ranks by fit, flags risk and skips a job", async ({ page }) => {
  const calls = await mockApi(page);
  await page.goto("/inbox");
  const rows = page.getByTestId("job-row");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText("RAG chatbot");
  await expect(rows.nth(2)).toContainText("Shopify");
  await expect(rows.nth(1).getByTestId("risk-badge")).toContainText("Off-platform payment");

  await page.getByRole("button", { name: "Skip Quick test task, pay via Telegram" }).click();
  await expect(rows).toHaveCount(2);
  expect(calls.some((c) => c.method === "POST" && c.path === "/api/jobs/job-scam/skip")).toBeTruthy();
});

test("error state with retry when the jobs request fails", async ({ page }) => {
  await mockApi(page, {
    overrides: {
      "GET /api/jobs": (route) => route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"boom"}' }),
    },
  });
  await page.goto("/inbox");
  await expect(page.getByTestId("error")).toContainText("boom");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});
