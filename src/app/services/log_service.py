# src/app/services/log_service.py
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
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
from app.repositories.base import AbstractLogRepository
from app.repositories.goals_repository import GoalsRepository
from app.services.notification_service import NotificationService
from app.services.product_cache import ProductCache


class LogService:
    def __init__(
        self,
        adapter_registry: dict[DataSource, ProductSourcePort],
        repository: AbstractLogRepository,
        product_cache: ProductCache,
        notification_service: NotificationService | None = None,
        goals_repository: GoalsRepository | None = None,
    ) -> None:
        self._adapters = adapter_registry
        self._repo = repository
        self._cache = product_cache
        self._notification_service = notification_service
        self._goals_repo = goals_repository

    async def create_entry(self, tenant_id: str, payload: LogEntryCreate) -> LogEntry:
        # 1. Check cache
        product = self._cache.get(payload.source, payload.product_id)

        # 2. If miss, fetch from adapter and update cache
        if product is None:
            adapter = self._adapters[payload.source]
            product = await adapter.fetch_by_id(payload.product_id)
            self._cache.set(payload.source, payload.product_id, product)

        entry = LogEntry(
            tenant_id=tenant_id,
            product=product,
            quantity_g=payload.quantity_g,
            log_date=payload.log_date or datetime.now(UTC).date(),
            note=payload.note,
        )
        saved_entry = await self._repo.save(entry)
        await self._handle_notifications(tenant_id, saved_entry)
        return saved_entry

    async def _handle_notifications(self, tenant_id: str, entry: LogEntry) -> None:
        """Handles triggering notifications for new entries."""
        if not self._notification_service:
            return

        # 1. Check for first log of the day
        daily_entries = await self.get_entries_for_date(tenant_id, entry.log_date)
        if len(daily_entries) == 1:
            await self._notification_service.send(
                "Nutrition Tracker", f"Logging started for {entry.log_date}"
            )

        # 2. Check for calorie goal reached
        if self._goals_repo:
            goals = self._goals_repo.get(tenant_id)
            if goals and goals.calories_kcal is not None:
                summary = await self.get_daily_nutrition(tenant_id, entry.log_date)
                current_total = summary.totals.calories_kcal
                previous_total = current_total - entry.scaled_macros.calories_kcal

                if current_total >= goals.calories_kcal and previous_total < goals.calories_kcal:
                    await self._notification_service.send(
                        "Goal Reached!",
                        f"You have reached your daily calorie goal of {goals.calories_kcal} kcal!",
                    )

    async def get_entries_for_date(self, tenant_id: str, log_date: date) -> list[LogEntry]:
        return await self._repo.find_by_date(tenant_id, log_date)

    async def get_entry(self, tenant_id: str, entry_id: str) -> LogEntry | None:
        return await self._repo.find_by_id(tenant_id, entry_id)

    async def update_entry(
        self, tenant_id: str, entry_id: str, payload: LogEntryUpdate
    ) -> LogEntry | None:
        entry = await self._repo.find_by_id(tenant_id, entry_id)
        if not entry:
            return None
        updated = entry.model_copy(
            update={k: v for k, v in payload.model_dump(exclude_none=True).items()}
        )
        return await self._repo.update(updated)

    async def delete_entry(self, tenant_id: str, entry_id: str) -> bool:
        return await self._repo.delete(tenant_id, entry_id)

    async def get_daily_nutrition(self, tenant_id: str, log_date: date) -> DailyNutritionSummary:
        entries = await self._repo.find_by_date(tenant_id, log_date)
        return self._summarize_nutrition(log_date, entries)

    async def get_daily_hydration(self, tenant_id: str, log_date: date) -> DailyHydrationSummary:
        entries = await self._repo.find_by_date(tenant_id, log_date)
        return self._summarize_hydration(log_date, entries)

    async def get_nutrition_range(
        self, tenant_id: str, start_date: date, end_date: date
    ) -> list[DailyNutritionSummary]:
        all_entries = await self._repo.find_by_date_range(tenant_id, start_date, end_date)
        entries_by_date = self._group_by_date(all_entries)

        summaries = []
        curr = start_date
        while curr <= end_date:
            day_entries = entries_by_date.get(curr, [])
            summaries.append(self._summarize_nutrition(curr, day_entries))
            curr += timedelta(days=1)
        return summaries

    async def get_hydration_range(
        self, tenant_id: str, start_date: date, end_date: date
    ) -> list[DailyHydrationSummary]:
        all_entries = await self._repo.find_by_date_range(tenant_id, start_date, end_date)
        entries_by_date = self._group_by_date(all_entries)

        summaries = []
        curr = start_date
        while curr <= end_date:
            day_entries = entries_by_date.get(curr, [])
            summaries.append(self._summarize_hydration(curr, day_entries))
            curr += timedelta(days=1)
        return summaries

    def _group_by_date(self, entries: list[LogEntry]) -> dict[date, list[LogEntry]]:
        grouped: dict[date, list[LogEntry]] = {}
        for e in entries:
            grouped.setdefault(e.log_date, []).append(e)
        return grouped

    def _summarize_nutrition(
        self, log_date: date, entries: list[LogEntry]
    ) -> DailyNutritionSummary:
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

    def _summarize_hydration(
        self, log_date: date, entries: list[LogEntry]
    ) -> DailyHydrationSummary:
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
