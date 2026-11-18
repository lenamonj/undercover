import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { claim, claimRoutes, mockApi, renderAt, step } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows a waiting claim in full and runs the agent", async () => {
  const fetchMock = mockApi(claimRoutes(claim()), {
    "POST /api/claims/CLM-1001/run": { status: "in_progress" },
  });
  renderAt("/claims/CLM-1001");
  expect(await screen.findByText(/canceled\.$/)).toBeDefined();
  expect(screen.getByText("Airport hotel")).toBeDefined();
  expect(screen.getByText("Hotel receipt")).toBeDefined();
  expect(await screen.findByText("UnderCover Premium")).toBeDefined();
  expect(screen.getByText("CLM-0412")).toBeDefined();
  expect(screen.getByText("The agent has not run yet.")).toBeDefined();

  fireEvent.click(screen.getByRole("button", { name: "Run the agent" }));
  await vi.waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/claims/CLM-1001/run",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

it("polls the steps while the agent works", async () => {
  let polled = 0;
  mockApi(
    claimRoutes(() => {
      polled += 1;
      return polled < 2
        ? claim({ status: "in_progress", running: true })
        : claim({ status: "decided" });
    }, [step(), step({ step_id: 2, kind: "reply", detail: "Approved." })]),
  );
  renderAt("/claims/CLM-1001");
  expect(await screen.findByText("Working")).toBeDefined();
  expect(screen.getByText("Approved.")).toBeDefined();
  expect(
    await screen.findByText("Decided", {}, { timeout: 2500 }),
  ).toBeDefined();
});

it("shows a claim waiting for sign-off and signs it off", async () => {
  const fetchMock = mockApi(
    claimRoutes(
      claim({
        status: "awaiting_sign_off",
        decision: "approve",
        payout: 1500,
        reason: "Covered in full.",
        policy_section: "5. Baggage and Personal Effects",
      }),
      [step({ kind: "error", detail: "Refused (409)" })],
    ),
    { "POST /api/claims/CLM-1001/sign-off": claim() },
  );
  renderAt("/claims/CLM-1001");
  expect(
    await screen.findByText("Waits for a handler's sign-off"),
  ).toBeDefined();
  expect(screen.getByText("$1,500.00")).toBeDefined();
  expect(screen.getByText("Refused (409)")).toBeDefined();

  fireEvent.change(await screen.findByLabelText("Handler"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign off and pay" }));
  await vi.waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/claims/CLM-1001/sign-off",
      expect.objectContaining({
        body: JSON.stringify({ handler_id: "HND-01" }),
      }),
    );
  });
});

it("shows a decided claim that was signed off and paid", async () => {
  mockApi(
    claimRoutes(
      claim({
        status: "decided",
        decision: "approve",
        payout: 1500,
        paid_amount: 1500,
        signed_off_by: "Dana Whitfield",
        reason: "Covered in full.",
        policy_section: "5. Baggage and Personal Effects",
      }),
    ),
  );
  renderAt("/claims/CLM-1001");
  expect(await screen.findByText("Paid $1,500.00")).toBeDefined();
  expect(screen.getByText("Dana Whitfield")).toBeDefined();
  expect(screen.getByText("Covered in full.")).toBeDefined();
  expect(screen.queryByRole("button", { name: "Run the agent" })).toBeNull();
});

it("lists the sections read and the failed attempts", async () => {
  mockApi(
    claimRoutes(claim({ status: "waiting", attempts: 1 }), [
      step({
        step_id: 1,
        kind: "read",
        detail: "Claims manual 9. Repeat claims",
      }),
      step({ step_id: 2, kind: "error", detail: "The agent failed: timeout" }),
    ]),
  );
  renderAt("/claims/CLM-1001");
  const sections = await screen.findByRole("region", { name: "Sections read" });
  expect(sections.textContent).toContain("Claims manual 9. Repeat claims");
  expect(screen.getByText("Failed attempts")).toBeDefined();
  expect(screen.getByText("Read")).toBeDefined();
});

it("shows a declined claim as not paid", async () => {
  mockApi(
    claimRoutes(
      claim({
        status: "decided",
        decision: "decline",
        payout: 0,
        reason: "Not covered.",
        policy_section: "9. General exclusions",
      }),
    ),
  );
  renderAt("/claims/CLM-1001");
  expect(await screen.findByText("Not paid")).toBeDefined();
  expect(screen.getByText("Declined")).toBeDefined();
});

it("shows an error for an unknown claim", async () => {
  mockApi({});
  renderAt("/claims/CLM-1001");
  expect((await screen.findByRole("alert")).textContent).toContain("404");
});
