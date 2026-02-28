# tests/unit/test_log_service.py
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models import (
    DailyGoals,
    DataSource,
    GeneralizedProduct,
    LogEntryCreate,
    LogEntryUpdate,
    Macronutrients,
)
from app.repositories.goals_repository import GoalsRepository
from app.repositories.log_repository import InMemoryLogRepository
from app.services.log_service import LogService
from app.services.notification_service import NotificationService
from app.services.product_cache import ProductCache


def _make_product(is_liquid: bool = False) -> GeneralizedProduct:
    return GeneralizedProduct(
        id="test-123",
        source=DataSource.OPEN_FOOD_FACTS,
        name="Test Product",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("100"),
            protein_g=Decimal("10"),
            carbohydrates_g=Decimal("50"),
            fat_g=Decimal("5"),
        ),
        is_liquid=is_liquid,
        volume_ml_per_100g=Decimal("100") if is_liquid else None,
    )


@pytest.mark.asyncio  # type: ignore[misc]
async def test_daily_hydration_only_counts_liquids() -> None:
    mock_adapter = AsyncMock()
    mock_adapter.fetch_by_id.return_value = _make_product(is_liquid=True)

    repo = InMemoryLogRepository()
    cache = ProductCache(ttl_seconds=60)
    service = LogService(
        adapter_registry={DataSource.OPEN_FOOD_FACTS: mock_adapter},
        repository=repo,
        product_cache=cache,
    )

    payload = LogEntryCreate(
        product_id="test-123", source=DataSource.OPEN_FOOD_FACTS, quantity_g=Decimal("250")
    )
    await service.create_entry("tenant_alice", payload)

    summary = await service.get_daily_hydration("tenant_alice", date.today())
    assert summary.total_volume_ml == Decimal("250.0")
    assert summary.contributing_entries == 1


