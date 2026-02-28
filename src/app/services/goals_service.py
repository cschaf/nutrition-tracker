from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.models import DailyGoals, DailyGoalsProgress, GoalProgress
from app.repositories.goals_repository import GoalsRepository
from app.services.log_service import LogService


class GoalsService:
    def __init__(self, repository: GoalsRepository, log_service: LogService) -> None:
        self._repo = repository
        self._log_service = log_service

    async def get_goals(self, tenant_id: str) -> DailyGoals:
        """Retrieves daily goals for a tenant, returns default if not found."""
        return self._repo.get(tenant_id) or DailyGoals()

    async def update_goals(self, tenant_id: str, goals: DailyGoals) -> DailyGoals:
        """Updates daily goals for a tenant."""
        return self._repo.save(tenant_id, goals)

    async def get_progress(self, tenant_id: str, log_date: date) -> DailyGoalsProgress:
        """Calculates progress against daily goals for a specific date."""
        goals = await self.get_goals(tenant_id)
        nutrition = await self._log_service.get_daily_nutrition(tenant_id, log_date)
        hydration = await self._log_service.get_daily_hydration(tenant_id, log_date)

        def _calc_progress(target: Decimal | None, actual: Decimal) -> GoalProgress | None:
            if target is None:
                return None
            remaining = max(Decimal("0"), target - actual)
            percent = (
                (actual / target * Decimal("100")).quantize(Decimal("0.1"))
                if target > 0
                else Decimal("100")
            )
            return GoalProgress(
                target=target,
                actual=actual,
                remaining=remaining,
                percent_achieved=percent,
            )

        return DailyGoalsProgress(
            log_date=log_date,
            calories=_calc_progress(goals.calories_kcal, nutrition.totals.calories_kcal),
            protein=_calc_progress(goals.protein_g, nutrition.totals.protein_g),
            carbohydrates=_calc_progress(goals.carbohydrates_g, nutrition.totals.carbohydrates_g),
            fat=_calc_progress(goals.fat_g, nutrition.totals.fat_g),
            water=_calc_progress(goals.water_ml, hydration.total_volume_ml),
        )
