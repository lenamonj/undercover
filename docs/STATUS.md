# Status

The claims pilot from `docs/PLAN.md` is built. All six phases are done.

## Built

- `backend/`: FastAPI on SQLite. `backend/db.py` creates `backend/undercover.db` (or the file in `UNDERCOVER_DB`) and seeds it from `data/` the first time the backend starts.
  - Read: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions`, `list_handlers`, `list_steps`.
  - Write: `record_decision`, `pay_claim`, `sign_off_claim`, `add_step`.
  - Runs: `run_agent` starts the agent on one waiting claim in a background task, and `work_queue` runs it on every waiting claim, one after another. A claim's `running` flag is set from the start (or queueing) to the end of its run. A run that fails or ends without a decision puts the claim back to `waiting` with an error step.
  - The sign-off rule: a payout over the $1,000 limit in `data/company.json` sets the claim to `awaiting_sign_off`, and `pay_claim` refuses it with 409 until a handler signs off, which makes the payment.
  - The agent's instructions are in `backend/instructions.md`.
- `agent/`: the UnderCover Agent, `run(claim_id, thread_id)`. LangChain's `create_agent` on OpenRouter with six tools that call the backend's API: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision` and `pay_claim`. It fetches its instructions from `get_instructions` and posts each tool call, tool result and reply as a step. A refused call comes back to the model as text. It reaches the backend at `UNDERCOVER_URL`, or `http://localhost:8000`.
- `dashboard/`: React, React Router and plain CSS in the brand's fonts and colors, light and dark. The queue with a count for each state and "Work the queue". Each claim in full, with its policy, claim history, the agent's decision and reasons, the agent's steps (polled every second while it runs), "Run the agent" and the sign-off form. The agent's instructions, read only.
- `e2e/`: Playwright tests against `e2e/server.py`, a backend on port 8001 with a fresh database and a scripted model, and a dashboard on port 5174.

`data/evals/` and `data/security/` are never loaded.

## Run

- `npm run dev`: the backend on port 8000 and the dashboard on http://localhost:5173
- `npm run reset`: delete the database and seed it again from `data/`. Run it after pulling a change to the database's tables.
- `npm run check`: every check. Tests never call a model.

The agent uses `openai/gpt-6-luna` with low reasoning effort, or the model in `MODEL_NAME`, with `OPENROUTER_API_KEY` from `.env`.

## Live runs (2026-11-18, `openai/gpt-6-luna`)

Not scored against `data/evals/`.

| Claim | Decision | Payout | Section | Notes |
|---|---|---|---|---|
| CLM-1001 | Approve | $420.00 | 3. Trip Delay | Paid |
| CLM-1003 | Approve | $3,750.00 | 7. Emergency Medical | $3,800.00 less the $50.00 deductible. The agent tried to pay, the backend refused, and the claim waits for sign-off |
| CLM-1013 | Decline | $0.00 | 3. Trip Delay | A 7 hour 5 minute delay is under the Economy plan's 12-hour waiting period |
