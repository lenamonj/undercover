# Plan for the pilot

The plan for building the claims pilot in `docs/SPEC.md`, on top of the hello-world skeleton. Six phases, each building on the last. Every criterion is a checkbox that gets ticked when it has been verified.

## What gets built

- **Backend**: SQLite seeded from `data/`, an API for the queue, claims, decisions, payments, sign-off, the agent's steps and its instructions, and an operation that starts the agent on a claim.
- **Agent**: the UnderCover Agent, which reads a claim through the backend's API, decides it, records its reasons and pays when it is allowed to.
- **Dashboard**: the queue, each claim in full, the agent's steps as it works, sign-off for payouts over $1,000, and the agent's instructions, read only.

## The main design choices

1. **The sign-off rule lives in the backend, not in the agent's instructions.** `pay_claim` refuses any amount over the limit until a handler has signed off. The spec says the system must block the payment "even if the agent tries to pay", and a prompt cannot guarantee that. The limit is read from `data/company.json`.
2. **Standard library `sqlite3`, no ORM.** Five small tables, a connection per request. Claims, policies and customers are stored as JSON documents with a few indexed columns, because the pilot only reads them whole. An ORM would add a layer with nothing to do.
3. **The agent reaches everything over HTTP.** Its tools call the backend's API, and it fetches its instructions from the API at the start of each run. Nothing in `agent/` reads `data/` or the database. That is the tech stack's rule, and it keeps `data/evals/` out of the agent's reach by construction: the backend never loads that folder, so no route can return it.
4. **The decision is a tool call, not parsed text.** The agent calls `record_decision` with the decision, the payout, the reason and the policy section. The backend validates it. A structured call is reliable where parsing a final message is not.
5. **Steps are posted by the agent and polled by the dashboard.** As the agent streams, each tool call and result is posted to the backend as a step. The dashboard polls once a second while a claim is in progress. Polling is far simpler than server-sent events and is fast enough for three handlers.
6. **The backend starts the agent in a background task.** "Run the agent" on the dashboard calls the backend, which calls `agent.main.run(claim_id, thread_id)` off the request thread. The run then talks back to the backend over HTTP like any other client.
7. **Tests never call a model.** Unit tests and Playwright tests use a scripted stub model. Playwright starts the backend from `e2e/server.py`, which swaps the stub in and uses a throwaway database, so no test code sits in the product.

### Claim states

| Status | Meaning | How a claim gets there |
|---|---|---|
| `waiting` | In the queue, untouched | Seeded, or an agent run failed |
| `in_progress` | The agent is working on it | `run_agent` |
| `awaiting_sign_off` | Approved for more than $1,000, not yet paid | `record_decision` |
| `decided` | Declined, referred, or approved (and paid once signed off) | `record_decision` or `sign_off_claim` |

### The API

Every operation has an `operation_id`, a one-line docstring and no optional inputs.

