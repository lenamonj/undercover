"""The UnderCover Agent."""

import json
import os
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
STEP_DETAIL_LIMIT = 600
MODEL_TIMEOUT_SECONDS = 60
CLAIM_MODEL_CALL_LIMIT = 30


def backend() -> httpx.Client:
    """Return a client for the backend at UNDERCOVER_URL, or on port 8000."""
    return httpx.Client(base_url=os.getenv("UNDERCOVER_URL", BACKEND_URL), timeout=30)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend; a refusal comes back as text for the agent to read."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_server_error:
        response.raise_for_status()
    if response.is_client_error:
        return f"Refused ({response.status_code}): {response.text}"
    return response.text


@tool
def get_claim(claim_id: str) -> str:
    """Get a claim: the story, the items claimed and the documents."""
    return call("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> str:
    """Get a policy with its plan's limits, waiting periods, deductible and add-ons."""
    return call("GET", f"/api/policies/{policy_id}")


@tool
def get_claim_history(customer_id: str) -> str:
    """Get a customer's earlier claims."""
    return call("GET", f"/api/customers/{customer_id}/claim-history")


@tool
def list_sections() -> str:
    """List the numbered sections of the policy wording and the claims manual."""
    return call("GET", "/api/documents/sections")


@tool
def read_section(
    document: Literal["policy_wording", "claims_manual"], number: int
) -> str:
    """Read one numbered section of the policy wording or the claims manual."""
    return call("GET", f"/api/documents/{document}/sections/{number}")


@tool
def record_decision(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reason: str,
    policy_section: str,
) -> str:
    """Record the decision on a claim, with the payout, reason and policy section."""
    body = {
        "decision": decision,
        "payout": payout,
        "reason": reason,
        "policy_section": policy_section,
    }
    return call("POST", f"/api/claims/{claim_id}/decision", body)


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim its payout."""
    return call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})


def claim_middleware() -> list[AgentMiddleware[Any, Any, Any]]:
    """Retry provider errors and timed-out tool calls, and stop a looping agent."""
    return [
        ModelRetryMiddleware(max_retries=2),
        ToolRetryMiddleware(max_retries=2, retry_on=(httpx.TimeoutException,)),
        ModelCallLimitMiddleware(run_limit=CLAIM_MODEL_CALL_LIMIT),
    ]


TOOLS = [
    get_claim,
    get_policy,
    get_claim_history,
    list_sections,
    read_section,
    record_decision,
    pay_claim,
]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or DeepSeek V4.1 Flash by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
        timeout=MODEL_TIMEOUT_SECONDS,
    )


def instructions(name: Literal["queue", "claim"]) -> str:
    """Fetch the queue agent's or the claim agent's instructions from the backend."""
    return json.loads(call("GET", "/api/instructions"))[name]


def add_step(claim_id: str, kind: str, detail: str) -> None:
    call("POST", f"/api/claims/{claim_id}/steps", {"kind": kind, "detail": detail})


def section_read(result: str) -> str:
    """Name the section a read_section result holds, or pass on its refusal."""
    if result.startswith("Refused"):
        return result[:STEP_DETAIL_LIMIT]
    section = json.loads(result)
    return f"{section['document_title']} {section['number']}. {section['title']}"


def record_steps(claim_id: str, message: BaseMessage) -> None:
    """Post the steps one message represents to the backend."""
    if isinstance(message, ToolMessage) and message.name == "read_section":
        add_step(claim_id, "read", section_read(message.text))
    elif isinstance(message, ToolMessage):
        detail = f"{message.name}: {message.text}"[:STEP_DETAIL_LIMIT]
        add_step(claim_id, "tool_result", detail)
    elif isinstance(message, AIMessage):
        for tool_call in message.tool_calls:
            add_step(
                claim_id,
                "tool_call",
                f"{tool_call['name']} {json.dumps(tool_call['args'])}",
            )
        if message.text:
            add_step(claim_id, "reply", message.text)


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim, recording each step, and return its final reply."""
    agent = create_agent(
        llm or model(),
        tools=TOOLS,
        system_prompt=instructions("claim"),
        middleware=claim_middleware(),
    )
    reply = ""
    for update in agent.stream(
        {"messages": [{"role": "user", "content": f"Decide claim {claim_id}."}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    ):
        for node in update.values():
            if not node:  # middleware nodes can report no update
                continue
            for message in node.get("messages", []):
                record_steps(claim_id, message)
                if isinstance(message, AIMessage) and not message.tool_calls:
                    reply = message.text
    return reply


def report(claim: dict[str, Any]) -> str:
    """Sum up a decided claim in one line."""
    line = f"{claim['claim_id']}: {claim['decision']}"
    if claim["decision"] != "approve":
        return line
    line += f", ${claim['payout']:,.2f}"
    if claim["paid_amount"] is not None:
        return line + ", paid"
    if claim["status"] == "awaiting_sign_off":
        return line + ", payment waits for a handler's sign-off"
    return line + ", not paid"


def fail(claim_id: str, error: str) -> str:
    """Record a failed attempt and say where the claim went."""
    claim = json.loads(
        call("POST", f"/api/claims/{claim_id}/failure", {"error": error})
    )
    where = (
        "left for a handler"
        if claim["status"] == "needs_handler"
        else "back in the queue"
    )
    return f"{claim_id}: failed ({error}); {where}"


def work_claim(claim_id: str, llm: BaseChatModel | None = None) -> str:
    """Run a fresh claim agent on a started claim and report back in one line."""
    claim = json.loads(call("GET", f"/api/claims/{claim_id}"))
    try:
        run(claim_id, claim["thread_id"], llm)
    except Exception as error:  # noqa: BLE001
        return fail(claim_id, f"The agent failed: {error}")
    claim = json.loads(call("GET", f"/api/claims/{claim_id}"))
    if claim["status"] == "in_progress":
        return fail(claim_id, "The agent ended without recording a decision.")
    call("POST", f"/api/claims/{claim_id}/release")
    return report(claim)
