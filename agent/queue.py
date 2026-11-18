"""The queue agent: works a run's claims through a fresh claim agent for each."""

import json
from typing import Any, Literal, TypedDict

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, tool

from agent import main
from agent.main import call

QUEUE_MODEL_CALL_LIMIT = 200


class Todo(TypedDict):
    content: str
    status: Literal["pending", "in_progress", "done", "left_for_handler"]


def queue_tools(run_id: int) -> list[BaseTool]:
    """The queue agent's tools, bound to one run."""

    @tool
    def list_waiting_claims() -> str:
        """List the claims waiting to be worked, with how often each has failed."""
        return call("GET", "/api/claims/waiting")

    @tool
    def write_todos(todos: list[Todo]) -> str:
        """Save the whole to-do list for this run."""
        call("PUT", f"/api/runs/{run_id}/todos", {"todos": todos})
        return "Saved."

    @tool
    def work_claim(claim_id: str) -> str:
        """Hand one waiting claim to a fresh claim agent; it reports back in a line."""
        started = call("POST", f"/api/runs/{run_id}/claims/{claim_id}/start")
        if started.startswith("Refused"):
            return started
        return main.work_claim(claim_id)

    @tool
    def finish_run(summary: str) -> str:
        """Finish the run with a short summary for the handlers."""
        result = call("POST", f"/api/runs/{run_id}/finish", {"summary": summary})
        return result if result.startswith("Refused") else "Finished."

    return [list_waiting_claims, write_todos, work_claim, finish_run]


def queue_middleware() -> list[AgentMiddleware[Any, Any, Any]]:
    """Retry provider errors, and stop a queue agent that loops."""
    return [
        ModelRetryMiddleware(max_retries=2),
        ModelCallLimitMiddleware(run_limit=QUEUE_MODEL_CALL_LIMIT),
    ]


def run_queue(run_id: int, llm: BaseChatModel | None = None) -> str:
    """Run the queue agent on one run and return its final reply."""
    run = json.loads(call("GET", "/api/runs/current"))
    agent = create_agent(
        llm or main.model(),
        tools=queue_tools(run_id),
        system_prompt=main.instructions("queue"),
        middleware=queue_middleware(),
    )
    request = f"Work the queue. This run is capped at {run['cap']} claims."
    result = agent.invoke(
        {"messages": [{"role": "user", "content": request}]},
        config={"configurable": {"thread_id": run["thread_id"]}},
    )
    return result["messages"][-1].text


def work_run(run_id: int, llm: BaseChatModel | None = None) -> None:
    """Run the queue agent, and mark the run failed if it stops before finishing."""
    try:
        run_queue(run_id, llm)
    except Exception as error:  # noqa: BLE001
        call(
            "POST",
            f"/api/runs/{run_id}/failure",
            {"error": f"The agent failed: {error}"},
        )
        return
    run = json.loads(call("GET", "/api/runs/current"))
    if run["status"] == "running":
        error = "The agent ended without finishing the run."
        call("POST", f"/api/runs/{run_id}/failure", {"error": error})
