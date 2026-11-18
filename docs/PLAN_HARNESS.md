# Plan for the harness

The plan for `docs/HARNESS.md`, on top of the pilot in `docs/STATUS.md`. Six phases, each building on the last. Every criterion is a checkbox that gets ticked when it has been verified.

## What changes

Today the backend feeds the agent one claim at a time, the agent is handed the whole policy wording, and our code decides what happens after a failure. After this build:

- **A queue agent** is started once per run. It reads the waiting claims, writes a to-do list, hands each claim to a claim agent, retries what failed, checks nothing was missed and finishes with a summary.
- **A claim agent** is created fresh for each claim. It looks up the sections of the wording and the manual it needs, decides, pays when allowed, and the queue agent gets back one line.
- **The backend** keeps the run, its cap and its to-do list, counts failed attempts, and refuses anything the rules forbid: going over the cap, deciding or paying twice, finishing with claims missed.

## The main design choices

1. **The rules live in the backend, the organizing lives in the agent.** The agent chooses the order, writes the to-do list and decides when to retry. The backend enforces the cap, the two-attempt limit, the missed-claim check and the existing rules on decisions and payments. Same reasoning as the pilot's sign-off: an instruction is guidance, a refused API call is a guarantee.
2. **Our own `write_todos` tool, not `TodoListMiddleware`.** LangChain's middleware keeps the list inside the agent's state with the states pending, in progress and completed. We need the list in the backend so the dashboard can show it, and a fourth state, left for a handler. A tool that saves the list through the API does both in a few lines.
3. **The subagent is a tool.** The queue agent's `work_claim` tool builds a new claim agent with an empty conversation, runs it and returns one line. Each claim starts clean and the queue agent's context grows by a line per claim, not by every document read.
4. **Documents by section.** The backend splits the wording and the manual on their `##` headings. The claim agent gets a table of contents (`list_sections`) and reads only what it needs (`read_section`). With 26 sections in all, a table of contents is enough to find things, so there is no search index. Each section read is recorded as a `read` step, which the claim page lists.
5. **LangChain middleware for retries.** `ModelRetryMiddleware` retries provider errors with backoff, `ToolRetryMiddleware` retries a tool call whose HTTP request timed out, and `ModelCallLimitMiddleware` stops a claim agent that loops. All three ship with `langchain` 1.4, so nothing new is installed.
6. **A failure is recorded, never left hanging.** A claim agent that raises, or ends without a decision, is recorded as a failed attempt: the claim goes back to `waiting`, or to the new status `needs_handler` on the second failure. When the backend starts, any claim still `in_progress` from an interrupted run is recorded as a failed attempt the same way.

### Claim states

The pilot's four, plus one:

| Status | Meaning |
|---|---|
| `waiting` | In the queue, never tried or tried once and failed |
| `in_progress` | A claim agent is working on it |
| `awaiting_sign_off` | Approved for more than $1,000, not yet paid |
| `decided` | Approved, declined or referred by the agent |
| `needs_handler` | The agent failed on it twice; a handler takes it from here |

### To-do items

Each item has `content` and a `status` of `pending`, `in_progress`, `done` or `left_for_handler`. The queue agent writes the whole list each time, as `TodoListMiddleware` does.

### New and changed API operations

Every operation keeps an `operation_id`, a one-line docstring and no optional inputs.

