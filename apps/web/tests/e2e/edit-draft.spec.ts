import { expect, mockApi, test } from "./fixtures";

test("edit a draft, regenerate one paragraph and approve the edited text", async ({ page }) => {
  const calls = await mockApi(page);
  await page.goto("/studio/t-rag");
  await page.evaluate(() => localStorage.clear());
  await page.reload();

  // regenerate only the last paragraph
  await expect(page.getByTestId("paragraph")).toHaveCount(4);
  await page.getByRole("button", { name: "Regenerate paragraph 4" }).click();
  await expect(page.getByTestId("paragraph").nth(3)).toContainText("30 minute scoping call");
  await expect(page.getByTestId("paragraph").nth(0)).toContainText("retrieval systems");
  const regen = calls.find((c) => c.path === "/api/proposals/t-rag/regenerate");
  expect(regen?.body).toMatchObject({ paragraph_index: 3 });

  // remove the unsupported claim by hand
  await page.getByTestId("toggle-edit").click();
  const editor = page.getByTestId("draft-editor");
  const text = await editor.inputValue();
  await editor.fill(text.replace("I have led a team of 50 engineers at a large bank.\n\n", ""));

  // unsaved edits survive a refresh
  await page.reload();
  await expect(page.getByText("Unsaved edits")).toBeVisible();

  await page.getByTestId("save-edit").click();
  await expect(page.getByTestId("decision-result")).toContainText("Edits saved");
  const edit = calls.find((c) => c.method === "POST" && c.path === "/api/proposals/t-rag/edit");
  const sent = (edit?.body as { edited_text: string }).edited_text;
  expect(sent).not.toContain("50 engineers");
  expect(sent).toContain("30 minute scoping call");
});
