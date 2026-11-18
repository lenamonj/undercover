from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies and remembers what it was sent."""

    seen: list[list[BaseMessage]] = []

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(messages)
        return super()._generate(messages, stop, run_manager, **kwargs)


def stub(*replies: AIMessage) -> StubModel:
    return StubModel(messages=iter(replies), seen=[])


def call(name: str, **args) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


def decision(claim_id: str, verdict: str, payout: float) -> AIMessage:
    return call(
        "record_decision",
        claim_id=claim_id,
        decision=verdict,
        payout=payout,
        reason="Covered by the wording.",
        policy_section="3. Trip Delay",
    )


class Backend(TestClient):
    """The backend's test client, without re-running its startup on every call."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