| Operation | Route | Notes |
|---|---|---|
| `list_sections` | `GET /api/documents/sections` | Number and title of every section of `policy_wording` and `claims_manual` |
| `read_section` | `GET /api/documents/{document}/sections/{number}` | One section's text |
| `start_run` | `POST /api/runs` | `cap`. Starts the queue agent in the background; 409 if a run is already going |
| `get_current_run` | `GET /api/runs/current` | The latest run: status, cap, claims started, to-do list, summary |
| `list_waiting_claims` | `GET /api/claims/waiting` | Id, type, amount and attempts of each waiting claim |
| `write_todos` | `PUT /api/runs/{run_id}/todos` | The whole list |
| `start_claim` | `POST /api/runs/{run_id}/claims/{claim_id}/start` | 409 over the cap or if the claim is not waiting |
| `record_failure` | `POST /api/claims/{claim_id}/failure` | `error`. Back to `waiting`, or `needs_handler` on the second failure |
| `release_claim` | `POST /api/claims/{claim_id}/release` | Marks a claim agent's work as over, so the dashboard stops refreshing it. Added in Phase 3: the wrapper reaches the backend only over HTTP |
| `finish_run` | `POST /api/runs/{run_id}/finish` | `summary`. 409 listing the claims missed, if any waiting claim was never tried and the cap is not reached |
| `fail_run` | `POST /api/runs/{run_id}/failure` | `error`. Marks a run `failed` when the queue agent raises or stops without finishing. Added in Phase 4 |
| `get_instructions` | `GET /api/instructions` | Now returns `queue` and `claim` |
| `run_agent` | `POST /api/claims/{claim_id}/run` | Unchanged for the dashboard: one named claim, through the same claim agent and failure handling |
| `work_queue` | `POST /api/queue/run` | Removed; `start_run` replaces it |
| `get_policy_wording` | `GET /api/policy-wording` | Removed; the agent reads sections instead |

### Out of scope

Anything from later briefs: durable state, evaluations, parallel claim agents, an improver, sign-in. `data/evals/` is never opened.

---

## Phase 1: Documents by section, and the new model

**Builds:** `backend/documents.py`, which splits `data/policy_wording.md` and `data/claims_manual.md` on `##` headings. `list_sections` and `read_section` replace `get_policy_wording`. The claim agent's `get_policy_wording` tool is replaced by `list_sections` and `read_section`, and a `read_section` result is posted as a `read` step such as `Claims manual 9. Repeat claims`. The default model becomes `deepseek/deepseek-v4.1-flash` with low reasoning effort, and `MODEL_NAME` still overrides it.

**Why first:** it is self-contained, and every later phase's claim agent uses it.

- [x] `uv run pytest -q` passes, with tests for splitting both documents, `list_sections`, `read_section` and a 404 for an unknown document or section
- [x] `GET /api/documents/sections` lists 12 sections of the policy wording and 14 of the claims manual
- [x] `GET /api/documents/claims_manual/sections/9` returns the section on repeat claims, and nothing from section 10
- [x] A stubbed claim run that reads a section records a `read` step naming the document and section
- [x] `/api/policy-wording` is gone, and no tool hands the agent a whole document
- [x] `main.model()` defaults to `deepseek/deepseek-v4.1-flash` with low reasoning effort, and `MODEL_NAME` overrides it
- [x] `npm run check:python` passes

## Phase 2: Runs, the cap and the to-do list in the backend

**Builds:** a `runs` table (id, cap, status, claims started, to-do list, summary, times) and the operations `start_run` (without the agent yet), `get_current_run`, `list_waiting_claims`, `write_todos`, `start_claim` and `finish_run`.

**Why now:** the rules the queue agent works under are built and tested on their own, before an agent exists to test them, as the sign-off rule was in the pilot.

- [x] `uv run pytest -q` passes, with tests for each rule below
- [x] With a cap of 5, `start_claim` succeeds for five different claims and returns 409 for a sixth; retrying a claim already started in the run does not count against the cap
- [x] `start_claim` on a claim that is not `waiting` returns 409, so a decided claim is never decided again
- [x] `write_todos` stores the list, rejects an unknown status with 422, and `get_current_run` returns it in order
- [x] `finish_run` returns 409 naming the missed claims while a waiting claim was never tried and the cap is not reached; it succeeds when the cap is reached or no such claim is left, and stores the summary
- [x] `start_run` returns 409 while another run is going
- [x] `list_waiting_claims` lists only `waiting` claims, with their attempts

## Phase 3: Failures put right

**Builds:** an `attempts` column and the `needs_handler` status; `record_failure`; recovery at startup for claims left `in_progress` and runs left going; `ModelRetryMiddleware`, `ToolRetryMiddleware` and `ModelCallLimitMiddleware` on the claim agent; a 60-second model timeout. The claim agent's run is wrapped in one function, `work_claim(claim_id, run_id)`, that records any exception or a run ending without a decision as a failure and returns a one-line report.

**Why before the queue agent:** the queue agent's `work_claim` tool is this function, so it needs to be right first.

