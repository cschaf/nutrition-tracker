# src/app/repositories/log_repository.py
from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.domain.models import LogEntry
from app.repositories.base import AbstractLogRepository


class InMemoryLogRepository(AbstractLogRepository):
    """
    In-Memory Repository für den Homelab-Einsatz.
    Interface kann gegen SQLAlchemy/Motor-Implementierung ausgetauscht werden.
    """

    def __init__(self) -> None:
        # Struktur: {tenant_id: {log_id: LogEntry}}
        self._store: dict[str, dict[str, LogEntry]] = defaultdict(dict)

    async def save(self, entry: LogEntry) -> LogEntry:
        self._store[entry.tenant_id][entry.id] = entry
        return entry

    async def find_by_id(self, tenant_id: str, entry_id: str) -> LogEntry | None:
        return self._store[tenant_id].get(entry_id)

    async def find_by_date(self, tenant_id: str, log_date: date) -> list[LogEntry]:
        return [e for e in self._store[tenant_id].values() if e.log_date == log_date]

    async def find_by_date_range(
        self, tenant_id: str, start_date: date, end_date: date
    ) -> list[LogEntry]:
        return [e for e in self._store[tenant_id].values() if start_date <= e.log_date <= end_date]

    async def delete(self, tenant_id: str, entry_id: str) -> bool:
        return self._store[tenant_id].pop(entry_id, None) is not None

    async def update(self, entry: LogEntry) -> LogEntry:
        self._store[entry.tenant_id][entry.id] = entry
        return entry
