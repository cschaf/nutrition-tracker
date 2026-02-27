# src/app/services/log_service.py
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from app.domain.models import (
    DailyHydrationSummary,
    DailyNutritionSummary,
    DataSource,
    LogEntry,
    LogEntryCreate,
    LogEntryUpdate,
    Macronutrients,
)
from app.domain.ports import ProductSourcePort
from app.repositories.log_repository import InMemoryLogRepository


class LogService:
    def __init__(
        self,
        adapter_registry: dict[DataSource, ProductSourcePort],
        repository: InMemoryLogRepository,
    ) -> None:
        self._adapters = adapter_registry
        self._repo = repository

    async def create_entry(self, tenant_id: str, payload: LogEntryCreate) -> LogEntry:
        adapter = self._adapters[payload.source]
        product = await adapter.fetch_by_id(payload.product_id)

        entry = LogEntry(
            tenant_id=tenant_id,
            product=product,
            quantity_g=payload.quantity_g,
            log_date=payload.log_date or datetime.now(UTC).date(),
            note=payload.note,
        )
        return self._repo.save(entry)

    def get_entries_for_date(self, tenant_id: str, log_date: date) -> list[LogEntry]:
        return self._repo.find_by_date(tenant_id, log_date)

    def get_entry(self, tenant_id: str, entry_id: str) -> LogEntry | None:
        return self._repo.find_by_id(tenant_id, entry_id)

    def update_entry(
        self, tenant_id: str, entry_id: str, payload: LogEntryUpdate
    ) -> LogEntry | None:
        entry = self._repo.find_by_id(tenant_id, entry_id)
        if not entry:
            return None
        updated = entry.model_copy(
            update={k: v for k, v in payload.model_dump(exclude_none=True).items()}
        )
        return self._repo.update(updated)

    def delete_entry(self, tenant_id: str, entry_id: str) -> bool:
        return self._repo.delete(tenant_id, entry_id)

    def get_daily_nutrition(self, tenant_id: str, log_date: date) -> DailyNutritionSummary:
        entries = self._repo.find_by_date(tenant_id, log_date)

        def _sum_field(field: str) -> Decimal:
            total = Decimal("0")
            for e in entries:
                val = getattr(e.scaled_macros, field)
                if val is not None:
                    total += val
            return total

        totals = Macronutrients(
            calories_kcal=_sum_field("calories_kcal"),
            protein_g=_sum_field("protein_g"),
            carbohydrates_g=_sum_field("carbohydrates_g"),
            fat_g=_sum_field("fat_g"),
            fiber_g=_sum_field("fiber_g"),
            sugar_g=_sum_field("sugar_g"),
        )
        return DailyNutritionSummary(log_date=log_date, total_entries=len(entries), totals=totals)

    def get_daily_hydration(self, tenant_id: str, log_date: date) -> DailyHydrationSummary:
        entries = self._repo.find_by_date(tenant_id, log_date)
        liquid_entries = [e for e in entries if e.product.is_liquid]
        total_ml = sum(
            (e.consumed_volume_ml for e in liquid_entries if e.consumed_volume_ml),
            Decimal("0"),
        )
        return DailyHydrationSummary(
            log_date=log_date,
            total_volume_ml=total_ml,
            contributing_entries=len(liquid_entries),
        )
