# tests/unit/test_log_service.py
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.domain.models import (
    DataSource,
    GeneralizedProduct,
    LogEntryCreate,
    Macronutrients,
)
from app.repositories.log_repository import InMemoryLogRepository
from app.services.log_service import LogService
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


@pytest.mark.asyncio
async def test_daily_hydration_only_counts_liquids():
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


@pytest.mark.asyncio
async def test_tenant_isolation():
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


@pytest.mark.asyncio
async def test_get_nutrition_range():
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


@pytest.mark.asyncio
async def test_get_hydration_range():
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
