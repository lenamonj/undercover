import pytest
from langchain_core.messages import AIMessage, ToolMessage

from agent import main, queue
from agent.tests.stub import Backend, call, decision, stub
from backend import db
from backend.main import app, create_run


@pytest.fixture(autouse=True)
def backend(client, monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: Backend(app))


def keep_waiting(*claim_ids: str) -> None:
    """Leave only these claims waiting, so a run's work stays small."""
    marks = ",".join("?" * len(claim_ids))
    with db.connect() as conn:
        conn.execute(
            f"UPDATE claims SET status = 'decided' WHERE claim_id NOT IN ({marks})",  # noqa: S608
            claim_ids,
        )


def claim_in_progress(client) -> str:
    return next(
        c["claim_id"]
        for c in client.get("/api/claims").json()
        if c["status"] == "in_progress"
    )


def referring_claim_agents(client, monkeypatch) -> None:
    def make():
        claim_id = claim_in_progress(client)
        return stub(decision(claim_id, "refer", 0), AIMessage(content="Referred."))

    monkeypatch.setattr(main, "model", make)


def todos(*items: tuple[str, str]) -> AIMessage:
    return call(
        "write_todos",
        todos=[{"content": content, "status": status} for content, status in items],
    )


def tool_results(model, name: str) -> list[str]:
    return [
        m.text for m in model.seen[-1] if isinstance(m, ToolMessage) and m.name == name
    ]


def test_capped_run_works_claims_and_finishes(client, monkeypatch):
    keep_waiting("CLM-1001", "CLM-1002", "CLM-1003")
    referring_claim_agents(client, monkeypatch)
    run_id = create_run(2)["run_id"]
    queue_model = stub(
        call("list_waiting_claims"),
        todos(("Work CLM-1001", "pending"), ("Work CLM-1002", "pending")),
        call("work_claim", claim_id="CLM-1001"),
        call("work_claim", claim_id="CLM-1002"),
        call("work_claim", claim_id="CLM-1003"),
        todos(("Work CLM-1001", "done"), ("Work CLM-1002", "done")),
        call("finish_run", summary="Two claims referred."),
        AIMessage(content="Two claims referred."),
    )
    queue.work_run(run_id, queue_model)

    run = client.get("/api/runs/current").json()
    assert run["status"] == "finished"
    assert run["summary"] == "Two claims referred."
    assert run["claims_started"] == 2
    assert run["todos"][1] == {"content": "Work CLM-1002", "status": "done"}
    assert client.get("/api/claims/CLM-1003").json()["status"] == "waiting"

    reports = tool_results(queue_model, "work_claim")
    assert reports[:2] == ["CLM-1001: refer", "CLM-1002: refer"]
    assert reports[2].startswith("Refused (409)")
    assert "cap of 2" in reports[2]
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [s["kind"] for s in steps] == ["tool_call", "tool_result", "reply"]


def test_failed_claim_is_retried_and_the_run_carries_on(client, monkeypatch):
    keep_waiting("CLM-1001", "CLM-1002")
    attempts = []

    def make():
        claim_id = claim_in_progress(client)
        attempts.append(claim_id)
        if attempts.count("CLM-1001") == 1 and claim_id == "CLM-1001":
            return stub(AIMessage(content="Lost my way."))
        return stub(decision(claim_id, "refer", 0), AIMessage(content="Referred."))

    monkeypatch.setattr(main, "model", make)
    run_id = create_run(2)["run_id"]
    queue_model = stub(
        call("work_claim", claim_id="CLM-1001"),
        call("work_claim", claim_id="CLM-1002"),
        call("work_claim", claim_id="CLM-1001"),
        call("finish_run", summary="Done."),
        AIMessage(content="Done."),
    )
    queue.work_run(run_id, queue_model)

    reports = tool_results(queue_model, "work_claim")
    assert reports[0].endswith("back in the queue")
    assert reports[1:] == ["CLM-1002: refer", "CLM-1001: refer"]
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["attempts"] == 1
    assert client.get("/api/runs/current").json()["status"] == "finished"


