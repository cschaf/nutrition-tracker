# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.core.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    return Settings(api_keys={"test-key-alice": "tenant_alice", "test-key-bob": "tenant_bob"})


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    with patch("app.core.config.get_settings", return_value=test_settings):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def alice_headers() -> dict:
    return {"X-API-Key": "test-key-alice"}