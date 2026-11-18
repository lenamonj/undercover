import pytest

from backend import db


def start(claim_id: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE claims SET status = 'in_progress' WHERE claim_id = ?", (claim_id,)
        )


def decide(client, claim_id: str, decision: str, payout: float):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "reason": "The delay is covered.",
            "policy_section": "3. Trip Delay",
        },
    )


def pay(client, claim_id: str, amount: float):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def test_approve_and_pay_under_limit(client):
    start("CLM-1001")
    assert decide(client, "CLM-1001", "approve", 420).json()["status"] == "decided"
    claim = pay(client, "CLM-1001", 420).json()
    assert claim["paid_amount"] == 420.0
    assert claim["reason"] == "The delay is covered."
    assert claim["policy_section"] == "3. Trip Delay"


@pytest.mark.parametrize(
    ("payout", "status"),
    [(1000.00, "decided"), (1000.01, "awaiting_sign_off")],
)
def test_limit_boundary(client, payout, status):
    start("CLM-1002")
    assert decide(client, "CLM-1002", "approve", payout).json()["status"] == status


def test_payment_over_limit_is_blocked_until_sign_off(client):
    start("CLM-1002")
    decide(client, "CLM-1002", "approve", 1500)
    blocked = pay(client, "CLM-1002", 1500)
    assert blocked.status_code == 409
    assert "sign-off" in blocked.json()["detail"]
    assert client.get("/api/claims/CLM-1002").json()["paid_amount"] is None

    signed = client.post("/api/claims/CLM-1002/sign-off", json={"handler_id": "HND-01"})
    claim = signed.json()
    assert claim["status"] == "decided"
    assert claim["paid_amount"] == 1500.0
    assert claim["signed_off_by"] == "Dana Whitfield"
    assert pay(client, "CLM-1002", 1500).status_code == 409


def test_decision_needs_claim_in_progress(client):
    assert decide(client, "CLM-1001", "approve", 420).status_code == 409


def test_decline_and_refer_have_no_payout(client):
    start("CLM-1001")
    assert decide(client, "CLM-1001", "decline", 50).status_code == 422
    assert decide(client, "CLM-1001", "approve", 0).status_code == 422
    claim = decide(client, "CLM-1001", "refer", 0).json()
    assert claim["status"] == "decided"
    assert claim["payout"] == 0


def test_bad_payments(client):
    start("CLM-1001")
    decide(client, "CLM-1001", "decline", 0)
    assert pay(client, "CLM-1001", 420).status_code == 409
    start("CLM-1013")
    decide(client, "CLM-1013", "approve", 123)
    assert pay(client, "CLM-1013", 100).status_code == 409
    assert pay(client, "CLM-1013", 123).status_code == 200
    assert pay(client, "CLM-1013", 123).status_code == 409


def test_bad_sign_offs(client):
    sign_off = {"handler_id": "HND-01"}
    assert (
        client.post("/api/claims/CLM-1001/sign-off", json=sign_off).status_code == 409
    )
    start("CLM-1002")
    decide(client, "CLM-1002", "approve", 1500)
    unknown = {"handler_id": "HND-99"}
    assert client.post("/api/claims/CLM-1002/sign-off", json=unknown).status_code == 404