def test_claim_failing_twice_is_left_for_a_handler(client, monkeypatch):
    keep_waiting("CLM-1001")
    monkeypatch.setattr(main, "model", lambda: stub(AIMessage(content="Lost.")))
    run_id = create_run(1)["run_id"]
    queue_model = stub(
        call("work_claim", claim_id="CLM-1001"),
        call("work_claim", claim_id="CLM-1001"),
        todos(("Work CLM-1001", "left_for_handler")),
        call("finish_run", summary="CLM-1001 left for a handler."),
        AIMessage(content="CLM-1001 left for a handler."),
    )
    queue.work_run(run_id, queue_model)

    assert tool_results(queue_model, "work_claim")[1].endswith("left for a handler")
    assert client.get("/api/claims/CLM-1001").json()["status"] == "needs_handler"
    run = client.get("/api/runs/current").json()
    assert run["status"] == "finished"
    assert run["todos"] == [{"content": "Work CLM-1001", "status": "left_for_handler"}]


def test_finishing_early_is_refused_until_missed_claims_are_worked(client, monkeypatch):
    keep_waiting("CLM-1001", "CLM-1002")
    referring_claim_agents(client, monkeypatch)
    run_id = create_run(5)["run_id"]
    queue_model = stub(
        call("finish_run", summary="Nothing to do."),
        call("work_claim", claim_id="CLM-1001"),
        call("work_claim", claim_id="CLM-1002"),
        call("finish_run", summary="Two referred."),
        AIMessage(content="Two referred."),
    )
    queue.work_run(run_id, queue_model)

    finishes = tool_results(queue_model, "finish_run")
    assert finishes[0].startswith("Refused (409)")
    assert "CLM-1001, CLM-1002" in finishes[0]
    assert finishes[1] == "Finished."
    assert client.get("/api/runs/current").json()["summary"] == "Two referred."


def test_queue_agent_failure_fails_the_run(client, monkeypatch):
    def broken(run_id, llm=None):
        raise RuntimeError("provider down")

    monkeypatch.setattr(queue, "run_queue", broken)
    queue.work_run(create_run(1)["run_id"])
    run = client.get("/api/runs/current").json()
    assert run["status"] == "failed"
    assert run["error"] == "The agent failed: provider down"


def test_run_that_never_finishes_fails(client):
    keep_waiting("CLM-1001")
    queue.work_run(create_run(1)["run_id"], stub(AIMessage(content="Bye.")))
    run = client.get("/api/runs/current").json()
    assert run["status"] == "failed"
    assert run["error"] == "The agent ended without finishing the run."


def test_queue_agent_gets_its_own_instructions(client):
    keep_waiting()
    queue_model = stub(
        call("finish_run", summary="Nothing waiting."), AIMessage(content="Done.")
    )
    queue.work_run(create_run(3)["run_id"], queue_model)
    system, request = queue_model.seen[0][:2]
    assert system.content == client.get("/api/instructions").json()["queue"]
    assert request.content == "Work the queue. This run is capped at 3 claims."


def test_start_run_starts_the_queue_agent(client, monkeypatch):
    started = []
    monkeypatch.setattr(queue, "work_run", started.append)
    run = client.post("/api/runs", json={"cap": 5}).json()
    assert started == [run["run_id"]]


def test_capped_run_leaves_the_rest_of_the_queue_waiting(client, monkeypatch):
    referring_claim_agents(client, monkeypatch)
    run_id = create_run(2)["run_id"]
    queue_model = stub(
        call("work_claim", claim_id="CLM-1001"),
        call("work_claim", claim_id="CLM-1002"),
        call("finish_run", summary="Two referred."),
        AIMessage(content="Two referred."),
    )
    queue.work_run(run_id, queue_model)
    statuses = [c["status"] for c in client.get("/api/claims").json()]
    assert statuses.count("waiting") == 23
    assert client.get("/api/runs/current").json()["status"] == "finished"
