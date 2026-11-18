import { expect, test } from "@playwright/test";

test("the instructions page shows both sets of instructions", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Agent instructions" }).click();
  await expect(
    page.getByRole("heading", { name: "Running the queue" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Working a claim" }),
  ).toBeVisible();
  await expect(page.getByText(/You run UnderCover/)).toBeVisible();
  await expect(page.getByText(/You decide one travel insurance/)).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
});
