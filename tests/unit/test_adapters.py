# tests/unit/test_adapters.py
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.adapters.manual import ManualProductAdapter
from app.adapters.open_food_facts import OpenFoodFactsAdapter
from app.adapters.usda_fooddata import UsdaFoodDataAdapter
from app.domain.models import DataSource, GeneralizedProduct, Macronutrients
from app.domain.ports import ExternalApiError, ProductNotFoundError
from app.repositories.manual_product_repository import ManualProductRepository

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


@pytest.mark.asyncio  # type: ignore[misc]
async def test_off_adapter_normalizes_beverage_correctly() -> None:
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


@pytest.mark.asyncio  # type: ignore[misc]
async def test_off_adapter_raises_not_found() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": 0, "product": None}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    adapter = OpenFoodFactsAdapter(http_client=mock_client)

    with pytest.raises(ProductNotFoundError):
        await adapter.fetch_by_id("0000000000000")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_off_adapter_detects_liquid_via_product_type() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": 1,
        "product": {
            "code": "111",
            "product_name": "Fruit Juice",
            "product_type": "beverages",
            "nutriments": {
                "energy-kcal_100g": 50.0,
                "proteins_100g": 0.5,
                "carbohydrates_100g": 12.0,
                "fat_100g": 0.0,
            },
        },
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    adapter = OpenFoodFactsAdapter(http_client=mock_client)
    product = await adapter.fetch_by_id("111")

    assert product.is_liquid is True
    assert product.volume_ml_per_100g == Decimal("100")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_off_adapter_fetch_http_error_raises_external_api_error() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Internal Server Error",
        request=httpx.Request("GET", "https://world.openfoodfacts.org/api/v0/product/123.json"),
        response=MagicMock(spec=httpx.Response),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    adapter = OpenFoodFactsAdapter(http_client=mock_client)

    with pytest.raises(ExternalApiError) as exc_info:
        await adapter.fetch_by_id("123")
    assert exc_info.value.source == "open_food_facts"


@pytest.mark.asyncio  # type: ignore[misc]
async def test_off_adapter_fetch_request_error_raises_external_api_error() -> None:
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.RequestError("Connection refused")

    adapter = OpenFoodFactsAdapter(http_client=mock_client)

    with pytest.raises(ExternalApiError) as exc_info:
        await adapter.fetch_by_id("123")
    assert exc_info.value.source == "open_food_facts"


_OFF_SEARCH_RESPONSE = {
    "products": [
        {
            "code": "9999",
            "product_name": "Search Apple",
            "brands": "FruitCo",
            "pnns_groups_1": "Fruits and vegetables",
            "nutriments": {
                "energy-kcal_100g": 52.0,
                "proteins_100g": 0.3,
                "carbohydrates_100g": 14.0,
                "fat_100g": 0.2,
            },
        }
    ]
}


@pytest.mark.asyncio  # type: ignore[misc]
async def test_off_adapter_search_returns_products() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = _OFF_SEARCH_RESPONSE
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    adapter = OpenFoodFactsAdapter(http_client=mock_client)
    results = await adapter.search("apple", limit=5)

    assert len(results) == 1
    assert results[0].id == "9999"
    assert results[0].source == DataSource.OPEN_FOOD_FACTS
    assert results[0].name == "Search Apple"
    assert results[0].is_liquid is False


@pytest.mark.asyncio  # type: ignore[misc]
async def test_off_adapter_search_raises_external_api_error() -> None:
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.RequestError("Timeout")

    adapter = OpenFoodFactsAdapter(http_client=mock_client)

    with pytest.raises(ExternalApiError):
        await adapter.search("apple")


# ---------------------------------------------------------------------------
# USDA FoodData Central Adapter
# ---------------------------------------------------------------------------

_USDA_FETCH_RESPONSE = {
    "fdcId": 1104647,
    "description": "WHOLE MILK",
    "brandOwner": "DAIRY BRAND",
    "foodCategory": "Dairy and Egg Products",
    "foodNutrients": [
        {"nutrient": {"nutrientId": 1008, "nutrientName": "Energy"}, "amount": 61.0},
        {"nutrient": {"nutrientId": 1003, "nutrientName": "Protein"}, "amount": 3.2},
        {"nutrient": {"nutrientId": 1005, "nutrientName": "Carbohydrate"}, "amount": 4.8},
        {"nutrient": {"nutrientId": 1004, "nutrientName": "Total lipid (fat)"}, "amount": 3.3},
        {"nutrient": {"nutrientId": 1093, "nutrientName": "Sodium, Na"}, "amount": 43.0},
    ],
}


