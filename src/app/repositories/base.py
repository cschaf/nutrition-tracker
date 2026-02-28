from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.models import LogEntry


class AbstractLogRepository(ABC):
    @abstractmethod
    async def save(self, entry: LogEntry) -> LogEntry:
        """Saves a new log entry."""
        ...

    @abstractmethod
    async def find_by_id(self, tenant_id: str, entry_id: str) -> LogEntry | None:
        """Finds a log entry by ID and tenant ID."""
        ...

    @abstractmethod
    async def find_by_date(self, tenant_id: str, log_date: date) -> list[LogEntry]:
        """Finds all log entries for a specific date and tenant ID."""
        ...

    @abstractmethod
    async def find_by_date_range(
        self, tenant_id: str, start_date: date, end_date: date
    ) -> list[LogEntry]:
        """Finds all log entries within a date range (inclusive) for a tenant ID."""
        ...

    @abstractmethod
    async def delete(self, tenant_id: str, entry_id: str) -> bool:
        """Deletes a log entry by ID and tenant ID. Returns True if deleted."""
        ...

    @abstractmethod
    async def update(self, entry: LogEntry) -> LogEntry:
        """Updates an existing log entry."""
        ...
