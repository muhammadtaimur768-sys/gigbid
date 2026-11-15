import { expect, mockApi, test } from "./fixtures";

test("reject a proposal with a reason", async ({ page }) => {
  const calls = await mockApi(page);
  await page.goto("/studio/t-rag");

  await page.getByTestId("reject").click();
  const dialog = page.getByRole("dialog", { name: "Reject this draft" });
  await expect(dialog).toBeVisible();

  // Esc closes the dialog without rejecting
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  expect(calls.some((c) => c.path.endsWith("/reject"))).toBeFalsy();

  await page.getByTestId("reject").click();
  await dialog.getByLabel("Other").check();
  await expect(dialog.getByTestId("confirm-reject")).toBeDisabled();
  await dialog.getByLabel("Price is wrong").check();
  await dialog.getByTestId("reject-note").fill("client budget is far below my floor");
  await dialog.getByTestId("confirm-reject").click();

  await expect(page.getByTestId("decision-result")).toContainText("Rejected");
  const call = calls.find((c) => c.method === "POST" && c.path === "/api/proposals/t-rag/reject");
  expect(call?.body).toMatchObject({ reason: "Price is wrong: client budget is far below my floor" });
});
