# Status

The pilot (`docs/PLAN.md`) and the harness (`docs/PLAN_HARNESS.md`) are built.

## Built

- `backend/`: FastAPI on SQLite. `backend/db.py` creates `backend/undercover.db` (or the file in `UNDERCOVER_DB`) and seeds it from `data/` the first time the backend starts.
  - Claims: `list_claims`, `list_waiting_claims`, `get_claim`, `get_policy`, `get_claim_history`, `list_handlers`.
  - Documents: `backend/documents.py` splits the policy wording and the claims manual on their `##` headings. `list_sections` gives the table of contents and `read_section` one section.
  - Decisions: `record_decision`, `pay_claim`, `sign_off_claim`. A payout over the $1,000 limit in `data/company.json` sets the claim to `awaiting_sign_off`, and `pay_claim` refuses it with 409 until a handler signs off, which makes the payment.
  - Runs: `start_run` with a cap starts the queue agent in a background task. `get_current_run`, `write_todos`, `start_claim` (refused over the cap or for a claim that is not waiting, so nothing is decided twice), `finish_run` (refused while the run owes a retry or an untried claim within its cap) and `fail_run`.
  - One claim: `run_agent` starts the claim agent on one waiting claim.
  - Failures: `record_failure` sends a claim back to `waiting`, or to `needs_handler` on its second failure. `release_claim` marks a claim agent's work as over. At startup the backend records a failed attempt on any claim left `in_progress` and marks a run left going `interrupted`.
  - Steps: `add_step` and `list_steps`. Step kinds are `tool_call`, `tool_result`, `read`, `reply` and `error`.
  - Instructions: `backend/instructions/queue.md` and `backend/instructions/claim.md`, written from the policy wording and the claims manual, served by `get_instructions`.
- `agent/queue.py`: the queue agent, `work_run(run_id)`. A `create_agent` with four tools: `list_waiting_claims`, `write_todos`, `work_claim` (starts the claim in the run, hands it to a fresh claim agent and returns its one-line report) and `finish_run`. A run that raises or ends without finishing is marked `failed`.
- `agent/main.py`: the claim agent, `run(claim_id, thread_id)`, with seven tools: `get_claim`, `get_policy`, `get_claim_history`, `list_sections`, `read_section`, `record_decision` and `pay_claim`. Each tool call, result, section read and reply is posted as a step on the claim. `work_claim(claim_id)` wraps a run: a raise or a run without a decision is recorded as a failure, and it returns a one-line report. Middleware retries provider errors and timed-out tool calls, and stops a claim agent after 30 model calls (the queue agent after 200). The model times out after 60 seconds.
- `dashboard/`: React, React Router and plain CSS in the brand's fonts and colors, light and dark. The queue with a count for each of the five states, a cap ("Claims to work", default 5) beside "Work the queue", and the current run's to-do list, status and summary, refreshed every second while the run is going. Each claim in full, with its policy, claim history, the agent's decision and reasons, the sections it read, its failed attempts, its steps, "Run the agent" and the sign-off form. Both sets of instructions, read only.
- `e2e/`: Playwright tests against `e2e/server.py`, a backend on port 8001 with a fresh database and a scripted model that plays both agents, and a dashboard on port 5174.

`data/evals/` and `data/security/` are never loaded. Tests remove `OPENROUTER_API_KEY`, so no test can reach a model.

## Run

- `npm run dev`: the backend on port 8000 and the dashboard on http://localhost:5173
- `npm run reset`: delete the database and seed it again from `data/`. Run it after pulling a change to the database's tables, and before any live run.
- `npm run check`: every check.

The agents use `deepseek/deepseek-v4.1-flash` with low reasoning effort, or the model in `MODEL_NAME`, with `OPENROUTER_API_KEY` from `.env`. For a trial, keep "Claims to work" at 5.

## Live runs

Not scored against `data/evals/`.

**2026-11-18, harness, `deepseek/deepseek-v4.1-flash`, freshly seeded, capped at 5.** The queue agent wrote its to-do list, worked CLM-1001 to CLM-1005 in under a minute and finished with a summary. Each claim was decided on the first attempt after reading 7 to 9 sections. The other 20 claims stayed waiting.

| Claim | Decision | Payout | Section | Notes |
|---|---|---|---|---|
| CLM-1001 | Approve | $420.00 | 3. Trip Delay | Paid |
| CLM-1002 | Approve | $580.00 | 5. Baggage and Personal Effects | Per-item limit, the carrier's $400.00 settlement and the $50.00 deductible taken off. Paid |
| CLM-1003 | Approve | $3,750.00 | 7. Emergency Medical | $50.00 deductible taken off. Waits for sign-off |
| CLM-1004 | Approve | $186.00 | 4. Baggage Delay | Paid |
| CLM-1005 | Approve | $243.00 | 6. Passport and Travel Documents | A giraffe; the manual's wild-animal note applied. Paid |

**2026-11-18, pilot, `openai/gpt-6-luna`, one claim at a time.** CLM-1001 approved for $420.00 and paid; CLM-1003 approved for $3,750.00, waiting for sign-off; CLM-1013 declined, a 7 hour 5 minute delay being under the Economy plan's 12-hour waiting period.
