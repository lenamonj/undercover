from fastapi.testclient import TestClient

from backend import db
from backend.main import app


def test_queue_is_seeded(client):
    queue = client.get("/api/claims").json()
    assert len(queue) == 25
    assert {claim["status"] for claim in queue} == {"waiting"}
    assert queue[0]["customer_name"] == "Maya Patel"


def test_security_claim_is_not_in_queue(client):
    ids = [claim["claim_id"] for claim in client.get("/api/claims").json()]
    assert "CLM-1901" not in ids
    assert client.get("/api/claims/CLM-1901").status_code == 404


def test_restart_does_not_reseed(client):
    db.init_db()
    with TestClient(app) as again:
        assert len(again.get("/api/claims").json()) == 25


def test_reset(client):
    with db.connect() as conn:
        conn.execute("UPDATE claims SET status = 'decided'")
    db.reset()
    assert {c["status"] for c in client.get("/api/claims").json()} == {"waiting"}


def test_get_claim(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["amount_claimed"] == 420.0
    assert len(claim["items"]) == 3
    assert claim["documents"]
    assert claim["story"].startswith("My flight home from Rome")
    assert claim["status"] == "waiting"
    assert claim["decision"] is None


def test_get_policy(client):
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"] == "premium"
    assert policy["plan_details"]["trip_delay_max"] == 800.0
    assert policy["deductible_applies_to"] == ["baggage", "emergency_medical"]
    assert policy["add_on_details"] == []


def test_get_claim_history(client):
    history = client.get("/api/customers/CUS-3001/claim-history").json()
    assert [c["claim_id"] for c in history["previous_claims"]] == ["CLM-0412"]
    assert not {"email", "phone", "address", "date_of_birth"} & history.keys()


def test_policy_wording(client):
    wording = client.get("/api/policy-wording").json()
    assert wording["text"] == (db.DATA_DIR / "policy_wording.md").read_text(
        encoding="utf-8"
    )
    assert wording["version"] == "2026.1"


def test_instructions(client):
    assert "UnderCover Agent" in client.get("/api/instructions").json()["instructions"]


def test_handlers(client):
    handlers = client.get("/api/handlers").json()
    assert [h["handler_id"] for h in handlers] == ["HND-01", "HND-02", "HND-03"]


def test_unknown_records(client):
    assert client.get("/api/claims/CLM-0000").status_code == 404
    assert client.get("/api/policies/POL-0000").status_code == 404
    assert client.get("/api/customers/CUS-0000/claim-history").status_code == 404


def test_every_operation_is_documented(client):
    paths = client.get("/openapi.json").json()["paths"]
    for path in paths.values():
        for operation in path.values():
            assert operation["operationId"]
            assert operation["description"]
            for parameter in operation.get("parameters", []):
                assert parameter["required"]