| Operation | Route | Notes |
|---|---|---|
| `health` | `GET /api/health` | Exists |
| `list_claims` | `GET /api/claims` | The queue: id, customer, type, amount claimed, status, decision, payout |
| `get_claim` | `GET /api/claims/{claim_id}` | The claim in full with its decision, payment and sign-off |
| `get_policy` | `GET /api/policies/{policy_id}` | The policy with its plan's limits and its add-ons |
| `get_claim_history` | `GET /api/customers/{customer_id}/claim-history` | Earlier claims only, no contact details |
| `get_policy_wording` | `GET /api/policy-wording` | `data/policy_wording.md` |
| `get_instructions` | `GET /api/instructions` | The agent's instructions |
| `list_handlers` | `GET /api/handlers` | For the sign-off picker |
| `record_decision` | `POST /api/claims/{claim_id}/decision` | `decision`, `payout`, `reason`, `policy_section` |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` | `amount`. Blocked over the limit without sign-off |
| `sign_off_claim` | `POST /api/claims/{claim_id}/sign-off` | `handler_id`. Records the sign-off and the payment |
| `add_step` | `POST /api/claims/{claim_id}/steps` | `kind`, `detail` |
| `list_steps` | `GET /api/claims/{claim_id}/steps` | In order |
| `run_agent` | `POST /api/claims/{claim_id}/run` | Starts the agent on one waiting claim |
| `work_queue` | `POST /api/queue/run` | Runs the agent on every waiting claim, one after another |

### Out of scope

As the spec says: the claims manual, sign-in, real payments and messages to customers. Also nothing from later briefs: no evaluation runner, no durable state, no middleware. `data/evals/` and `data/security/` are never loaded.

---

## Phase 1: The data and the read API

**Builds:** `backend/db.py` (schema, connection, seeding from `data/` when the database is empty), the read operations (`list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions`, `list_handlers`), and `backend/instructions.md` as a first draft. The database file is `backend/undercover.db`, or the path in `UNDERCOVER_DB`, and is added to `.gitignore`. `npm run reset` (a `uv run` command) deletes and reseeds it.

**Why first:** everything else reads from here. Seeding at startup means `npm run dev` works on a fresh clone with no setup step.

- [x] `uv run pytest -q backend` passes, with tests for seeding and every read operation, including a 404 for an unknown claim, policy and customer
- [x] `GET /api/claims` returns 25 claims, all with status `waiting`
- [x] `GET /api/claims/CLM-1001` returns the story, the three items, the documents and `amount_claimed` of 420.0
- [x] `GET /api/policies/POL-2001` returns the Premium plan's limits alongside the policy
- [x] `GET /api/customers/CUS-3001/claim-history` returns CLM-0412 and no email, phone or address
- [x] `GET /api/policy-wording` returns the text of `data/policy_wording.md`
- [x] A test asserts that CLM-1901 (the security claim) is not in the queue
- [x] Searching `backend/` and `agent/` for `evals` finds nothing
- [x] `/openapi.json` shows an `operationId` and a summary for every route, and no optional parameters
- [x] `backend/undercover.db` is ignored by git
- [x] Restarting the backend does not reseed or duplicate claims

## Phase 2: Decisions, payments and sign-off

**Builds:** `record_decision`, `pay_claim` and `sign_off_claim`, with the state changes in the table above.

Rules the backend enforces, each returning 409 with a plain message when broken (422 for an invalid payout, 404 for an unknown handler):

- A decision is recorded only on a claim that is `in_progress`.
- `decision` is `approve`, `decline` or `refer`. The payout is greater than zero for an approval and zero otherwise.
- A payment is made only on an approved claim, only once, and only for the decided payout.
- A payment over the limit is refused until a handler has signed off.
- A sign-off is accepted only on a claim that is `awaiting_sign_off`, from a handler who exists.

**Why now:** this is the pilot's one hard rule, so it gets built and tested on its own before any agent exists to test it.

- [x] `uv run pytest -q backend` passes, with a test for each rule above
- [x] Approving for $420.00 sets the claim to `decided`, and paying $420.00 then succeeds
- [x] Approving for $1,000.00 exactly does not need sign-off; $1,000.01 does
- [x] Approving for $1,500.00 sets the claim to `awaiting_sign_off`, and `pay_claim` for $1,500.00 returns 409 with no payment recorded
- [x] After `sign_off_claim` with `HND-01`, the claim is `decided`, the payment of $1,500.00 is recorded and the handler's name is on the claim
- [x] Paying twice, paying a declined claim and paying the wrong amount each return 409
- [x] `get_claim` shows the decision, reason, policy section, payment and sign-off

## Phase 3: The UnderCover Agent

**Builds:** the agent in `agent/main.py`, replacing the hello-world tool.

- Tools, each a thin call to the backend: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision`, `pay_claim`.
- `run(claim_id, thread_id)` fetches the instructions from the backend as the system prompt, streams the agent and posts each tool call, tool result and the final reply to `add_step`.
- `backend/instructions.md`, written out properly: read the claim, the policy, the history and the wording; decide from the wording alone; work out the payout from the plan's limits, waiting periods and deductible; record the decision with a reason of two or three sentences and the relevant section; pay only when approving; refer when the wording does not settle the claim.
- A refused payment comes back to the agent as a tool result saying the payment waits for a handler's sign-off, so the agent ends cleanly instead of failing.

**Why this shape:** six small tools keep each step visible on the dashboard and let a small model work one fact at a time. The instructions sit in the backend so the dashboard can show exactly what the agent was told.

- [x] `uv run pytest -q agent` passes with a stub model and the backend's test client in place of HTTP
- [x] A stubbed run that approves $420.00 leaves the claim `decided` and paid, with steps recorded in order
- [x] A stubbed run that approves $1,500.00 and then tries to pay leaves the claim `awaiting_sign_off` with no payment, and the refusal appears as a step
- [x] A stubbed run that declines records a payout of zero and makes no payment
- [x] The system prompt used in a run equals the text from `get_instructions`
- [x] `MODEL_NAME` still overrides the default model, and the default is `openai/gpt-6-luna` with low reasoning effort
- [x] Nothing in `agent/` opens a file under `data/` or imports `backend.db`

