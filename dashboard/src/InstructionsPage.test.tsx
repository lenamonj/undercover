import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockApi, renderAt } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the agent's instructions read only", async () => {
  mockApi({
    "GET /api/instructions": { instructions: "You are the UnderCover Agent." },
  });
  renderAt("/instructions");
  expect(
    await screen.findByText("You are the UnderCover Agent."),
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
    "GET /api/instructions": { instructions: "Decide claims." },
  });
  renderAt("/");
  fireEvent.click(
    await screen.findByRole("link", { name: "Agent instructions" }),
  );
  expect(await screen.findByText("Decide claims.")).toBeDefined();
});
