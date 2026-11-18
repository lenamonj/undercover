import pytest
from fastapi.testclient import TestClient

from agent import queue
from backend.main import app


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    """Give every test its own freshly seeded database."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
    # No test may reach a real model: without the key, any attempt fails at once.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def no_queue_agent(monkeypatch):
    """Start runs without the queue agent, for tests of the backend's rules."""
    monkeypatch.setattr(queue, "work_run", lambda run_id: None)
