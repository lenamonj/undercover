# Status

The claims pilot from `docs/PLAN.md` is built. The harness from `docs/PLAN_HARNESS.md` is in progress: phases 1 to 5 of 6 are done.

## Built

- `backend/`: FastAPI on SQLite. `backend/db.py` creates `backend/undercover.db` (or the file in `UNDERCOVER_DB`) and seeds it from `data/` the first time the backend starts.
  - Read: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `list_sections`, `read_section`, `get_instructions`, `list_handlers`, `list_steps`. `backend/documents.py` splits the policy wording and the claims manual into numbered sections.
  - Write: `record_decision`, `pay_claim`, `sign_off_claim`, `add_step`.
  - Runs: `start_run` with a cap starts the queue agent in a background task; `get_current_run`, `list_waiting_claims`, `write_todos`, `start_claim` (refused over the cap or for a claim that is not waiting), `finish_run` (refused while the run owes a retry or an untried claim within its cap) and `fail_run`.
  - One claim: `run_agent` starts the claim agent on one waiting claim in a background task. A claim's `running` flag is set from the start to the end of its agent's work.
  - Failures: `record_failure` sends a claim back to `waiting`, or to `needs_handler` on its second failure. `release_claim` marks a claim agent's work as over. At startup the backend records a failed attempt on any claim left `in_progress` and marks a run left going `interrupted`.
  - The sign-off rule: a payout over the $1,000 limit in `data/company.json` sets the claim to `awaiting_sign_off`, and `pay_claim` refuses it with 409 until a handler signs off, which makes the payment.
  - The instructions are in `backend/instructions/queue.md` and `backend/instructions/claim.md`, written from the policy wording and the claims manual.
- `agent/queue.py`: the queue agent, `work_run(run_id)`. A `create_agent` with four tools: `list_waiting_claims`, `write_todos`, `work_claim` (starts the claim in the run, then hands it to a fresh claim agent and returns its one-line report) and `finish_run`. A run that raises or ends without finishing is marked `failed`.
- `agent/main.py`: the claim agent, `run(claim_id, thread_id)`. LangChain's `create_agent` on OpenRouter with six tools that call the backend's API: `get_claim`, `get_policy`, `get_claim_history`, `list_sections`, `read_section`, `record_decision` and `pay_claim`. Each section read is recorded as a `read` step. It fetches its instructions from `get_instructions` and posts each tool call, tool result and reply as a step. A refused call comes back to the model as text. `work_claim(claim_id)` runs a fresh claim agent on a started claim, records a failure if it raises or ends without a decision, and returns a one-line report. Middleware retries provider errors and timed-out tool calls and stops an agent after 30 model calls; the model times out after 60 seconds. It reaches the backend at `UNDERCOVER_URL`, or `http://localhost:8000`.
- `dashboard/`: React, React Router and plain CSS in the brand's fonts and colors, light and dark. The queue with a count for each of the five states, a cap ("Claims to work", default 5) beside "Work the queue", and the current run's to-do list, status and summary, refreshed every second while the run is going. Each claim in full, with its policy, claim history, the agent's decision and reasons, the agent's steps (polled every second while it runs), "Run the agent", the sign-off form, the sections the agent read and its failed attempts. Both sets of instructions, read only.
- `e2e/`: Playwright tests against `e2e/server.py`, a backend on port 8001 with a fresh database and a scripted model, and a dashboard on port 5174.

`data/evals/` and `data/security/` are never loaded.

## Run

- `npm run dev`: the backend on port 8000 and the dashboard on http://localhost:5173
- `npm run reset`: delete the database and seed it again from `data/`. Run it after pulling a change to the database's tables.
- `npm run check`: every check. Tests never call a model.

The agent uses `deepseek/deepseek-v4.1-flash` with low reasoning effort, or the model in `MODEL_NAME`, with `OPENROUTER_API_KEY` from `.env`.

## Live runs (2026-11-18, `openai/gpt-6-luna`)

Not scored against `data/evals/`.

| Claim | Decision | Payout | Section | Notes |
|---|---|---|---|---|
| CLM-1001 | Approve | $420.00 | 3. Trip Delay | Paid |
| CLM-1003 | Approve | $3,750.00 | 7. Emergency Medical | $3,800.00 less the $50.00 deductible. The agent tried to pay, the backend refused, and the claim waits for sign-off |
| CLM-1013 | Decline | $0.00 | 3. Trip Delay | A 7 hour 5 minute delay is under the Economy plan's 12-hour waiting period |
