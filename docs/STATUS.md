# Status

The claims pilot from `docs/PLAN.md`, in progress. Phases 1 and 2 of 6 are done.

## Built

- `backend/`: FastAPI on SQLite. `backend/db.py` creates `backend/undercover.db` (or the file in `UNDERCOVER_DB`) and seeds it from `data/` the first time the backend starts. Read operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions`, `list_handlers`. Write operations: `record_decision`, `pay_claim` and `sign_off_claim`. A payout over the $1,000 limit in `data/company.json` sets the claim to `awaiting_sign_off`, and `pay_claim` refuses it with 409 until a handler signs off, which makes the payment. The agent's instructions are in `backend/instructions.md`.
- `agent/`: still the hello-world agent.
- `dashboard/`: still the hello-world page.

`data/evals/` and `data/security/` are never loaded.

## Run

- `npm run dev`: the backend on port 8000 and the dashboard on port 5173
- `npm run reset`: delete the database and seed it again from `data/`
- `npm run check`: every check
