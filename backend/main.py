"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend import db

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
        raise HTTPException(404, f"No {table[:-1]} {value}")
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


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> dict[str, str]:
    """Get the policy wording, the contract with the customer."""
    version = db.load("company.json")["policy_wording_version"]
    text = (db.DATA_DIR / "policy_wording.md").read_text(encoding="utf-8")
    return {"version": version, "text": text}


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