@pytest.mark.asyncio  # type: ignore[misc]
async def test_tenant_isolation() -> None:
    mock_adapter = AsyncMock()
    mock_adapter.fetch_by_id.return_value = _make_product()

    repo = InMemoryLogRepository()
    cache = ProductCache(ttl_seconds=60)
    service = LogService(
        adapter_registry={DataSource.OPEN_FOOD_FACTS: mock_adapter},
        repository=repo,
        product_cache=cache,
    )

    payload = LogEntryCreate(
        product_id="test-123", source=DataSource.OPEN_FOOD_FACTS, quantity_g=Decimal("100")
    )
    await service.create_entry("tenant_alice", payload)

    # Bob sieht Alices Daten nicht
    bob_entries = await service.get_entries_for_date("tenant_bob", date.today())
    assert len(bob_entries) == 0


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_nutrition_range() -> None:
    mock_adapter = AsyncMock()
    mock_adapter.fetch_by_id.return_value = _make_product()

    repo = InMemoryLogRepository()
    cache = ProductCache(ttl_seconds=60)
    service = LogService(
        adapter_registry={DataSource.OPEN_FOOD_FACTS: mock_adapter},
        repository=repo,
        product_cache=cache,
    )

    d1 = date(2025, 1, 1)
    d2 = date(2025, 1, 2)

    await service.create_entry(
        "tenant_alice",
        LogEntryCreate(
            product_id="test-123",
            source=DataSource.OPEN_FOOD_FACTS,
            quantity_g=Decimal("100"),
            log_date=d1,
        ),
    )
    await service.create_entry(
        "tenant_alice",
        LogEntryCreate(
            product_id="test-123",
            source=DataSource.OPEN_FOOD_FACTS,
            quantity_g=Decimal("200"),
            log_date=d2,
        ),
    )

    summaries = await service.get_nutrition_range("tenant_alice", d1, d2)
    assert len(summaries) == 2
    assert summaries[0].log_date == d1
    assert summaries[0].totals.calories_kcal == Decimal("100.00")
    assert summaries[1].log_date == d2
    assert summaries[1].totals.calories_kcal == Decimal("200.00")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_hydration_range() -> None:
    mock_adapter = AsyncMock()
    mock_adapter.fetch_by_id.return_value = _make_product(is_liquid=True)

    repo = InMemoryLogRepository()
    cache = ProductCache(ttl_seconds=60)
    service = LogService(
        adapter_registry={DataSource.OPEN_FOOD_FACTS: mock_adapter},
        repository=repo,
        product_cache=cache,
    )

    d1 = date(2025, 1, 1)
    d2 = date(2025, 1, 2)

    await service.create_entry(
        "tenant_alice",
        LogEntryCreate(
            product_id="test-123",
            source=DataSource.OPEN_FOOD_FACTS,
            quantity_g=Decimal("100"),
            log_date=d1,
        ),
    )
    # Day 2 has no entries

    summaries = await service.get_hydration_range("tenant_alice", d1, d2)
    assert len(summaries) == 2
    assert summaries[0].log_date == d1
    assert summaries[0].total_volume_ml == Decimal("100.0")
    assert summaries[1].log_date == d2
    assert summaries[1].total_volume_ml == Decimal("0")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_entry_returns_existing_entry() -> None:
    mock_adapter = AsyncMock()
    mock_adapter.fetch_by_id.return_value = _make_product()

    repo = InMemoryLogRepository()
    cache = ProductCache(ttl_seconds=60)
    service = LogService(
        adapter_registry={DataSource.OPEN_FOOD_FACTS: mock_adapter},
        repository=repo,
        product_cache=cache,
    )

    payload = LogEntryCreate(
        product_id="test-123", source=DataSource.OPEN_FOOD_FACTS, quantity_g=Decimal("100")
    )
    created = await service.create_entry("tenant_alice", payload)

    found = await service.get_entry("tenant_alice", created.id)
    assert found is not None
    assert found.id == created.id


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_entry_returns_none_for_unknown() -> None:
    repo = InMemoryLogRepository()
    cache = ProductCache(ttl_seconds=60)
    service = LogService(
        adapter_registry={},
        repository=repo,
        product_cache=cache,
    )

    result = await service.get_entry("tenant_alice", "does-not-exist")
    assert result is None


@pytest.mark.asyncio  # type: ignore[misc]
async def test_update_entry_changes_quantity() -> None:
    mock_adapter = AsyncMock()
    mock_adapter.fetch_by_id.return_value = _make_product()

    repo = InMemoryLogRepository()
    cache = ProductCache(ttl_seconds=60)
    service = LogService(
        adapter_registry={DataSource.OPEN_FOOD_FACTS: mock_adapter},
        repository=repo,
        product_cache=cache,
    )

    payload = LogEntryCreate(
        product_id="test-123", source=DataSource.OPEN_FOOD_FACTS, quantity_g=Decimal("100")
    )
    created = await service.create_entry("tenant_alice", payload)

    update = LogEntryUpdate(quantity_g=Decimal("250"))
    updated = await service.update_entry("tenant_alice", created.id, update)

    assert updated is not None
    assert updated.quantity_g == Decimal("250")
    assert updated.id == created.id


@pytest.mark.asyncio  # type: ignore[misc]
async def test_update_entry_returns_none_for_unknown() -> None:
    repo = InMemoryLogRepository()
    cache = ProductCache(ttl_seconds=60)
    service = LogService(
        adapter_registry={},
        repository=repo,
        product_cache=cache,
    )

    update = LogEntryUpdate(quantity_g=Decimal("250"))
    result = await service.update_entry("tenant_alice", "does-not-exist", update)
    assert result is None


