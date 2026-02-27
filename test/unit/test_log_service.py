# tests/unit/test_log_service.py
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.domain.models import (
    DataSource, GeneralizedProduct, LogEntryCreate, Macronutrients,
)
from app.repositories.log_repository import InMemoryLogRepository
from app.services.log_service import LogService


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
    service = LogService(
        adapter_registry={DataSource.OPEN_FOOD_FACTS: mock_adapter}, repository=repo
    )

    payload = LogEntryCreate(
        product_id="test-123", source=DataSource.OPEN_FOOD_FACTS, quantity_g=Decimal("250")
    )
    await service.create_entry("tenant_alice", payload)

    summary = service.get_daily_hydration("tenant_alice", date.today())
    assert summary.total_volume_ml == Decimal("250.0")
    assert summary.contributing_entries == 1


@pytest.mark.asyncio
async def test_tenant_isolation():
    mock_adapter = AsyncMock()
    mock_adapter.fetch_by_id.return_value = _make_product()

    repo = InMemoryLogRepository()
    service = LogService(
        adapter_registry={DataSource.OPEN_FOOD_FACTS: mock_adapter}, repository=repo
    )

    payload = LogEntryCreate(
        product_id="test-123", source=DataSource.OPEN_FOOD_FACTS, quantity_g=Decimal("100")
    )
    await service.create_entry("tenant_alice", payload)

    # Bob sieht Alices Daten nicht
    bob_entries = service.get_entries_for_date("tenant_bob", date.today())
    assert len(bob_entries) == 0