@pytest.mark.asyncio  # type: ignore[misc]
async def test_usda_adapter_fetch_by_id_success() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = _USDA_FETCH_RESPONSE
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    adapter = UsdaFoodDataAdapter(http_client=mock_client, api_key="DEMO_KEY")
    product = await adapter.fetch_by_id("1104647")

    assert product.id == "1104647"
    assert product.source == DataSource.USDA_FOODDATA
    assert product.name == "WHOLE MILK"
    assert product.brand == "DAIRY BRAND"
    assert product.macronutrients.calories_kcal == Decimal("61.0")
    assert product.macronutrients.protein_g == Decimal("3.2")
    assert product.is_liquid is False
    assert product.micronutrients is not None
    assert product.micronutrients.sodium_mg == Decimal("43.0")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_usda_adapter_fetch_beverage_is_liquid() -> None:
    liquid_response = dict(_USDA_FETCH_RESPONSE)
    liquid_response["foodCategory"] = "Beverages"

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = liquid_response
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    adapter = UsdaFoodDataAdapter(http_client=mock_client, api_key="DEMO_KEY")
    product = await adapter.fetch_by_id("1104647")

    assert product.is_liquid is True
    assert product.volume_ml_per_100g == Decimal("100")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_usda_adapter_fetch_not_found() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 404
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    adapter = UsdaFoodDataAdapter(http_client=mock_client, api_key="DEMO_KEY")

    with pytest.raises(ProductNotFoundError) as exc_info:
        await adapter.fetch_by_id("9999999")
    assert exc_info.value.source == "usda_fooddata"


@pytest.mark.asyncio  # type: ignore[misc]
async def test_usda_adapter_fetch_http_error_raises_external_api_error() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Server Error",
        request=httpx.Request("GET", "https://api.nal.usda.gov/fdc/v1/food/123"),
        response=MagicMock(spec=httpx.Response),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    adapter = UsdaFoodDataAdapter(http_client=mock_client, api_key="DEMO_KEY")

    with pytest.raises(ExternalApiError) as exc_info:
        await adapter.fetch_by_id("123")
    assert exc_info.value.source == "usda_fooddata"


@pytest.mark.asyncio  # type: ignore[misc]
async def test_usda_adapter_search_returns_products() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "foods": [_USDA_FETCH_RESPONSE],
        "totalHits": 1,
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    adapter = UsdaFoodDataAdapter(http_client=mock_client, api_key="DEMO_KEY")
    results = await adapter.search("milk", limit=5)

    assert len(results) == 1
    assert results[0].source == DataSource.USDA_FOODDATA
    assert results[0].name == "WHOLE MILK"


@pytest.mark.asyncio  # type: ignore[misc]
async def test_usda_adapter_search_raises_external_api_error() -> None:
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.RequestError("Connection error")

    adapter = UsdaFoodDataAdapter(http_client=mock_client, api_key="DEMO_KEY")

    with pytest.raises(ExternalApiError):
        await adapter.search("milk")


# ---------------------------------------------------------------------------
# Manual Product Adapter
# ---------------------------------------------------------------------------


def _make_manual_product(product_id: str = "manual-1") -> GeneralizedProduct:
    return GeneralizedProduct(
        id=product_id,
        source=DataSource.MANUAL,
        name="Homemade Granola",
        brand="My Kitchen",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("430"),
            protein_g=Decimal("8"),
            carbohydrates_g=Decimal("65"),
            fat_g=Decimal("15"),
        ),
    )


@pytest.mark.asyncio  # type: ignore[misc]
async def test_manual_adapter_fetch_by_id_found() -> None:
    repo = ManualProductRepository()
    product = _make_manual_product("manual-1")
    repo.save(product)

    adapter = ManualProductAdapter(repository=repo)
    found = await adapter.fetch_by_id("manual-1")

    assert found.id == "manual-1"
    assert found.name == "Homemade Granola"
    assert found.source == DataSource.MANUAL


@pytest.mark.asyncio  # type: ignore[misc]
async def test_manual_adapter_fetch_by_id_not_found() -> None:
    repo = ManualProductRepository()
    adapter = ManualProductAdapter(repository=repo)

    with pytest.raises(ProductNotFoundError) as exc_info:
        await adapter.fetch_by_id("does-not-exist")
    assert exc_info.value.source == DataSource.MANUAL


@pytest.mark.asyncio  # type: ignore[misc]
async def test_manual_adapter_search_returns_matching_products() -> None:
    repo = ManualProductRepository()
    repo.save(_make_manual_product("m-1"))
    repo.save(
        GeneralizedProduct(
            id="m-2",
            source=DataSource.MANUAL,
            name="Banana Smoothie",
            macronutrients=Macronutrients(
                calories_kcal=Decimal("80"),
                protein_g=Decimal("1"),
                carbohydrates_g=Decimal("18"),
                fat_g=Decimal("0"),
            ),
        )
    )

    adapter = ManualProductAdapter(repository=repo)
    results = await adapter.search("granola")

    assert len(results) == 1
    assert results[0].id == "m-1"


@pytest.mark.asyncio  # type: ignore[misc]
async def test_manual_adapter_search_matches_brand() -> None:
    repo = ManualProductRepository()
    repo.save(_make_manual_product("m-1"))  # brand="My Kitchen"

    adapter = ManualProductAdapter(repository=repo)
    results = await adapter.search("my kitchen")

    assert len(results) == 1
    assert results[0].brand == "My Kitchen"
