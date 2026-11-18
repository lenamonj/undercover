import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent import main as agent
from agent.tests.stub import call, decision, stub
from backend.main import app


@pytest.fixture(autouse=True)
def backend(client, monkeypatch):
    monkeypatch.setattr(agent, "backend", lambda: TestClient(app))


def use_model(monkeypatch, make):
    monkeypatch.setattr(agent, "model", make)


def status(client, claim_id: str) -> str:
    return client.get(f"/api/claims/{claim_id}").json()["status"]


def test_run_agent_decides_claim(client, monkeypatch):
    use_model(
        monkeypatch,
        lambda: stub(
            call("get_claim", claim_id="CLM-1001"),
            decision("CLM-1001", "approve", 420),
            call("pay_claim", claim_id="CLM-1001", amount=420),
            AIMessage(content="Approved."),
        ),
    )
    response = client.post("/api/claims/CLM-1001/run")
    assert response.json() == {"claim_id": "CLM-1001", "status": "in_progress"}
    assert status(client, "CLM-1001") == "decided"
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [s["kind"] for s in steps][-1] == "reply"
    assert client.post("/api/claims/CLM-1001/run").status_code == 409


def test_failed_run_returns_claim_to_queue(client, monkeypatch):
    def broken():
        raise RuntimeError("model unavailable")

    use_model(monkeypatch, broken)
    client.post("/api/claims/CLM-1001/run")
    assert status(client, "CLM-1001") == "waiting"
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert steps[-1]["kind"] == "error"
    assert "model unavailable" in steps[-1]["detail"]


def test_run_without_decision_returns_claim_to_queue(client, monkeypatch):
    use_model(monkeypatch, lambda: stub(AIMessage(content="I am not sure.")))
    client.post("/api/claims/CLM-1001/run")
    assert status(client, "CLM-1001") == "waiting"
    detail = client.get("/api/claims/CLM-1001/steps").json()[-1]["detail"]
    assert detail == "The agent ended without recording a decision."


def test_rerun_clears_earlier_steps(client, monkeypatch):
    use_model(monkeypatch, lambda: stub(AIMessage(content="Thinking.")))
    client.post("/api/claims/CLM-1001/run")
    client.post("/api/claims/CLM-1001/run")
    assert len(client.get("/api/claims/CLM-1001/steps").json()) == 2


def test_work_queue_leaves_nothing_waiting(client, monkeypatch):
    def refer_current_claim():
        claim_id = next(
            c["claim_id"]
            for c in client.get("/api/claims").json()
            if c["status"] == "in_progress"
        )
        return stub(decision(claim_id, "refer", 0), AIMessage(content="Referred."))

    use_model(monkeypatch, refer_current_claim)
    assert client.post("/api/queue/run").json() == {"queued": 25}
    statuses = {c["status"] for c in client.get("/api/claims").json()}
    assert statuses == {"decided"}


def test_unknown_claim(client):
    assert client.post("/api/claims/CLM-0000/run").status_code == 404
