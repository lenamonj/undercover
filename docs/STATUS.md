# Status

The claims pilot from `docs/PLAN.md`, in progress. Phases 1 to 4 of 6 are done.

## Built

- `backend/`: FastAPI on SQLite. `backend/db.py` creates `backend/undercover.db` (or the file in `UNDERCOVER_DB`) and seeds it from `data/` the first time the backend starts. Read operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions`, `list_handlers`. Write operations: `record_decision`, `pay_claim` and `sign_off_claim`, and `add_step` and `list_steps` for the agent's steps. `run_agent` starts the agent on one waiting claim in a background task, and `work_queue` runs it on every waiting claim, one after another. A run that fails or ends without a decision puts the claim back to `waiting` with an error step. A payout over the $1,000 limit in `data/company.json` sets the claim to `awaiting_sign_off`, and `pay_claim` refuses it with 409 until a handler signs off, which makes the payment. The agent's instructions are in `backend/instructions.md`.
- `agent/`: the UnderCover Agent, `run(claim_id, thread_id)`. LangChain's `create_agent` with six tools that call the backend's API: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision` and `pay_claim`. It fetches its instructions from `get_instructions` and posts each tool call, tool result and reply as a step. A refused call comes back to the model as text.
- `dashboard/`: still the hello-world page.

`data/evals/` and `data/security/` are never loaded.

## Run

- `npm run dev`: the backend on port 8000 and the dashboard on port 5173
- `npm run reset`: delete the database and seed it again from `data/`
- `npm run check`: every check
