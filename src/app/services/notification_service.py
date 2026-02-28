from __future__ import annotations

import asyncio
import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http_client = http_client
        self._settings = settings

    async def send(self, title: str, message: str) -> None:
        """Sends a notification using the configured webhook (fire-and-forget)."""
        if not self._settings.webhook_enabled or not self._settings.webhook_url:
            return

        # Fire and forget
        asyncio.create_task(self._perform_send(title, message))

    async def _perform_send(self, title: str, message: str) -> None:
        """Internal method to perform the actual HTTP call."""
        url = self._settings.webhook_url
        if not url:
            return

        try:
            if "ntfy.sh" in url:
                # ntfy style: POST {url} with text body and Title header
                await self._http_client.post(
                    url,
                    content=message,
                    headers={"Title": title},
                    timeout=10.0,
                )
            else:
                # Gotify style (fallback): POST {url}/message with JSON body
                # Ensure we don't double up on slashes if the URL ends with one
                base_url = url.rstrip("/")
                await self._http_client.post(
                    f"{base_url}/message",
                    json={
                        "title": title,
                        "message": message,
                        "priority": 5,
                    },
                    timeout=10.0,
                )
        except Exception:
            logger.exception("Failed to send notification to %s", url)
