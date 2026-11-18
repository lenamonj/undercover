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


class ScriptedModel(BaseChatModel):
    """Reads the claim, approves the amount claimed, pays it, then replies."""

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(
        self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs
    ):
        time.sleep(STEP_DELAY_SECONDS)
        claim_id = re.findall(r"CLM-\d+", messages[1].text)[0]
        results = [m for m in messages if isinstance(m, ToolMessage)]
        if not results:
            reply = tool_call("get_claim", claim_id=claim_id)
        else:
            payout = json.loads(results[0].text)["amount_claimed"]
            if len(results) == 1:
                reply = tool_call(
                    "record_decision",
                    claim_id=claim_id,
                    decision="approve",
                    payout=payout,
                    reason="The scripted model approves the amount claimed.",
                    policy_section="3. Trip Delay",
                )
            elif len(results) == 2:  # noqa: PLR2004
                reply = tool_call("pay_claim", claim_id=claim_id, amount=payout)
            else:
                reply = AIMessage(content=f"Approved {claim_id}.")
        return ChatResult(generations=[ChatGeneration(message=reply)])


if __name__ == "__main__":
    db.reset()
    agent.model = ScriptedModel
    uvicorn.run("backend.main:app", port=PORT)
