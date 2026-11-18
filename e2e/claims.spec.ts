import { expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" });

test("running the agent shows its steps and decision", async ({ page }) => {
  await page.goto("/claims/CLM-1001");
  await page.getByRole("button", { name: "Run the agent" }).click();
  await expect(
    page.getByText('get_claim {"claim_id": "CLM-1001"}'),
  ).toBeVisible();
  await expect(page.getByText("Paid $420.00")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Approved CLM-1001.")).toBeVisible();
  await expect(
    page.getByText("The scripted model approves the amount claimed.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText("3. Trip Delay", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Back to the queue" }).click();
  const row = page.getByRole("row", { name: /CLM-1001/ });
  await expect(row.getByText("Decided")).toBeVisible();
});

test("a payout over $1,000 waits for a handler's sign-off", async ({
  page,
}) => {
  await page.goto("/claims/CLM-1002");
  await page.getByRole("button", { name: "Run the agent" }).click();
  await expect(
    page.getByText("Waits for a handler's sign-off", { exact: true }),
  ).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/pay_claim: Refused \(409\)/)).toBeVisible();

  await page.getByLabel("Handler").selectOption("HND-02");
  await page.getByRole("button", { name: "Sign off and pay" }).click();
  await expect(page.getByText("Paid $1,150.00", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Marcus Oyelaran", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".page-head").getByText("Decided")).toBeVisible();
});

test("working the queue leaves no claim waiting", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/");
  await page.getByRole("button", { name: "Work the queue" }).click();
  const counts = page.getByRole("list", { name: "Claims by status" });
  await expect(counts.locator(".count-waiting .count-number")).toHaveText("0", {
    timeout: 80_000,
  });
  await expect(counts.locator(".count-in_progress .count-number")).toHaveText(
    "0",
    {
      timeout: 80_000,
    },
  );
  await expect(
    page.getByRole("button", { name: "Work the queue" }),
  ).toBeDisabled();
});
