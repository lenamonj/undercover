"""The UnderCover Agent."""

import json
import os
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
STEP_DETAIL_LIMIT = 600


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


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
def get_policy_wording() -> str:
    """Get the policy wording, the contract with the customer."""
    return call("GET", "/api/policy-wording")


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


TOOLS = [
    get_claim,
    get_policy,
    get_claim_history,
    get_policy_wording,
    record_decision,
    pay_claim,
]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def instructions() -> str:
    """Fetch the agent's instructions from the backend."""
    return json.loads(call("GET", "/api/instructions"))["instructions"]


def add_step(claim_id: str, kind: str, detail: str) -> None:
    call("POST", f"/api/claims/{claim_id}/steps", {"kind": kind, "detail": detail})


def record_steps(claim_id: str, message: BaseMessage) -> None:
    """Post the steps one message represents to the backend."""
    if isinstance(message, ToolMessage):
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
    agent = create_agent(llm or model(), tools=TOOLS, system_prompt=instructions())
    reply = ""
    for update in agent.stream(
        {"messages": [{"role": "user", "content": f"Decide claim {claim_id}."}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    ):
        for node in update.values():
            for message in node["messages"]:
                record_steps(claim_id, message)
                if isinstance(message, AIMessage) and not message.tool_calls:
                    reply = message.text
    return reply
