from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.domain.models import DataSource, GeneralizedProduct, Macronutrients, Micronutrients
from app.main import app


@pytest.fixture
def mock_generalized_product():
    return GeneralizedProduct(
        id="test-product-123",
        source=DataSource.MANUAL,
        name="Test Apple",
        brand="Nature",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("52"),
            protein_g=Decimal("0.3"),
            carbohydrates_g=Decimal("14"),
            fat_g=Decimal("0.2"),
        ),
        micronutrients=Micronutrients(potassium_mg=Decimal("107")),
        is_liquid=False,
    )


def test_create_log_entry_success(client: TestClient, mock_generalized_product: GeneralizedProduct):
    # Mock den Service-Aufruf
    with patch(
        "app.services.log_service.LogService.create_entry", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = {
            "id": "new-log-id",
            "tenant_id": "tenant_alice",
            "log_date": "2023-10-27",
            "product": mock_generalized_product,
            "quantity_g": Decimal("150.5"),
            "consumed_at": "2023-10-27T10:00:00Z",
            "note": "Lunch snack",
        }

        payload = {
            "product_id": "test-product-123",
            "source": "manual",
            "quantity_g": 150.5,
            "note": "Lunch snack",
        }

        # Bypass security for integration test
        from app.core.security import get_tenant_id

        app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"

        try:
            response = client.post("/api/v1/logs/", json=payload, headers={"X-API-Key": "any"})
            assert response.status_code == 201
            data = response.json()
            assert data["id"] == "new-log-id"
        finally:
            app.dependency_overrides.clear()


def test_get_daily_log_empty(client: TestClient):
    from app.core.security import get_tenant_id

    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"
    try:
        response = client.get("/api/v1/logs/daily", headers={"X-API-Key": "any"})
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()


def test_health_check(client: TestClient):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_nutrition_range_success(client: TestClient):
    from app.core.security import get_tenant_id

    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"

    with patch(
        "app.services.log_service.LogService.get_nutrition_range", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = [
            {
                "log_date": "2025-01-01",
                "total_entries": 1,
                "totals": {
                    "calories_kcal": "100.00",
                    "protein_g": "10.00",
                    "carbohydrates_g": "50.00",
                    "fat_g": "5.00",
                },
            }
        ]

        try:
            response = client.get(
                "/api/v1/logs/range/nutrition",
                params={"from": "2025-01-01", "to": "2025-01-01"},
                headers={"X-API-Key": "any"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["log_date"] == "2025-01-01"
        finally:
            app.dependency_overrides.clear()


def test_get_range_validation_error(client: TestClient):
    from app.core.security import get_tenant_id

    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"

    try:
        # 'to' before 'from'
        response = client.get(
            "/api/v1/logs/range/nutrition",
            params={"from": "2025-01-02", "to": "2025-01-01"},
            headers={"X-API-Key": "any"},
        )
        assert response.status_code == 400

        # range too long
        response = client.get(
            "/api/v1/logs/range/nutrition",
            params={"from": "2025-01-01", "to": "2026-02-01"},
            headers={"X-API-Key": "any"},
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()