## Phase 4: Running the agent from the backend

**Builds:** `run_agent` and `work_queue`. `run_agent` sets the claim to `in_progress`, clears its earlier steps, makes a thread id and starts the agent in a background task. `work_queue` does the same for every waiting claim, one after another. If a run raises, or ends without a decision, the backend records a step saying so and returns the claim to `waiting`, so a claim is never stuck in progress.

**Why separate from Phase 3:** the agent is testable alone with a stub, and this phase adds only the wiring and the one failure case that matters.

- [x] `uv run pytest -q` passes at 80% coverage or more across `backend/` and `agent/`
- [x] `run_agent` on a waiting claim returns at once with status `in_progress`; on a claim in any other state it returns 409
- [x] With a stub model, a run started through `run_agent` ends with the claim `decided` and its steps listed by `list_steps`
- [x] A stubbed run that raises leaves the claim `waiting` with a step that carries the error
- [x] A stubbed run that ends without a decision leaves the claim `waiting` with a step saying so
- [x] `work_queue` with a stub model leaves no claim `waiting` or `in_progress`
- [x] `npm run check:python` passes: ruff, pyright and pytest

## Phase 5: The dashboard

**Builds:** three pages with React Router and plain CSS, following `docs/BRAND.md`.

- **Queue**: every claim with its customer, type, amount claimed, status and decision. A count for each of the four states. "Work the queue" runs every waiting claim.
- **Claim**: the story, items, documents, policy and claim history. The agent's decision, payout, reason and policy section. The steps, polled once a second while the claim is in progress. "Run the agent" on a waiting claim. On a claim awaiting sign-off, a handler picker and "Sign off".
- **Instructions**: the agent's instructions, read only.

Brand: Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts; the palette as CSS variables with light and dark surfaces from `prefers-color-scheme`; Sea Green, Marigold, Coral and Cerulean for the four states; money formatted as $1,250.00; rounded panels with no outline.

**Why plain CSS and polling:** three pages do not justify a component library or a state library. Typed `fetch` helpers in one `api.ts` are enough.

- [x] `npm run check:ts` passes: Prettier, ESLint, `tsc` in strict mode with no `any`, and vitest at 80% coverage or more
- [x] Vitest covers the queue, the claim page in each of the four states, the sign-off form, the instructions page and money formatting, with `fetch` mocked
- [x] In the browser (Playwright MCP): the queue lists 25 claims and the four counts add up to 25
- [x] In the browser: opening CLM-1001 shows the story, three items, the documents, the Premium policy and the earlier claim CLM-0412
- [x] In the browser: the instructions page shows the instructions and has no way to edit them
- [x] In the browser: fonts and colors match `docs/BRAND.md` in light and dark mode, with no borders on one edge and no gradients
- [x] Screenshots of the three pages are checked for layout at 1280px and 390px wide

## Phase 6: End to end, a live run and the documents

**Builds:** `e2e/server.py`, which serves the backend with a scripted stub model and a throwaway database, and Playwright tests for the full flows. Then one live run with the real model, and the documents brought up to date.

**Why last:** the end-to-end tests prove the three parts work together, and the live run is the first time the instructions meet a real model, so there is room here to adjust the wording of the instructions.

- [ ] Playwright: running the agent on a claim shows its steps appearing, then the decision, reason and policy section, and the queue shows the claim as decided
- [ ] Playwright: a stubbed approval over $1,000 shows the claim as waiting for sign-off with the blocked payment in its steps; after a handler signs off, it shows as decided and paid with the handler's name
- [ ] Playwright: "Work the queue" leaves no claim waiting
- [ ] Playwright: the instructions page shows the instructions
- [ ] Live, with `OPENROUTER_API_KEY` set: running the agent on CLM-1001 from the dashboard ends with a decision, a payout, a reason of two or three sentences and a policy section, and every step visible. The model's answer is recorded in `docs/STATUS.md`, not checked against `data/evals/`
- [ ] Live: one claim with more than $1,000 claimed is run, and if the agent approves over the limit, the payment is blocked until sign-off
- [ ] `npm run check` passes in full, and the output is reported
- [ ] `docs/STATUS.md` says what is built and how to run, reset and test it, and `README.md` stays short
- [ ] Every phase is committed, nothing is pushed
