from itertools import repeat

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent import main
from agent.tests.stub import Backend, StubModel, call, decision, stub
from backend import db
from backend.main import app


@pytest.fixture(autouse=True)
def backend(client, monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: Backend(app))


def start(claim_id: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE claims SET status = 'in_progress', running = 1 WHERE claim_id = ?",
            (claim_id,),
        )


def claim(client, claim_id: str) -> dict:
    return client.get(f"/api/claims/{claim_id}").json()


class FlakyModel(StubModel):
    """Raises on its first call, as a provider error would, then follows its script."""

    failed: bool = False

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if not self.failed:
            self.failed = True
            raise RuntimeError("provider unavailable")
        return super()._generate(messages, stop, run_manager, **kwargs)


def broken(monkeypatch):
    def raise_error(*args):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(main, "run", raise_error)


def test_failure_goes_back_in_the_queue(client, monkeypatch):
    broken(monkeypatch)
    start("CLM-1001")
    line = main.work_claim("CLM-1001")
    assert line == (
        "CLM-1001: failed (The agent failed: model unavailable); back in the queue"
    )
    record = claim(client, "CLM-1001")
    assert record["status"] == "waiting"
    assert record["attempts"] == 1
    assert record["running"] is False
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert steps[-1]["kind"] == "error"


@pytest.mark.usefixtures("no_queue_agent")
def test_second_failure_is_left_for_a_handler(client, monkeypatch):
    broken(monkeypatch)
    start("CLM-1001")
    main.work_claim("CLM-1001")
    start("CLM-1001")
    line = main.work_claim("CLM-1001")
    assert line.endswith("left for a handler")
    assert claim(client, "CLM-1001")["status"] == "needs_handler"

    run_id = client.post("/api/runs", json={"cap": 5}).json()["run_id"]
    refused = client.post(f"/api/runs/{run_id}/claims/CLM-1001/start")
    assert refused.status_code == 409
    assert "needs_handler" in refused.json()["detail"]


def test_no_decision_is_a_failure(client):
    start("CLM-1001")
    line = main.work_claim("CLM-1001", stub(AIMessage(content="Not sure.")))
    assert "ended without recording a decision" in line
    assert claim(client, "CLM-1001")["attempts"] == 1


def test_provider_error_is_retried(client):
    start("CLM-1001")
    model = FlakyModel(
        messages=iter([decision("CLM-1001", "decline", 0), AIMessage(content="Done.")]),
        seen=[],
    )
    assert main.work_claim("CLM-1001", model) == "CLM-1001: decline"
    record = claim(client, "CLM-1001")
    assert record["status"] == "decided"
    assert record["attempts"] == 0


def test_looping_agent_is_stopped(client):
    start("CLM-1001")
    looping = StubModel(messages=repeat(call("list_sections")), seen=[])
    line = main.work_claim("CLM-1001", looping)
    assert "ended without recording a decision" in line
    assert len(looping.seen) == main.CLAIM_MODEL_CALL_LIMIT


def test_reports(client):
    start("CLM-1001")
    model = stub(
        decision("CLM-1001", "approve", 420),
        call("pay_claim", claim_id="CLM-1001", amount=420),
        AIMessage(content="Approved."),
    )
    assert main.work_claim("CLM-1001", model) == "CLM-1001: approve, $420.00, paid"
    assert claim(client, "CLM-1001")["running"] is False

    start("CLM-1003")
    model = stub(
        decision("CLM-1003", "approve", 3750),
        call("pay_claim", claim_id="CLM-1003", amount=3750),
        AIMessage(content="Approved."),
    )
    assert main.work_claim("CLM-1003", model) == (
        "CLM-1003: approve, $3,750.00, payment waits for a handler's sign-off"
    )

    start("CLM-1013")
    model = stub(decision("CLM-1013", "approve", 61), AIMessage(content="Approved."))
    assert main.work_claim("CLM-1013", model) == "CLM-1013: approve, $61.00, not paid"


@pytest.mark.usefixtures("no_queue_agent")
def test_startup_recovers_an_interrupted_run(client):
    run_id = client.post("/api/runs", json={"cap": 5}).json()["run_id"]
    client.post(f"/api/runs/{run_id}/claims/CLM-1001/start")
    with TestClient(app) as restarted:
        record = restarted.get("/api/claims/CLM-1001").json()
        run = restarted.get("/api/runs/current").json()
    assert record["status"] == "waiting"
    assert record["attempts"] == 1
    assert record["running"] is False
    assert run["status"] == "interrupted"


def test_failure_needs_claim_in_progress(client):
    response = client.post("/api/claims/CLM-1001/failure", json={"error": "Boom"})
    assert response.status_code == 409
