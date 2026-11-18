import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    """Give every test its own freshly seeded database."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
