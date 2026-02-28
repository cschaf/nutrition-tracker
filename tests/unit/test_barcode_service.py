from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.domain.models import DataSource, GeneralizedProduct, Macronutrients
from app.domain.ports import ExternalApiError, ProductNotFoundError, ProductSourcePort
from app.services.barcode_service import BarcodeService


@pytest.fixture
def mock_product() -> GeneralizedProduct:
    return GeneralizedProduct(
        id="123456",
        source=DataSource.OPEN_FOOD_FACTS,
        name="Test Product",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("100"),
            protein_g=Decimal("10"),
            carbohydrates_g=Decimal("20"),
            fat_g=Decimal("5"),
        ),
    )


@pytest.fixture
def off_adapter() -> AsyncMock:
    return AsyncMock(spec=ProductSourcePort)


@pytest.fixture
def usda_adapter() -> AsyncMock:
    return AsyncMock(spec=ProductSourcePort)


@pytest.fixture
def adapter_registry(
    off_adapter: AsyncMock, usda_adapter: AsyncMock
) -> dict[DataSource, ProductSourcePort]:
    return {
        DataSource.OPEN_FOOD_FACTS: off_adapter,
        DataSource.USDA_FOODDATA: usda_adapter,
    }


@pytest.fixture
def barcode_service(adapter_registry: dict[DataSource, ProductSourcePort]) -> BarcodeService:
    return BarcodeService(
        adapter_registry=adapter_registry,
        lookup_order=["open_food_facts", "usda_fooddata"],
    )


@pytest.mark.asyncio
async def test_found_in_first_adapter(
    barcode_service: BarcodeService,
    off_adapter: AsyncMock,
    usda_adapter: AsyncMock,
    mock_product: GeneralizedProduct,
) -> None:
    # OFF findet Produkt
    off_adapter.fetch_by_id.return_value = mock_product

    result = await barcode_service.lookup("123456")

    assert result == mock_product
    off_adapter.fetch_by_id.assert_called_once_with("123456")
    usda_adapter.fetch_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_fallback_to_second_adapter(
    barcode_service: BarcodeService,
    off_adapter: AsyncMock,
    usda_adapter: AsyncMock,
    mock_product: GeneralizedProduct,
) -> None:
    # OFF wirft ProductNotFoundError
    off_adapter.fetch_by_id.side_effect = ProductNotFoundError("123456", "open_food_facts")
    # USDA findet Produkt
    usda_adapter.fetch_by_id.return_value = mock_product.model_copy(
        update={"source": DataSource.USDA_FOODDATA}
    )

    result = await barcode_service.lookup("123456")

    assert result.source == DataSource.USDA_FOODDATA
    off_adapter.fetch_by_id.assert_called_once_with("123456")
    usda_adapter.fetch_by_id.assert_called_once_with("123456")


@pytest.mark.asyncio
async def test_not_found_anywhere(
    barcode_service: BarcodeService,
    off_adapter: AsyncMock,
    usda_adapter: AsyncMock,
) -> None:
    # Beide werfen ProductNotFoundError
    off_adapter.fetch_by_id.side_effect = ProductNotFoundError("123456", "open_food_facts")
    usda_adapter.fetch_by_id.side_effect = ProductNotFoundError("123456", "usda_fooddata")

    with pytest.raises(ProductNotFoundError) as excinfo:
        await barcode_service.lookup("123456")

    assert excinfo.value.source == "all_configured_sources"
    assert off_adapter.fetch_by_id.called
    assert usda_adapter.fetch_by_id.called


@pytest.mark.asyncio
async def test_external_api_error_propagates(
    barcode_service: BarcodeService,
    off_adapter: AsyncMock,
    usda_adapter: AsyncMock,
) -> None:
    # OFF wirft ExternalApiError
    off_adapter.fetch_by_id.side_effect = ExternalApiError("open_food_facts", "Network timeout")

    with pytest.raises(ExternalApiError) as excinfo:
        await barcode_service.lookup("123456")

    assert excinfo.value.source == "open_food_facts"
    usda_adapter.fetch_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_source_in_config_skipped(
    off_adapter: AsyncMock,
    adapter_registry: dict[DataSource, ProductSourcePort],
    mock_product: GeneralizedProduct,
) -> None:
    # Konfiguration enthält ungültige Quelle
    service = BarcodeService(
        adapter_registry=adapter_registry,
        lookup_order=["invalid_source", "open_food_facts"],
    )
    off_adapter.fetch_by_id.return_value = mock_product

    result = await service.lookup("123456")

    assert result == mock_product
    off_adapter.fetch_by_id.assert_called_once_with("123456")
