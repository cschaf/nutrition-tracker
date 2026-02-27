# tests/unit/test_adapters.py
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.adapters.open_food_facts import OpenFoodFactsAdapter
from app.domain.models import DataSource
from app.domain.ports import ProductNotFoundError

_OFF_RESPONSE_BEVERAGE = {
    "status": 1,
    "product": {
        "code": "5449000000996",
        "product_name": "Coca-Cola Classic",
        "brands": "Coca-Cola",
        "pnns_groups_1": "Beverages",
        "nutriments": {
            "energy-kcal_100g": 42.0,
            "proteins_100g": 0.0,
            "carbohydrates_100g": 10.6,
            "fat_100g": 0.0,
            "sugars_100g": 10.6,
            "sodium_100g": 0.01,
        },
    },
}


@pytest.mark.asyncio
async def test_off_adapter_normalizes_beverage_correctly():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = _OFF_RESPONSE_BEVERAGE
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    adapter = OpenFoodFactsAdapter(http_client=mock_client)
    product = await adapter.fetch_by_id("5449000000996")

    assert product.source == DataSource.OPEN_FOOD_FACTS
    assert product.is_liquid is True
    assert product.volume_ml_per_100g == Decimal("100")
    assert product.macronutrients.calories_kcal == Decimal("42.0")
    assert product.macronutrients.carbohydrates_g == Decimal("10.6")
    # Sodium: OFF in Gramm, wir erwarten Milligramm
    assert product.micronutrients is not None
    assert product.micronutrients.sodium_mg == Decimal("10")  # 0.01g * 1000


@pytest.mark.asyncio
async def test_off_adapter_raises_not_found():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": 0, "product": None}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    adapter = OpenFoodFactsAdapter(http_client=mock_client)

    with pytest.raises(ProductNotFoundError):
        await adapter.fetch_by_id("0000000000000")
