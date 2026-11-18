from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from agent import main
from agent.tests.stub import Backend, call, decision, stub
from backend import db
from backend.main import app


@pytest.fixture(autouse=True)
def backend(client, monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: Backend(app))


def start(claim_id: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE claims SET status = 'in_progress' WHERE claim_id = ?", (claim_id,)
        )


def steps(client, claim_id: str) -> list[tuple[str, str]]:
    rows = client.get(f"/api/claims/{claim_id}/steps").json()
    return [(row["kind"], row["detail"]) for row in rows]


def test_approve_and_pay(client):
    start("CLM-1001")
    model = stub(
        call("get_claim", claim_id="CLM-1001"),
        call("get_policy", policy_id="POL-2001"),
        call("get_claim_history", customer_id="CUS-3001"),
        call("read_section", document="policy_wording", number=3),
        decision("CLM-1001", "approve", 420),
        call("pay_claim", claim_id="CLM-1001", amount=420),
        AIMessage(content="Approved for $420.00."),
    )
    assert main.run("CLM-1001", "thread-1", model) == "Approved for $420.00."

    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["paid_amount"] == 420.0
    kinds = [kind for kind, _ in steps(client, "CLM-1001")]
    assert kinds == (
        ["tool_call", "tool_result"] * 3
        + ["tool_call", "read"]
        + ["tool_call", "tool_result"] * 2
        + ["reply"]
    )
    assert steps(client, "CLM-1001")[0] == (
        "tool_call",
        'get_claim {"claim_id": "CLM-1001"}',
    )


def test_payment_over_limit_is_refused(client):
    start("CLM-1002")
    model = stub(
        decision("CLM-1002", "approve", 1500),
        call("pay_claim", claim_id="CLM-1002", amount=1500),
        AIMessage(content="Approved; the payment waits for sign-off."),
    )
    main.run("CLM-1002", "thread-2", model)

    claim = client.get("/api/claims/CLM-1002").json()
    assert claim["status"] == "awaiting_sign_off"
    assert claim["paid_amount"] is None
    refusal = steps(client, "CLM-1002")[3]
    assert refusal[0] == "tool_result"
    assert refusal[1].startswith("pay_claim: Refused (409)")
    assert "sign-off" in refusal[1]


def test_decline_makes_no_payment(client):
    start("CLM-1001")
    model = stub(decision("CLM-1001", "decline", 0), AIMessage(content="Declined."))
    main.run("CLM-1001", "thread-3", model)

    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["decision"] == "decline"
    assert claim["payout"] == 0
    assert claim["paid_amount"] is None


def test_system_prompt_comes_from_backend(client):
    model = stub(AIMessage(content="Done."))
    main.run("CLM-1001", "thread-4", model)
    system = model.seen[0][0]
    assert system.type == "system"
    assert system.content == client.get("/api/instructions").json()["claim"]


def test_sections_read_are_recorded(client):
    model = stub(
        call("list_sections"),
        call("read_section", document="claims_manual", number=9),
        call("read_section", document="claims_manual", number=99),
        AIMessage(content="Read them."),
    )
    main.run("CLM-1001", "thread-6", model)
    reads = [detail for kind, detail in steps(client, "CLM-1001") if kind == "read"]
    assert reads[0] == "Claims manual 9. Repeat claims"
    assert reads[1].startswith("Refused (404)")


def test_long_results_are_trimmed(client):
    model = stub(call("get_claim", claim_id="CLM-1001"), AIMessage(content="Read it."))
    main.run("CLM-1001", "thread-5", model)
    result = steps(client, "CLM-1001")[1][1]
    assert len(result) == main.STEP_DETAIL_LIMIT


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    default = main.model()
    assert default.model_name == "deepseek/deepseek-v4.1-flash"
    assert default.reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"


def test_agent_reads_nothing_from_data():
    source = Path(main.__file__).read_text(encoding="utf-8")
    assert "data/" not in source
    assert "from backend" not in source
    assert "import backend" not in source
