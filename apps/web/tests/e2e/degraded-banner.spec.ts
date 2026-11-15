import { expect, mockApi, test } from "./fixtures";

test("shows the degraded banner when the marketplace is unavailable", async ({ page }) => {
  await mockApi(page, {
    health: { status: "degraded", marketplace: "unavailable", marketplace_detail: "GigSim timed out after 3 retries" },
    overrides: {
      "GET /api/jobs": (route) =>
        route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({ items: [], total: 0, marketplace: "unavailable", refreshed: false }),
        }),
    },
  });
  await page.goto("/inbox");
  const banner = page.getByTestId("degraded-banner");
  await expect(banner).toBeVisible();
  await expect(banner).toContainText("Marketplace unavailable");
  await expect(banner).toContainText("GigSim timed out");
  await expect(page.getByText("showing cached jobs only")).toBeVisible();
  await expect(page.getByTestId("empty")).toContainText("No jobs match");
});

test("shows an API-down banner when health fails", async ({ page }) => {
  await mockApi(page, { health: 503 });
  await page.goto("/inbox");
  await expect(page.getByTestId("degraded-banner")).toContainText("GigBid API unavailable");
});

test("no banner when everything is healthy", async ({ page }) => {
  await mockApi(page);
  await page.goto("/inbox");
  await expect(page.getByTestId("job-row").first()).toBeVisible();
  await expect(page.getByTestId("degraded-banner")).toHaveCount(0);
});
