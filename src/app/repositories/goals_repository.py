from __future__ import annotations

from app.domain.models import DailyGoals


class GoalsRepository:
    def __init__(self) -> None:
        self._goals: dict[str, DailyGoals] = {}

    def get(self, tenant_id: str) -> DailyGoals | None:
        """Retrieves daily goals for a tenant."""
        return self._goals.get(tenant_id)

    def save(self, tenant_id: str, goals: DailyGoals) -> DailyGoals:
        """Saves daily goals for a tenant."""
        self._goals[tenant_id] = goals
        return goals
