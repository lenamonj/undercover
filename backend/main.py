"""The UnderCover backend."""

import json
import sqlite3
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal, get_args

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent import main as undercover_agent
from backend import db, documents

INSTRUCTIONS = Path(__file__).parent / "instructions.md"


class Decision(BaseModel):
    decision: Literal["approve", "decline", "refer"]
    payout: float = Field(ge=0, description="US dollars; zero unless approving")
    reason: str = Field(min_length=1, description="Two or three sentences")
    policy_section: str = Field(min_length=1, description="Such as '3. Trip Delay'")


class Payment(BaseModel):
    amount: float = Field(gt=0, description="US dollars")


class SignOff(BaseModel):
    handler_id: str


class Step(BaseModel):
    kind: Literal["tool_call", "tool_result", "read", "reply", "error"]
    detail: str


def approval_limit() -> float:
    """Return the payout above which a handler must sign off."""
    return db.load("company.json")["payout_approval_limit"]


def conflict(message: str) -> HTTPException:
    return HTTPException(409, message)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    db.init_db()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


def claim_row(conn: sqlite3.Connection, claim_id: str) -> sqlite3.Row:
    """Return one claim's row, or raise 404."""
    row = conn.execute(
        "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No claim {claim_id}")
    return row


def document(conn: sqlite3.Connection, table: str, key: str, value: str) -> Any:
    """Return one stored JSON document, or raise 404."""
    row = conn.execute(
        f"SELECT data FROM {table} WHERE {key} = ?",  # noqa: S608
        (value,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No {key.removesuffix('_id')} {value}")
    return json.loads(row["data"])


def handler_name(conn: sqlite3.Connection, handler_id: str | None) -> str | None:
    """Return a handler's name, or None when there is no handler."""
    if handler_id is None:
        return None
    return document(conn, "handlers", "handler_id", handler_id)["name"]


def claim_view(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    """Return a claim in full with where it stands."""
    return {
        **json.loads(row["data"]),
        "status": row["status"],
        "decision": row["decision"],
        "payout": row["payout"],
        "running": bool(row["running"]),
        "reason": row["reason"],
        "policy_section": row["policy_section"],
        "paid_amount": row["paid_amount"],
        "signed_off_by": handler_name(conn, row["signed_off_by"]),
    }


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims() -> list[dict[str, Any]]:
    """List the claims queue with where each claim stands."""
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM claims ORDER BY claim_id").fetchall()
        queue = []
        for row in rows:
            claim = json.loads(row["data"])
            customer = document(conn, "customers", "customer_id", claim["customer_id"])
            queue.append(
                {
                    "claim_id": claim["claim_id"],
                    "customer_name": customer["name"],
                    "claim_type": claim["claim_type"],
                    "summary": claim["summary"],
                    "submitted_on": claim["submitted_on"],
                    "amount_claimed": claim["amount_claimed"],
                    "status": row["status"],
                    "decision": row["decision"],
                    "payout": row["payout"],
                    "running": bool(row["running"]),
                }
            )
    return queue


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> dict[str, Any]:
    """Get one claim in full, with its decision, payment and sign-off."""
    with db.connect() as conn:
        return claim_view(conn, claim_row(conn, claim_id))


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str) -> dict[str, Any]:
    """Get a policy with its plan's limits and the add-ons it has."""
    with db.connect() as conn:
        policy = document(conn, "policies", "policy_id", policy_id)
    plans = db.load("plans.json")
    return {
        **policy,
        "plan_details": next(p for p in plans["plans"] if p["plan"] == policy["plan"]),
        "deductible_applies_to": plans["deductible_applies_to"],
        "add_on_details": [
            a for a in plans["add_ons"] if a["add_on"] in policy["add_ons"]
        ],
    }


@app.get("/api/customers/{customer_id}/claim-history", operation_id="get_claim_history")
def get_claim_history(customer_id: str) -> dict[str, Any]:
    """Get a customer's earlier claims, without their contact details."""
    with db.connect() as conn:
        customer = document(conn, "customers", "customer_id", customer_id)
    return {
        "customer_id": customer["customer_id"],
        "name": customer["name"],
        "customer_since": customer["customer_since"],
        "previous_claims": customer["previous_claims"],
    }


@app.get("/api/documents/sections", operation_id="list_sections")
def list_sections() -> list[dict[str, Any]]:
    """List the numbered sections of the policy wording and the claims manual."""
    return [
        {
            "document": name,
            "document_title": documents.title(name),
            "number": section["number"],
            "title": section["title"],
        }
        for name in get_args(documents.Document)
        for section in documents.sections(name)
    ]


@app.get("/api/documents/{document}/sections/{number}", operation_id="read_section")
def read_section(document: documents.Document, number: int) -> dict[str, Any]:
    """Read one section of the policy wording or the claims manual."""
    for section in documents.sections(document):
        if section["number"] == number:
            return {
                "document": document,
                "document_title": documents.title(document),
                **section,
            }
    raise HTTPException(404, f"No section {number} in {document}")


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> dict[str, str]:
    """Get the UnderCover Agent's instructions."""
    return {"instructions": INSTRUCTIONS.read_text(encoding="utf-8")}


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[dict[str, Any]]:
    """List the claims handlers."""
    with db.connect() as conn:
        rows = conn.execute("SELECT data FROM handlers ORDER BY handler_id").fetchall()
    return [json.loads(row["data"]) for row in rows]


@app.post("/api/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, decision: Decision) -> dict[str, Any]:
    """Record the agent's decision on a claim it is working on."""
    payout = round(decision.payout, 2)
    if decision.decision == "approve" and payout <= 0:
        raise HTTPException(422, "An approval needs a payout above zero")
    if decision.decision != "approve" and payout != 0:
        raise HTTPException(422, "Only an approval has a payout")
    over_limit = decision.decision == "approve" and payout > approval_limit()
    status = "awaiting_sign_off" if over_limit else "decided"
    with db.connect() as conn:
        if claim_row(conn, claim_id)["status"] != "in_progress":
            raise conflict(f"Claim {claim_id} is not in progress")
        conn.execute(
            "UPDATE claims SET status = ?, decision = ?, payout = ?, reason = ?,"
            " policy_section = ? WHERE claim_id = ?",
            (
                status,
                decision.decision,
                payout,
                decision.reason,
                decision.policy_section,
                claim_id,
            ),
        )
        return claim_view(conn, claim_row(conn, claim_id))


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment) -> dict[str, Any]:
    """Pay an approved claim its payout; over the limit, only after sign-off."""
    amount = round(payment.amount, 2)
    with db.connect() as conn:
        row = claim_row(conn, claim_id)
        if row["decision"] != "approve":
            raise conflict(f"Claim {claim_id} is not approved")
        if row["paid_amount"] is not None:
            raise conflict(f"Claim {claim_id} is already paid")
        if amount != row["payout"]:
            raise conflict(f"The payout for {claim_id} is {row['payout']:.2f}")
        if row["status"] == "awaiting_sign_off":
            raise conflict(
                f"A payout over ${approval_limit():,.2f} waits for a handler's"
                " sign-off. The payment is not made."
            )
        conn.execute(
            "UPDATE claims SET paid_amount = ? WHERE claim_id = ?", (amount, claim_id)
        )
        return claim_view(conn, claim_row(conn, claim_id))


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, sign_off: SignOff) -> dict[str, Any]:
    """Sign off a payout over the limit as a handler, which makes the payment."""
    with db.connect() as conn:
        row = claim_row(conn, claim_id)
        if row["status"] != "awaiting_sign_off":
            raise conflict(f"Claim {claim_id} is not waiting for sign-off")
        handler_name(conn, sign_off.handler_id)
        conn.execute(
            "UPDATE claims SET status = 'decided', signed_off_by = ?,"
            " paid_amount = payout WHERE claim_id = ?",
            (sign_off.handler_id, claim_id),
        )
        return claim_view(conn, claim_row(conn, claim_id))


def add_step_row(conn: sqlite3.Connection, claim_id: str, step: Step) -> None:
    conn.execute(
        "INSERT INTO steps (claim_id, kind, detail) VALUES (?, ?, ?)",
        (claim_id, step.kind, step.detail),
    )


@app.post("/api/claims/{claim_id}/steps", operation_id="add_step")
def add_step(claim_id: str, step: Step) -> dict[str, str]:
    """Record one step the agent took on a claim."""
    with db.connect() as conn:
        claim_row(conn, claim_id)
        add_step_row(conn, claim_id, step)
    return {"status": "recorded"}


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str) -> list[dict[str, Any]]:
    """List the steps the agent took on a claim, in order."""
    with db.connect() as conn:
        claim_row(conn, claim_id)
        rows = conn.execute(
            "SELECT step_id, kind, detail, created_at FROM steps"
            " WHERE claim_id = ? ORDER BY step_id",
            (claim_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def start_claim(claim_id: str) -> bool:
    """Move a waiting claim to in progress with fresh steps; False if not waiting."""
    with db.connect() as conn:
        claim_row(conn, claim_id)
        started = conn.execute(
            "UPDATE claims SET status = 'in_progress', running = 1, thread_id = ?"
            " WHERE claim_id = ? AND status = 'waiting'",
            (str(uuid.uuid4()), claim_id),
        ).rowcount
        if started:
            conn.execute("DELETE FROM steps WHERE claim_id = ?", (claim_id,))
    return bool(started)


def return_to_queue(claim_id: str, message: str) -> None:
    with db.connect() as conn:
        add_step_row(conn, claim_id, Step(kind="error", detail=message))
        conn.execute(
            "UPDATE claims SET status = 'waiting' WHERE claim_id = ?", (claim_id,)
        )


def run_and_check(claim_id: str) -> None:
    """Run the agent on a claim, and put it back in the queue if it fails."""
    with db.connect() as conn:
        thread_id = claim_row(conn, claim_id)["thread_id"]
    try:
        undercover_agent.run(claim_id, thread_id)
    except Exception as error:  # noqa: BLE001
        return_to_queue(claim_id, f"The agent failed: {error}")
        return
    with db.connect() as conn:
        still_in_progress = claim_row(conn, claim_id)["status"] == "in_progress"
    if still_in_progress:
        return_to_queue(claim_id, "The agent ended without recording a decision.")


def work_claim(claim_id: str) -> None:
    """Run the agent on a claim; the claim is running until the run ends."""
    try:
        run_and_check(claim_id)
    finally:
        with db.connect() as conn:
            conn.execute(
                "UPDATE claims SET running = 0 WHERE claim_id = ?", (claim_id,)
            )


def work_waiting_claims(claim_ids: list[str]) -> None:
    for claim_id in claim_ids:
        if start_claim(claim_id):
            work_claim(claim_id)
        else:
            with db.connect() as conn:
                conn.execute(
                    "UPDATE claims SET running = 0 WHERE claim_id = ?", (claim_id,)
                )


@app.post("/api/claims/{claim_id}/run", operation_id="run_agent")
def run_agent(claim_id: str, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Start the UnderCover Agent on one waiting claim."""
    if not start_claim(claim_id):
        raise conflict(f"Claim {claim_id} is not waiting")
    background_tasks.add_task(work_claim, claim_id)
    return {"claim_id": claim_id, "status": "in_progress"}


@app.post("/api/queue/run", operation_id="work_queue")
def work_queue(background_tasks: BackgroundTasks) -> dict[str, int]:
    """Run the UnderCover Agent on every waiting claim, one after another."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT claim_id FROM claims WHERE status = 'waiting' AND running = 0"
            " ORDER BY claim_id"
        ).fetchall()
        conn.executemany(
            "UPDATE claims SET running = 1 WHERE claim_id = ?",
            [(row["claim_id"],) for row in rows],
        )
    claim_ids = [row["claim_id"] for row in rows]
    background_tasks.add_task(work_waiting_claims, claim_ids)
    return {"queued": len(claim_ids)}
