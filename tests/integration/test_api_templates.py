from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_adapter_registry
from app.core.config import get_settings
from app.domain.models import DataSource, GeneralizedProduct, Macronutrients, Micronutrients
from app.main import app


@pytest.fixture
def mock_adapter_registry():
    mock_adapter = AsyncMock()
    mock_adapter.fetch_by_id.return_value = GeneralizedProduct(
        id="test-product",
        source=DataSource.MANUAL,
        name="Test Product",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("100"),
            protein_g=Decimal("10"),
            carbohydrates_g=Decimal("20"),
            fat_g=Decimal("5"),
        ),
        micronutrients=Micronutrients(),
    )
    return {DataSource.MANUAL: mock_adapter}


@pytest.fixture
def override_adapter_registry(mock_adapter_registry):
    app.dependency_overrides[get_adapter_registry] = lambda: mock_adapter_registry
    yield
    app.dependency_overrides.pop(get_adapter_registry)


@pytest.fixture
def override_settings(test_settings):
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield
    app.dependency_overrides.pop(get_settings)


def test_template_lifecycle(
    client: TestClient, alice_headers: dict[str, str], override_adapter_registry, override_settings
):
    # 1. Create a template
    payload = {
        "name": "Quick Lunch",
        "entries": [
            {
                "product_id": "test-product",
                "source": "manual",
                "quantity_g": "200",
                "note": "Lunch note",
            }
        ],
    }
    response = client.post("/api/v1/templates/", json=payload, headers=alice_headers)
    assert response.status_code == 201
    template = response.json()
    assert template["name"] == "Quick Lunch"
    template_id = template["id"]

    # 2. Get all templates
    response = client.get("/api/v1/templates/", headers=alice_headers)
    assert response.status_code == 200
    templates = response.json()
    assert len(templates) == 1
    assert templates[0]["id"] == template_id

    # 3. Log the template
    response = client.post(
        f"/api/v1/templates/{template_id}/log?date=2025-01-15", headers=alice_headers
    )
    assert response.status_code == 200
    log_entries = response.json()
    assert len(log_entries) == 1
    assert log_entries[0]["product"]["id"] == "test-product"
    assert log_entries[0]["log_date"] == "2025-01-15"
    assert log_entries[0]["note"] == "Lunch note"

    # 4. Delete the template
    response = client.delete(f"/api/v1/templates/{template_id}", headers=alice_headers)
    assert response.status_code == 204

    # 5. Verify it's gone
    response = client.get("/api/v1/templates/", headers=alice_headers)
    assert len(response.json()) == 0


def test_template_not_found(client: TestClient, alice_headers: dict[str, str], override_settings):
    response = client.delete("/api/v1/templates/nonexistent", headers=alice_headers)
    assert response.status_code == 404

    response = client.post("/api/v1/templates/nonexistent/log", headers=alice_headers)
    assert response.status_code == 404
