# tests/conftest.py
from unittest.mock import patch

import pytest
from app.core.config import Settings
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def test_settings() -> Settings:
    return Settings(api_keys={"test-key-alice": "tenant_alice", "test-key-bob": "tenant_bob"})


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    with patch("app.core.config.get_settings", return_value=test_settings), TestClient(app) as c:
        yield c


@pytest.fixture
def alice_headers() -> dict:
    return {"X-API-Key": "test-key-alice"}
