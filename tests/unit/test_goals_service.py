from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models import (
    DailyGoals,
    DailyHydrationSummary,
    DailyNutritionSummary,
    Macronutrients,
)
from app.repositories.goals_repository import GoalsRepository
from app.services.goals_service import GoalsService
from app.services.log_service import LogService


@pytest.fixture  # type: ignore[misc]
def mock_repo() -> MagicMock:
    return MagicMock(spec=GoalsRepository)


@pytest.fixture  # type: ignore[misc]
def mock_log_service() -> MagicMock:
    return MagicMock(spec=LogService)


@pytest.fixture  # type: ignore[misc]
def goals_service(mock_repo: MagicMock, mock_log_service: MagicMock) -> GoalsService:
    return GoalsService(repository=mock_repo, log_service=mock_log_service)


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_goals_returns_default_if_none(
    goals_service: GoalsService, mock_repo: MagicMock
) -> None:
    mock_repo.get.return_value = None
    result = await goals_service.get_goals("tenant_1")
    assert result == DailyGoals()
    mock_repo.get.assert_called_once_with("tenant_1")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_goals_returns_saved_goals(
    goals_service: GoalsService, mock_repo: MagicMock
) -> None:
    goals = DailyGoals(calories_kcal=Decimal("2000"))
    mock_repo.get.return_value = goals
    result = await goals_service.get_goals("tenant_1")
    assert result == goals


@pytest.mark.asyncio  # type: ignore[misc]
async def test_update_goals(goals_service: GoalsService, mock_repo: MagicMock) -> None:
    goals = DailyGoals(calories_kcal=Decimal("2500"))
    mock_repo.save.return_value = goals
    result = await goals_service.update_goals("tenant_1", goals)
    assert result == goals
    mock_repo.save.assert_called_once_with("tenant_1", goals)


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_progress(
    goals_service: GoalsService, mock_repo: MagicMock, mock_log_service: MagicMock
) -> None:
    tenant_id = "tenant_1"
    today = date.today()

    goals = DailyGoals(calories_kcal=Decimal("2000"), water_ml=Decimal("2000"))
    mock_repo.get.return_value = goals

    nutrition = DailyNutritionSummary(
        log_date=today,
        total_entries=1,
        totals=Macronutrients(
            calories_kcal=Decimal("1000"),
            protein_g=Decimal("50"),
            carbohydrates_g=Decimal("100"),
            fat_g=Decimal("30"),
        ),
    )
    mock_log_service.get_daily_nutrition = AsyncMock(return_value=nutrition)

    hydration = DailyHydrationSummary(
        log_date=today, total_volume_ml=Decimal("1500"), contributing_entries=2
    )
    mock_log_service.get_daily_hydration = AsyncMock(return_value=hydration)

    progress = await goals_service.get_progress(tenant_id, today)

    assert progress.log_date == today
    assert progress.calories is not None
    assert progress.calories.target == Decimal("2000")
    assert progress.calories.actual == Decimal("1000")
    assert progress.calories.remaining == Decimal("1000")
    assert progress.calories.percent_achieved == Decimal("50.0")

    assert progress.water is not None
    assert progress.water.target == Decimal("2000")
    assert progress.water.actual == Decimal("1500")
    assert progress.water.remaining == Decimal("500")
    assert progress.water.percent_achieved == Decimal("75.0")

    assert progress.protein is None
    assert progress.carbohydrates is None
    assert progress.fat is None
