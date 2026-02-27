from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.domain.models import DataSource, GeneralizedProduct, Macronutrients
from app.main import app


@pytest.fixture
def mock_adapter_registry():
    off_adapter = AsyncMock()
    usda_adapter = AsyncMock()
    # We don't want the real search to be called because it uses the real httpx client
    # which might be closed or try to hit real network.
    registry = {
        DataSource.OPEN_FOOD_FACTS: off_adapter,
        DataSource.USDA_FOODDATA: usda_adapter,
    }
    yield registry


def test_search_products_off_success(
    client: TestClient, alice_headers: dict, mock_adapter_registry: dict
):
    # Setup
    mock_product = GeneralizedProduct(
        id="123",
        source=DataSource.OPEN_FOOD_FACTS,
        name="Test Product",
        macronutrients=Macronutrients(
            calories_kcal=100, protein_g=10, carbohydrates_g=20, fat_g=5
        ),
    )
    off_adapter = mock_adapter_registry[DataSource.OPEN_FOOD_FACTS]
    off_adapter.search.return_value = [mock_product]

    from app.api.dependencies import get_adapter_registry
    from app.core.security import get_tenant_id
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"
    app.dependency_overrides[get_adapter_registry] = lambda: mock_adapter_registry

    try:
        # Execute
        response = client.get(
            "/api/v1/products/search?q=apple&source=open_food_facts", headers=alice_headers
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "123"
        assert data[0]["source"] == "open_food_facts"
        off_adapter.search.assert_called_once_with(query="apple", limit=10)
    finally:
        app.dependency_overrides.clear()


def test_search_products_usda_success(
    client: TestClient, alice_headers: dict, mock_adapter_registry: dict
):
    # Setup
    mock_product = GeneralizedProduct(
        id="456",
        source=DataSource.USDA_FOODDATA,
        name="USDA Product",
        macronutrients=Macronutrients(
            calories_kcal=200, protein_g=5, carbohydrates_g=40, fat_g=2
        ),
    )
    usda_adapter = mock_adapter_registry[DataSource.USDA_FOODDATA]
    usda_adapter.search.return_value = [mock_product]

    from app.api.dependencies import get_adapter_registry
    from app.core.security import get_tenant_id
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"
    app.dependency_overrides[get_adapter_registry] = lambda: mock_adapter_registry

    try:
        # Execute
        response = client.get(
            "/api/v1/products/search?q=banana&source=usda_fooddata&limit=5", headers=alice_headers
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "456"
        assert data[0]["source"] == "usda_fooddata"
        usda_adapter.search.assert_called_once_with(query="banana", limit=5)
    finally:
        app.dependency_overrides.clear()


def test_search_products_invalid_source(client: TestClient, alice_headers: dict):
    from app.core.security import get_tenant_id
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"
    try:
        response = client.get(
            "/api/v1/products/search?q=apple&source=invalid_source", headers=alice_headers
        )
        assert response.status_code == 400
        assert "Invalid source" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_search_products_unsupported_source_for_search(
    client: TestClient, alice_headers: dict, mock_adapter_registry: dict
):
    from app.core.security import get_tenant_id
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"

    # Create a registry without USDA adapter
    registry_without_usda = {
        DataSource.OPEN_FOOD_FACTS: mock_adapter_registry[DataSource.OPEN_FOOD_FACTS],
    }
    from app.api.dependencies import get_adapter_registry
    app.dependency_overrides[get_adapter_registry] = lambda: registry_without_usda

    try:
        response = client.get(
            "/api/v1/products/search?q=apple&source=usda_fooddata", headers=alice_headers
        )
        assert response.status_code == 400
        assert "not supported for search" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_search_products_unauthorized(client: TestClient):
    # No dependency override here to test real security
    response = client.get("/api/v1/products/search?q=apple&source=open_food_facts")
    assert response.status_code == 401


def test_search_products_external_api_error(
    client: TestClient, alice_headers: dict, mock_adapter_registry: dict
):
    from app.api.dependencies import get_adapter_registry
    from app.core.security import get_tenant_id
    from app.domain.ports import ExternalApiError

    off_adapter = mock_adapter_registry[DataSource.OPEN_FOOD_FACTS]
    off_adapter.search.side_effect = ExternalApiError("open_food_facts", "API Down")
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"
    app.dependency_overrides[get_adapter_registry] = lambda: mock_adapter_registry

    try:
        response = client.get(
            "/api/v1/products/search?q=apple&source=open_food_facts", headers=alice_headers
        )

        assert response.status_code == 502
        assert "External API error" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_search_products_limit_validation(client: TestClient, alice_headers: dict):
    from app.core.security import get_tenant_id
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"
    try:
        # Too small
        response = client.get(
            "/api/v1/products/search?q=apple&source=open_food_facts&limit=0", headers=alice_headers
        )
        assert response.status_code == 422

        # Too large
        response = client.get(
            "/api/v1/products/search?q=apple&source=open_food_facts&limit=21", headers=alice_headers
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
