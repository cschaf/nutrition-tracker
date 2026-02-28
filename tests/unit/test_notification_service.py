import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.config import Settings
from app.services.notification_service import NotificationService


@pytest.fixture  # type: ignore[misc]
def http_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture  # type: ignore[misc]
def settings() -> MagicMock:
    s = MagicMock(spec=Settings)
    s.webhook_enabled = True
    s.webhook_url = "https://ntfy.sh/my-topic"
    return s


@pytest.mark.asyncio  # type: ignore[misc]
async def test_ntfy_sends_correct_request(http_client: AsyncMock, settings: MagicMock) -> None:
    service = NotificationService(http_client, settings)
    await service.send("Test Title", "Test Message")

    # Give the background task a moment to start
    await asyncio.sleep(0.1)

    http_client.post.assert_called_once_with(
        "https://ntfy.sh/my-topic",
        content="Test Message",
        headers={"Title": "Test Title"},
        timeout=10.0,
    )


@pytest.mark.asyncio  # type: ignore[misc]
async def test_gotify_sends_correct_json(http_client: AsyncMock, settings: MagicMock) -> None:
    settings.webhook_url = "https://gotify.example.com"
    service = NotificationService(http_client, settings)
    await service.send("Test Title", "Test Message")

    await asyncio.sleep(0.1)

    http_client.post.assert_called_once_with(
        "https://gotify.example.com/message",
        json={
            "title": "Test Title",
            "message": "Test Message",
            "priority": 5,
        },
        timeout=10.0,
    )


@pytest.mark.asyncio  # type: ignore[misc]
async def test_disabled_webhook_skips_http(http_client: AsyncMock, settings: MagicMock) -> None:
    settings.webhook_enabled = False
    service = NotificationService(http_client, settings)
    await service.send("Test Title", "Test Message")

    await asyncio.sleep(0.1)
    http_client.post.assert_not_called()


@pytest.mark.asyncio  # type: ignore[misc]
async def test_error_is_not_propagated(
    http_client: AsyncMock, settings: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    http_client.post.side_effect = httpx.RequestError("Network down")
    service = NotificationService(http_client, settings)

    # This should not raise an exception
    await service.send("Test Title", "Test Message")

    await asyncio.sleep(0.1)

    # Check if error was logged
    assert "Failed to send notification" in caplog.text
    assert "Network down" in caplog.text
