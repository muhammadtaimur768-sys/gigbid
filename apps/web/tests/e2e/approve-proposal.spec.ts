import { expect, mockApi, test } from "./fixtures";

test("approve a proposal after checking evidence and the dry run", async ({ page }) => {
  const calls = await mockApi(page);
  await page.goto("/inbox");

  // ranked by fit: best match first
  await expect(page.getByTestId("job-row").first()).toContainText("RAG chatbot");
  await page.getByRole("link", { name: "Review draft" }).click();
  await expect(page).toHaveURL(/\/studio\/t-rag$/);

  // every claim shows its evidence on hover / focus
  const supported = page.locator('[data-claim-status="supported"]');
  await supported.hover();
  await expect(page.getByTestId("evidence-popover")).toContainText("aiml-case-03");
  await page.mouse.move(0, 0);
  await expect(page.getByTestId("evidence-popover")).toHaveCount(0);
  await page.locator('[data-claim-status="unsupported"]').focus();
  await expect(page.getByTestId("evidence-popover")).toContainText("No portfolio evidence");

  // critic and compliance comments inline
  await expect(page.getByTestId("critic-comment")).toContainText("Opening is generic");
  await expect(page.getByTestId("compliance-comment")).toContainText("passes");

  await page.getByTestId("dry-run").click();
  await expect(page.getByTestId("dry-run-cost")).toHaveText("12");

  await page.getByTestId("approve").click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("spending 12 Connects");
  await page.getByTestId("confirm-approve").click();

  await expect(page.getByTestId("decision-result")).toContainText("Approved");
  expect(calls.some((c) => c.method === "POST" && c.path === "/api/proposals/t-rag/approve")).toBeTruthy();
});
