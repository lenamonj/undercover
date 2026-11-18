import pytest

from backend import db

pytestmark = pytest.mark.usefixtures("no_queue_agent")


def new_run(client, cap: int) -> int:
    return client.post("/api/runs", json={"cap": cap}).json()["run_id"]


def start(client, run_id: int, claim_id: str):
    return client.post(f"/api/runs/{run_id}/claims/{claim_id}/start")


def refer(client, claim_id: str) -> None:
    client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": "refer",
            "payout": 0,
            "reason": "Needs a handler.",
            "policy_section": "2. The three decisions",
        },
    )


def back_to_queue(claim_id: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE claims SET status = 'waiting', attempts = 1 WHERE claim_id = ?",
            (claim_id,),
        )


def finish(client, run_id: int):
    return client.post(f"/api/runs/{run_id}/finish", json={"summary": "All done."})


def test_cap_limits_claims_started(client):
    run_id = new_run(client, 5)
    for n in range(1, 6):
        assert start(client, run_id, f"CLM-100{n}").status_code == 200
    sixth = start(client, run_id, "CLM-1006")
    assert sixth.status_code == 409
    assert "cap of 5" in sixth.json()["detail"]
    assert client.get("/api/runs/current").json()["claims_started"] == 5


def test_retry_does_not_count_against_cap(client):
    run_id = new_run(client, 1)
    start(client, run_id, "CLM-1001")
    back_to_queue("CLM-1001")
    retry = start(client, run_id, "CLM-1001")
    assert retry.status_code == 200
    assert retry.json()["status"] == "in_progress"


def test_retry_keeps_steps_but_new_run_clears_them(client):
    run_id = new_run(client, 1)
    start(client, run_id, "CLM-1001")
    client.post("/api/claims/CLM-1001/steps", json={"kind": "error", "detail": "Boom"})
    back_to_queue("CLM-1001")
    start(client, run_id, "CLM-1001")
    assert len(client.get("/api/claims/CLM-1001/steps").json()) == 1

    refer(client, "CLM-1001")
    assert finish(client, run_id).status_code == 200
    back_to_queue("CLM-1001")
    start(client, new_run(client, 1), "CLM-1001")
    assert client.get("/api/claims/CLM-1001/steps").json() == []


def test_claim_not_waiting_is_never_started(client):
    run_id = new_run(client, 5)
    start(client, run_id, "CLM-1001")
    refer(client, "CLM-1001")
    again = start(client, run_id, "CLM-1001")
    assert again.status_code == 409
    assert "decided" in again.json()["detail"]


def test_todos_are_stored_in_order(client):
    run_id = new_run(client, 2)
    todos = [
        {"content": "Work CLM-1001", "status": "done"},
        {"content": "Work CLM-1002", "status": "in_progress"},
        {"content": "Work CLM-1003", "status": "pending"},
        {"content": "Work CLM-1004", "status": "left_for_handler"},
    ]
    client.put(f"/api/runs/{run_id}/todos", json={"todos": todos})
    assert client.get("/api/runs/current").json()["todos"] == todos
    bad = [{"content": "Work CLM-1001", "status": "finished"}]
    assert (
        client.put(f"/api/runs/{run_id}/todos", json={"todos": bad}).status_code == 422
    )


def test_finish_refused_while_claims_are_missed(client):
    run_id = new_run(client, 2)
    start(client, run_id, "CLM-1001")
    refer(client, "CLM-1001")
    missed = finish(client, run_id)
    assert missed.status_code == 409
    assert "CLM-1002" in missed.json()["detail"]

    start(client, run_id, "CLM-1002")
    back_to_queue("CLM-1002")
    retry_owed = finish(client, run_id)
    assert retry_owed.status_code == 409
    assert retry_owed.json()["detail"] == "Claims still to work: CLM-1002"

    start(client, run_id, "CLM-1002")
    refer(client, "CLM-1002")
    done = finish(client, run_id).json()
    assert done["status"] == "finished"
    assert done["summary"] == "All done."
    assert done["finished_at"]


def test_finish_when_no_claims_are_left(client):
    with db.connect() as conn:
        conn.execute("UPDATE claims SET status = 'decided'")
    run_id = new_run(client, 5)
    assert finish(client, run_id).status_code == 200
    assert finish(client, run_id).status_code == 409


def test_one_run_at_a_time(client):
    assert client.get("/api/runs/current").json() is None
    new_run(client, 5)
    assert client.post("/api/runs", json={"cap": 5}).status_code == 409
    assert client.post("/api/runs", json={"cap": 0}).status_code == 422
    assert client.post("/api/runs/99/claims/CLM-1001/start").status_code == 404


def test_waiting_claims_list(client):
    run_id = new_run(client, 2)
    start(client, run_id, "CLM-1001")
    back_to_queue("CLM-1001")
    start(client, run_id, "CLM-1002")
    waiting = client.get("/api/claims/waiting").json()
    assert len(waiting) == 24
    assert waiting[0]["claim_id"] == "CLM-1001"
    assert waiting[0]["attempts"] == 1
    assert "CLM-1002" not in [claim["claim_id"] for claim in waiting]