- [x] `uv run pytest -q` passes at 80% coverage or more
- [x] A stubbed claim agent that raises: the claim goes back to `waiting` with `attempts` 1, an error step, and the one-line report says so
- [x] A second failure on the same claim sets it to `needs_handler`, and `start_claim` then refuses it
- [x] A stubbed claim agent that ends without a decision is recorded as a failure
- [x] A model error on the first call and success on the second: the claim is decided, with no failure recorded (`ModelRetryMiddleware`)
- [x] A claim agent that keeps calling tools stops at the model call limit and is recorded as a failure
- [x] Starting the backend with a claim `in_progress` records a failed attempt on it and marks the old run `interrupted`
- [x] A successful report reads like `CLM-1001: approve, $420.00, paid`, and an over-limit one says the payment waits for sign-off

## Phase 4: The queue agent

**Builds:** `agent/queue.py` with `run_queue(run_id, thread_id)`, a `create_agent` with the tools `list_waiting_claims`, `write_todos`, `work_claim` and `finish_run`, plus `ModelRetryMiddleware`. `start_run` starts it in a background task; if the queue agent itself fails, the run is marked `failed` with the error. The instructions move to `backend/instructions/queue.md` and `backend/instructions/claim.md`, written from the policy wording and the manual. The claim instructions now cover the manual: repeat claims, meals without receipts, wild animals, missing documents, story and documents that disagree, and when to refer. `run_agent` on one named claim calls `work_claim` directly.

**Why the tools look like this:** four tools are the whole job of the queue agent, and each is a thin call to the backend except `work_claim`, which is Phase 3's function.

- [x] `uv run pytest -q` passes, with a stub model for the queue agent and another for the claim agents
- [x] A stubbed run capped at 2 works two claims, writes and updates the to-do list, finishes with a summary, and leaves 23 claims `waiting`
- [x] A stubbed run where one claim agent fails: the run carries on, the queue agent retries the claim and it is decided
- [x] A stubbed run where a claim fails twice: it ends `needs_handler` and its to-do item `left_for_handler`, and the run finishes
- [x] A stubbed queue agent that tries to finish early gets the 409 listing the missed claims, works them, then finishes
- [x] Every step of every claim in a run is recorded on that claim, and the queue agent's context holds one line per claim
- [x] `get_instructions` returns both sets of instructions, and searching `backend/` and `agent/` for `evals` finds nothing
- [x] `npm run check:python` passes

## Phase 5: The dashboard

**Builds:**
- **Queue page:** a number input for the cap (default 5) next to "Work the queue", the current run's to-do list with each item's status, the run's status and summary, polled every second while the run is going, and a count and color for `needs_handler` (Raspberry).
- **Claim page:** a "Sections read" panel listing the `read` steps, and the attempts count when it is above zero.
- **Instructions page:** the queue agent's and the claim agent's instructions, each under its own heading, still read only.

- [x] `npm run check:ts` passes, with vitest at 80% coverage or more
- [x] Vitest covers the cap input, the to-do list in all four states, the run summary, the `needs_handler` status, "Sections read" and both sets of instructions
- [x] In the browser (Playwright MCP): the to-do list and counts render at 1280px and 390px wide, in light and dark mode, with no page-wide horizontal scroll

## Phase 6: End to end, a live capped run and the documents

**Builds:** the scripted model in `e2e/server.py` grows a queue-agent script beside the claim-agent script, and Playwright tests cover a capped run. Then one live run on the default model, capped at five, after a reseed. `docs/SPEC.md` (the manual is no longer "Not for now"; the new state), `docs/TECH_STACK.md` (two entry points, the default model, the middleware) and `docs/STATUS.md` are brought up to date.

- [x] Playwright: a run capped at 3 fills in the to-do list, ticks items off, shows the summary, and leaves 22 claims waiting
- [x] Playwright: a claim worked in the run shows its steps, its "Sections read" and its decision
- [x] Playwright: the instructions page shows both sets of instructions
- [x] Live, after `npm run reset`, a run capped at five on `deepseek/deepseek-v4.1-flash` works five claims on its own, with the to-do list filling in and being ticked off on the dashboard, each claim's steps and sections read visible, and the other 20 claims still waiting. The results go in `docs/STATUS.md`, not checked against `data/evals/`
- [x] `npm run check` passes in full, and the output is reported
- [x] `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the product as it now is
- [x] Every phase is committed, nothing is pushed
