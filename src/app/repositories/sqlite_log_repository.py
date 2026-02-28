from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CursorResult, Date, String, Text, delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.models import LogEntry
from app.repositories.base import AbstractLogRepository

if TYPE_CHECKING:
    pass


class Base(DeclarativeBase):
    pass


class LogEntryORM(Base):
    __tablename__ = "log_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    log_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    # Store the entire LogEntry as JSON for simplicity,
    # but could be normalized further if needed.
    # The requirement is to replace InMemoryLogRepository with same methods.
    data: Mapped[str] = mapped_column(Text, nullable=False)


class SQLiteLogRepository(AbstractLogRepository):
    def __init__(self, database_url: str) -> None:
        self.engine = create_async_engine(database_url)
        self.async_session_maker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialize(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def save(self, entry: LogEntry) -> LogEntry:
        async with self.async_session_maker() as session, session.begin():
            orm_entry = LogEntryORM(
                id=entry.id,
                tenant_id=entry.tenant_id,
                log_date=entry.log_date,
                data=entry.model_dump_json(),
            )
            session.add(orm_entry)
        return entry

    async def find_by_id(self, tenant_id: str, entry_id: str) -> LogEntry | None:
        async with self.async_session_maker() as session:
            result = await session.execute(
                select(LogEntryORM).where(
                    LogEntryORM.id == entry_id, LogEntryORM.tenant_id == tenant_id
                )
            )
            orm_entry = result.scalar_one_or_none()
            if orm_entry:
                return LogEntry.model_validate_json(orm_entry.data)
            return None

    async def find_by_date(self, tenant_id: str, log_date: date) -> list[LogEntry]:
        async with self.async_session_maker() as session:
            result = await session.execute(
                select(LogEntryORM).where(
                    LogEntryORM.log_date == log_date, LogEntryORM.tenant_id == tenant_id
                )
            )
            return [LogEntry.model_validate_json(row.data) for row in result.scalars()]

    async def find_by_date_range(
        self, tenant_id: str, start_date: date, end_date: date
    ) -> list[LogEntry]:
        async with self.async_session_maker() as session:
            result = await session.execute(
                select(LogEntryORM).where(
                    LogEntryORM.log_date >= start_date,
                    LogEntryORM.log_date <= end_date,
                    LogEntryORM.tenant_id == tenant_id,
                )
            )
            return [LogEntry.model_validate_json(row.data) for row in result.scalars()]

    async def delete(self, tenant_id: str, entry_id: str) -> bool:
        async with self.async_session_maker() as session, session.begin():
            result = await session.execute(
                delete(LogEntryORM).where(
                    LogEntryORM.id == entry_id, LogEntryORM.tenant_id == tenant_id
                )
            )
            if isinstance(result, CursorResult):
                return bool(result.rowcount > 0)
            return False

    async def update(self, entry: LogEntry) -> LogEntry:
        async with self.async_session_maker() as session, session.begin():
            result = await session.execute(
                select(LogEntryORM).where(
                    LogEntryORM.id == entry.id, LogEntryORM.tenant_id == entry.tenant_id
                )
            )
            orm_entry = result.scalar_one_or_none()
            if orm_entry:
                orm_entry.log_date = entry.log_date
                orm_entry.data = entry.model_dump_json()
            else:
                # If not found, we could raise an error or just save it.
                # InMemoryLogRepository.update just overwrites.
                orm_entry = LogEntryORM(
                    id=entry.id,
                    tenant_id=entry.tenant_id,
                    log_date=entry.log_date,
                    data=entry.model_dump_json(),
                )
                session.add(orm_entry)
        return entry
