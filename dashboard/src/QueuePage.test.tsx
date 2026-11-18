import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockApi, queueItem, renderAt, run } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const queue = [
  queueItem(),
  queueItem({
    claim_id: "CLM-1002",
    customer_name: "Tom Reyes",
    claim_type: "baggage",
    amount_claimed: 1150,
    status: "decided",
    decision: "approve",
    payout: 1100,
  }),
  queueItem({ claim_id: "CLM-1003", status: "needs_handler" }),
];

it("lists the queue with counts by status", async () => {
  mockApi({ "GET /api/claims": queue, "GET /api/runs/current": null });
  renderAt("/");
  expect(await screen.findByText("CLM-1001")).toBeDefined();
  expect(screen.getByText("Tom Reyes")).toBeDefined();
  expect(screen.getByText("$1,150.00")).toBeDefined();
  expect(screen.getByText("Approved")).toBeDefined();
  const counts = screen.getByRole("list", { name: "Claims by status" });
  expect(within(counts).getAllByText("1")).toHaveLength(3);
  expect(within(counts).getAllByText("0")).toHaveLength(2);
  expect(screen.getAllByText("Left for a handler")).toHaveLength(2);
  expect(screen.queryByRole("list", { name: "To-do list" })).toBeNull();
});

it("starts a capped run and polls its to-do list until it finishes", async () => {
  let polled = 0;
  const fetchMock = mockApi({
    "GET /api/claims": queue,
    get "GET /api/runs/current"() {
      polled += 1;
      if (polled === 1) return null;
      if (polled === 2) return run();
      return run({
        status: "finished",
        todos: [{ content: "Work CLM-1001", status: "done" }],
        summary: "One claim approved.",
      });
    },
    "POST /api/runs": run(),
  });
  renderAt("/");
  fireEvent.change(await screen.findByLabelText("Claims to work"), {
    target: { value: "3" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Work the queue" }));

  const todos = await screen.findByRole("list", { name: "To-do list" });
  expect(within(todos).getByText("To do")).toBeDefined();
  expect(within(todos).getByText("In progress")).toBeDefined();
  expect(within(todos).getByText("Done")).toBeDefined();
  expect(within(todos).getByText("Left for a handler")).toBeDefined();
  expect(screen.getByText("2 of up to 5 claims started")).toBeDefined();
  expect(screen.getByRole("button", { name: "Work the queue" })).toHaveProperty(
    "disabled",
    true,
  );

  expect(
    await screen.findByText("One claim approved.", {}, { timeout: 2500 }),
  ).toBeDefined();
  expect(screen.getByText("Finished")).toBeDefined();
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/runs",
    expect.objectContaining({ body: JSON.stringify({ cap: 3 }) }),
  );
});

it("shows a failed run's error", async () => {
  mockApi({
    "GET /api/claims": queue,
    "GET /api/runs/current": run({
      status: "failed",
      todos: [],
      error: "The agent failed: provider down",
    }),
  });
  renderAt("/");
  expect((await screen.findByRole("alert")).textContent).toBe(
    "The agent failed: provider down",
  );
  expect(
    screen.getByText("The agent has not written its to-do list yet."),
  ).toBeDefined();
});

it("shows an error when the backend is down", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  renderAt("/");
  expect((await screen.findByRole("alert")).textContent).toContain("offline");
});
