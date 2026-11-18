import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";
import type {
  Claim,
  ClaimHistory,
  Handler,
  Policy,
  QueueItem,
  Run,
  Step,
} from "./api";
import { App } from "./App";

// Use a getter for a route whose reply changes between calls.
export type Routes = Record<string, object | null>;

export function mockApi(...routeSets: Routes[]) {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url}`;
    const routes = routeSets.find((set) => key in set);
    if (!routes) {
      return Promise.resolve(new Response(`No route ${key}`, { status: 404 }));
    }
    return Promise.resolve(Response.json(routes[key]));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

export const queueItem = (overrides: Partial<QueueItem> = {}): QueueItem => ({
  claim_id: "CLM-1001",
  customer_name: "Maya Patel",
  claim_type: "trip_delay",
  summary: "Flight canceled",
  submitted_on: "2026-06-24",
  amount_claimed: 420,
  status: "waiting",
  decision: null,
  payout: null,
  running: false,
  ...overrides,
});

export const claim = (overrides: Partial<Claim> = {}): Claim => ({
  claim_id: "CLM-1001",
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  claim_type: "trip_delay",
  submitted_on: "2026-06-24",
  incident_date: "2026-06-18",
  incident_location: "Rome, Italy",
  summary: "Flight canceled",
  story: "My flight home from Rome was canceled.",
  items: [
    { description: "Airport hotel", category: "accommodation", amount: 245 },
  ],
  amount_claimed: 245,
  documents: [
    { name: "Hotel receipt", type: "receipt", content: "Total paid: $245.00." },
  ],
  status: "waiting",
  decision: null,
  payout: null,
  running: false,
  attempts: 0,
  reason: null,
  policy_section: null,
  paid_amount: null,
  signed_off_by: null,
  ...overrides,
});

export const policy: Policy = {
  policy_id: "POL-2001",
  plan: "premium",
  purchased_on: "2026-04-22",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
  status: "active",
  plan_details: { name: "UnderCover Premium", deductible: 50 },
  add_on_details: [],
};

export const history: ClaimHistory = {
  customer_id: "CUS-3001",
  name: "Maya Patel",
  customer_since: "2023-04-11",
  previous_claims: [
    {
      claim_id: "CLM-0412",
      filed_on: "2024-08-19",
      claim_type: "baggage_delay",
      summary: "Checked bag arrived 30 hours late",
      outcome: "approved",
      amount_paid: 140,
    },
  ],
};

export const handlers: Handler[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
  },
];

export const step = (overrides: Partial<Step> = {}): Step => ({
  step_id: 1,
  kind: "tool_call",
  detail: 'get_claim {"claim_id": "CLM-1001"}',
  created_at: "2026-11-18T10:00:00Z",
  ...overrides,
});

export const run = (overrides: Partial<Run> = {}): Run => ({
  run_id: 1,
  cap: 5,
  status: "running",
  claims_started: 2,
  todos: [
    { content: "Work CLM-1001", status: "done" },
    { content: "Work CLM-1002", status: "in_progress" },
    { content: "Work CLM-1003", status: "pending" },
    { content: "Work CLM-1004", status: "left_for_handler" },
  ],
  summary: null,
  error: null,
  started_at: "2026-11-18T10:00:00Z",
  finished_at: null,
  ...overrides,
});

export function claimRoutes(
  current: Claim | (() => Claim),
  steps: Step[] = [],
) {
  return {
    get "GET /api/claims/CLM-1001"() {
      return typeof current === "function" ? current() : current;
    },
    "GET /api/claims/CLM-1001/steps": steps,
    "GET /api/policies/POL-2001": policy,
    "GET /api/customers/CUS-3001/claim-history": history,
    "GET /api/handlers": handlers,
  };
}
