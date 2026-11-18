import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockApi, renderAt } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the agent's instructions read only", async () => {
  mockApi({
    "GET /api/instructions": {
      queue: "You run the queue.",
      claim: "You decide one claim.",
    },
  });
  renderAt("/instructions");
  expect(await screen.findByText("You run the queue.")).toBeDefined();
  expect(screen.getByText("You decide one claim.")).toBeDefined();
  expect(
    screen.getByRole("heading", { name: "Running the queue" }),
  ).toBeDefined();
  expect(
    screen.getByRole("heading", { name: "Working a claim" }),
  ).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByRole("button")).toBeNull();
});

it("shows an error when the instructions cannot load", async () => {
  mockApi({});
  renderAt("/instructions");
  expect(await screen.findByRole("alert")).toBeDefined();
});

it("navigates between the pages", async () => {
  mockApi({
    "GET /api/claims": [],
    "GET /api/runs/current": null,
    "GET /api/instructions": {
      queue: "Run the queue.",
      claim: "Decide claims.",
    },
  });
  renderAt("/");
  fireEvent.click(
    await screen.findByRole("link", { name: "Agent instructions" }),
  );
  expect(await screen.findByText("Decide claims.")).toBeDefined();
});