@pytest.mark.asyncio  # type: ignore[misc]
async def test_delete_entry_returns_true_on_success() -> None:
    mock_adapter = AsyncMock()
    mock_adapter.fetch_by_id.return_value = _make_product()

    repo = InMemoryLogRepository()
    cache = ProductCache(ttl_seconds=60)
    service = LogService(
        adapter_registry={DataSource.OPEN_FOOD_FACTS: mock_adapter},
        repository=repo,
        product_cache=cache,
    )

    payload = LogEntryCreate(
        product_id="test-123", source=DataSource.OPEN_FOOD_FACTS, quantity_g=Decimal("100")
    )
    created = await service.create_entry("tenant_alice", payload)

    deleted = await service.delete_entry("tenant_alice", created.id)
    assert deleted is True

    found = await service.get_entry("tenant_alice", created.id)
    assert found is None


@pytest.mark.asyncio  # type: ignore[misc]
async def test_delete_entry_returns_false_for_unknown() -> None:
    repo = InMemoryLogRepository()
    cache = ProductCache(ttl_seconds=60)
    service = LogService(
        adapter_registry={},
        repository=repo,
        product_cache=cache,
    )

    result = await service.delete_entry("tenant_alice", "does-not-exist")
    assert result is False


@pytest.mark.asyncio  # type: ignore[misc]
async def test_handle_notifications_sends_first_log_of_day() -> None:
    mock_adapter = AsyncMock()
    mock_adapter.fetch_by_id.return_value = _make_product()

    repo = InMemoryLogRepository()
    cache = ProductCache(ttl_seconds=60)
    mock_notification_service = MagicMock(spec=NotificationService)
    mock_notification_service.send = AsyncMock()

    service = LogService(
        adapter_registry={DataSource.OPEN_FOOD_FACTS: mock_adapter},
        repository=repo,
        product_cache=cache,
        notification_service=mock_notification_service,
    )

    payload = LogEntryCreate(
        product_id="test-123", source=DataSource.OPEN_FOOD_FACTS, quantity_g=Decimal("100")
    )
    await service.create_entry("tenant_alice", payload)

    mock_notification_service.send.assert_called_once()
    call_args = mock_notification_service.send.call_args
    assert "Logging started" in call_args.args[1]


@pytest.mark.asyncio  # type: ignore[misc]
async def test_handle_notifications_calorie_goal_reached() -> None:
    mock_adapter = AsyncMock()
    mock_adapter.fetch_by_id.return_value = _make_product()  # 100 kcal per 100g

    repo = InMemoryLogRepository()
    cache = ProductCache(ttl_seconds=60)
    mock_notification_service = MagicMock(spec=NotificationService)
    mock_notification_service.send = AsyncMock()

    goals_repo = GoalsRepository()
    goals_repo.save("tenant_alice", DailyGoals(calories_kcal=Decimal("100")))

    service = LogService(
        adapter_registry={DataSource.OPEN_FOOD_FACTS: mock_adapter},
        repository=repo,
        product_cache=cache,
        notification_service=mock_notification_service,
        goals_repository=goals_repo,
    )

    # Log exactly 100g of a 100kcal/100g product -> reaches the 100 kcal goal
    payload = LogEntryCreate(
        product_id="test-123", source=DataSource.OPEN_FOOD_FACTS, quantity_g=Decimal("100")
    )
    await service.create_entry("tenant_alice", payload)

    # send called twice: first-log and goal-reached
    assert mock_notification_service.send.call_count == 2
    titles = [call.args[0] for call in mock_notification_service.send.call_args_list]
    assert "Goal Reached!" in titles


@pytest.mark.asyncio  # type: ignore[misc]
async def test_handle_notifications_no_service_does_not_raise() -> None:
    mock_adapter = AsyncMock()
    mock_adapter.fetch_by_id.return_value = _make_product()

    repo = InMemoryLogRepository()
    cache = ProductCache(ttl_seconds=60)
    service = LogService(
        adapter_registry={DataSource.OPEN_FOOD_FACTS: mock_adapter},
        repository=repo,
        product_cache=cache,
        # no notification_service
    )

    payload = LogEntryCreate(
        product_id="test-123", source=DataSource.OPEN_FOOD_FACTS, quantity_g=Decimal("100")
    )
    # Should not raise
    await service.create_entry("tenant_alice", payload)
