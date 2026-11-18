import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockApi, queueItem, renderAt } from "./testing";

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
];

it("lists the queue with counts by status", async () => {
  mockApi({ "GET /api/claims": queue });
  renderAt("/");
  expect(await screen.findByText("CLM-1001")).toBeDefined();
  expect(screen.getByText("Tom Reyes")).toBeDefined();
  expect(screen.getByText("$1,150.00")).toBeDefined();
  expect(screen.getByText("Approved")).toBeDefined();
  const counts = screen.getByRole("list", { name: "Claims by status" });
  expect(within(counts).getAllByText("1")).toHaveLength(2);
  expect(within(counts).getAllByText("0")).toHaveLength(2);
});

it("works the queue and polls while claims are in progress", async () => {
  let polled = 0;
  const fetchMock = mockApi({
    get "GET /api/claims"() {
      polled += 1;
      return polled === 1
        ? queue
        : [
            polled === 2
              ? queueItem({ status: "in_progress", running: true })
              : queueItem({ status: "decided" }),
          ];
    },
    "POST /api/queue/run": { queued: 1 },
  });
  renderAt("/");
  fireEvent.click(
    await screen.findByRole("button", { name: "Work the queue" }),
  );
  await vi.waitFor(() => {
    expect(screen.getAllByText("In progress")).toHaveLength(2);
  });
  expect(
    await screen.findByRole(
      "button",
      { name: "Work the queue" },
      { timeout: 2500 },
    ),
  ).toHaveProperty("disabled", true);
  expect(fetchMock).toHaveBeenCalledWith("/api/queue/run", expect.anything());
});

it("shows an error when the backend is down", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  renderAt("/");
  expect((await screen.findByRole("alert")).textContent).toContain("offline");
});
