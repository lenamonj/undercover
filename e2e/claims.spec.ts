import { expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" });

test("a capped run fills in its to-do list and finishes", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Claims to work").fill("3");
  await page.getByRole("button", { name: "Work the queue" }).click();

  const todos = page.getByRole("list", { name: "To-do list" });
  await expect(todos.getByText("In progress")).toBeVisible();
  await expect(page.getByText("Approved 3 claims.")).toBeVisible({
    timeout: 30_000,
  });
  await expect(todos.getByText("Done")).toHaveCount(3);
  await expect(page.getByText("3 of up to 3 claims started")).toBeVisible();
  const counts = page.getByRole("list", { name: "Claims by status" });
  await expect(counts.locator(".count-waiting .count-number")).toHaveText("22");
});

test("a claim worked in the run shows its steps, sections and decision", async ({
  page,
}) => {
  await page.goto("/claims/CLM-1001");
  const sections = page.getByRole("region", { name: "Sections read" });
  await expect(
    sections.getByText("Policy wording 3. Trip Delay"),
  ).toBeVisible();
  await expect(page.getByText("Paid $420.00", { exact: true })).toBeVisible();
  await expect(
    page.getByText('get_claim {"claim_id": "CLM-1001"}'),
  ).toBeVisible();
  await expect(page.getByText("Approved CLM-1001.")).toBeVisible();
});

test("a payout over $1,000 from the run waits for sign-off", async ({
  page,
}) => {
  await page.goto("/claims/CLM-1002");
  await expect(
    page.getByText("Waits for a handler's sign-off", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Handler").selectOption("HND-02");
  await page.getByRole("button", { name: "Sign off and pay" }).click();
  await expect(page.getByText("Paid $1,150.00", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Marcus Oyelaran", { exact: true }),
  ).toBeVisible();
});

test("one named claim can still be run on its own", async ({ page }) => {
  await page.goto("/claims/CLM-1004");
  await page.getByRole("button", { name: "Run the agent" }).click();
  await expect(page.getByText("Approved CLM-1004.")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.locator(".page-head").getByText("Decided")).toBeVisible();
});
