# tests/conftest.py
from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app.api.dependencies as _deps
from app.core.config import Settings, get_settings
from app.main import app


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        api_keys={"test-key-alice": "tenant_alice", "test-key-bob": "tenant_bob"},
        database_url="sqlite+aiosqlite:///:memory:",
    )


@pytest.fixture
def client(test_settings: Settings) -> Generator[TestClient, None, None]:
    # Reset the log-repository singleton so each test starts with an empty
    # in-memory SQLite database (avoids bleed-over from previous test runs or
    # other tests that created real entries via the singleton).
    _deps._repository = None
    # Override get_settings via FastAPI's DI override map (the correct approach
    # for FastAPI; plain unittest.mock.patch does not reach Depends() callbacks).
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        with patch("app.core.config.get_settings", return_value=test_settings), TestClient(
            app
        ) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_settings, None)
        _deps._repository = None


@pytest.fixture
def alice_headers() -> dict:
    return {"X-API-Key": "test-key-alice"}
