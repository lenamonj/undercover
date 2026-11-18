export type Status =
  "waiting" | "in_progress" | "awaiting_sign_off" | "decided" | "needs_handler";
export type Verdict = "approve" | "decline" | "refer";

export interface QueueItem {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  submitted_on: string;
  amount_claimed: number;
  status: Status;
  decision: Verdict | null;
  payout: number | null;
  running: boolean;
}

export interface ClaimItem {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: ClaimItem[];
  amount_claimed: number;
  documents: ClaimDocument[];
  status: Status;
  decision: Verdict | null;
  payout: number | null;
  running: boolean;
  attempts: number;
  reason: string | null;
  policy_section: string | null;
  paid_amount: number | null;
  signed_off_by: string | null;
}

export interface Policy {
  policy_id: string;
  plan: string;
  purchased_on: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  status: string;
  plan_details: { name: string; deductible: number };
  add_on_details: { add_on: string; name: string }[];
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface ClaimHistory {
  customer_id: string;
  name: string;
  customer_since: string;
  previous_claims: PreviousClaim[];
}

export interface Step {
  step_id: number;
  kind: "tool_call" | "tool_result" | "read" | "reply" | "error";
  detail: string;
  created_at: string;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
}

export interface Todo {
  content: string;
  status: "pending" | "in_progress" | "done" | "left_for_handler";
}

export interface Run {
  run_id: number;
  cap: number;
  status: "running" | "finished" | "failed" | "interrupted";
  claims_started: number;
  todos: Todo[];
  summary: string | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface Instructions {
  queue: string;
  claim: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new Error(`${String(response.status)}: ${await response.text()}`);
  }
  return (await response.json()) as T;
}

function post<T>(path: string, body?: object): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}

export const api = {
  listClaims: () => request<QueueItem[]>("/api/claims"),
  getClaim: (id: string) => request<Claim>(`/api/claims/${id}`),
  listSteps: (id: string) => request<Step[]>(`/api/claims/${id}/steps`),
  getPolicy: (id: string) => request<Policy>(`/api/policies/${id}`),
  getClaimHistory: (id: string) =>
    request<ClaimHistory>(`/api/customers/${id}/claim-history`),
  listHandlers: () => request<Handler[]>("/api/handlers"),
  getInstructions: () => request<Instructions>("/api/instructions"),
  getCurrentRun: () => request<Run | null>("/api/runs/current"),
  startRun: (cap: number) => post<Run>("/api/runs", { cap }),
  runAgent: (id: string) => post<unknown>(`/api/claims/${id}/run`),
  signOff: (id: string, handlerId: string) =>
    post<Claim>(`/api/claims/${id}/sign-off`, { handler_id: handlerId }),
};
