"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from backend import db

INSTRUCTIONS = Path(__file__).parent / "instructions.md"


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
