"""The backend for the end-to-end tests: a fresh database and a scripted model."""

import json
import os
import re
import tempfile
import time
from pathlib import Path

import uvicorn
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

PORT = 8001
os.environ["UNDERCOVER_DB"] = str(Path(tempfile.gettempdir()) / "undercover-e2e.db")
os.environ["UNDERCOVER_URL"] = f"http://127.0.0.1:{PORT}"

from agent import main as agent  # noqa: E402
from backend import db  # noqa: E402

STEP_DELAY_SECONDS = 0.2


def tool_call(name: str, **args: object) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


def results(messages: list[BaseMessage]) -> list[ToolMessage]:
    return [m for m in messages if isinstance(m, ToolMessage)]


def claim_step(messages: list[BaseMessage]) -> AIMessage:
    """Read the claim and one section, approve the amount claimed, pay, reply."""
    claim_id = re.findall(r"CLM-\d+", messages[1].text)[0]
    done = results(messages)
    if not done:
        return tool_call("get_claim", claim_id=claim_id)
    payout = json.loads(done[0].text)["amount_claimed"]
    script = [
        tool_call("read_section", document="policy_wording", number=3),
        tool_call(
            "record_decision",
            claim_id=claim_id,
            decision="approve",
            payout=payout,
            reason="The scripted model approves the amount claimed.",
            policy_section="3. Trip Delay",
        ),
        tool_call("pay_claim", claim_id=claim_id, amount=payout),
    ]
    if len(done) <= len(script):
        return script[len(done) - 1]
    return AIMessage(content=f"Approved {claim_id}.")


def todos(claim_ids: list[str], worked: int) -> AIMessage:
    statuses = ["done"] * worked + ["in_progress"] + ["pending"] * len(claim_ids)
    return tool_call(
        "write_todos",
        todos=[
            {"content": f"Work {claim_id}", "status": status}
            for claim_id, status in zip(claim_ids, statuses, strict=False)
        ],
    )


def queue_step(messages: list[BaseMessage]) -> AIMessage:
    """List the waiting claims, then for each one up to the cap: todos, work."""
    done = results(messages)
    if not done:
        return tool_call("list_waiting_claims")
    cap = int(re.findall(r"capped at (\d+)", messages[1].text)[0])
    claim_ids = [claim["claim_id"] for claim in json.loads(done[0].text)][:cap]
    worked = sum(1 for m in done if m.name == "work_claim")
    last = done[-1].name
    if last in ("list_waiting_claims", "work_claim"):
        return todos(claim_ids, worked)
    if last == "write_todos" and worked < len(claim_ids):
        return tool_call("work_claim", claim_id=claim_ids[worked])
    if last == "write_todos":
        return tool_call("finish_run", summary=f"Approved {worked} claims.")
    return AIMessage(content=f"Approved {worked} claims.")


class ScriptedModel(BaseChatModel):
    """Plays the queue agent or a claim agent, depending on its instructions."""

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(
        self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs
    ):
        time.sleep(STEP_DELAY_SECONDS)
        is_queue = "list_waiting_claims" in messages[0].text
        reply = queue_step(messages) if is_queue else claim_step(messages)
        return ChatResult(generations=[ChatGeneration(message=reply)])


if __name__ == "__main__":
    db.reset()
    agent.model = ScriptedModel
    uvicorn.run("backend.main:app", port=PORT)
