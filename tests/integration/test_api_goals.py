from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_goals_repository
from app.core.security import get_tenant_id
from app.main import app


@pytest.fixture(autouse=True)
def clear_goals():
    # GoalsRepository is a singleton via @lru_cache in dependencies.py
    get_goals_repository()._goals.clear()
    yield
    get_goals_repository()._goals.clear()


@pytest.fixture
def alice_tenant():
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"
    yield "tenant_alice"
    app.dependency_overrides.clear()


def test_get_goals_default(client: TestClient, alice_tenant):
    response = client.get("/api/v1/goals/", headers={"X-API-Key": "any"})
    assert response.status_code == 200
    assert response.json() == {
        "calories_kcal": None,
        "protein_g": None,
        "carbohydrates_g": None,
        "fat_g": None,
        "water_ml": None,
    }


def test_replace_goals(client: TestClient, alice_tenant):
    goals = {
        "calories_kcal": "2500.0",
        "protein_g": "150.0",
        "carbohydrates_g": "300.0",
        "fat_g": "80.0",
        "water_ml": "3000.0",
    }
    response = client.put("/api/v1/goals/", headers={"X-API-Key": "any"}, json=goals)
    assert response.status_code == 200
    # The API might return "2500" instead of "2500.0" depending on Decimal serialization
    data = response.json()
    assert Decimal(data["calories_kcal"]) == Decimal("2500.0")


def test_patch_goals(client: TestClient, alice_tenant):
    # Set initial goals
    initial_goals = {"calories_kcal": "2000.0", "water_ml": "2000.0"}
    client.put("/api/v1/goals/", headers={"X-API-Key": "any"}, json=initial_goals)

    # Patch goals
    patch_data = {"calories_kcal": "2200.0"}
    response = client.patch("/api/v1/goals/", headers={"X-API-Key": "any"}, json=patch_data)
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["calories_kcal"]) == Decimal("2200.0")
    assert Decimal(data["water_ml"]) == Decimal("2000.0")
    assert data["protein_g"] is None


def test_get_progress_empty(client: TestClient, alice_tenant):
    today = date.today().isoformat()
    response = client.get(f"/api/v1/goals/progress?date={today}", headers={"X-API-Key": "any"})
    assert response.status_code == 200
    data = response.json()
    assert data["log_date"] == today
    assert data["calories"] is None
    assert data["water"] is None


def test_get_progress_with_goals(client: TestClient, alice_tenant):
    today = date.today().isoformat()
    # Set goals
    goals = {"calories_kcal": "2000.0", "water_ml": "2000.0"}
    client.put("/api/v1/goals/", headers={"X-API-Key": "any"}, json=goals)

    response = client.get(f"/api/v1/goals/progress?date={today}", headers={"X-API-Key": "any"})
    assert response.status_code == 200
    data = response.json()
    assert data["log_date"] == today
    assert Decimal(data["calories"]["target"]) == Decimal("2000.0")
    assert Decimal(data["calories"]["actual"]) == Decimal("0.0")
    assert Decimal(data["calories"]["remaining"]) == Decimal("2000.0")
    assert Decimal(data["calories"]["percent_achieved"]) == Decimal("0.0")

    assert Decimal(data["water"]["target"]) == Decimal("2000.0")
    assert Decimal(data["water"]["actual"]) == Decimal("0.0")
    assert Decimal(data["water"]["remaining"]) == Decimal("2000.0")
    assert Decimal(data["water"]["percent_achieved"]) == Decimal("0.0")


def test_tenant_isolation_goals(client: TestClient):
    # Alice sets goals
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"
    alice_goals = {"calories_kcal": "2000.0"}
    client.put("/api/v1/goals/", headers={"X-API-Key": "any"}, json=alice_goals)

    # Bob gets goals, should be default
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_bob"
    response = client.get("/api/v1/goals/", headers={"X-API-Key": "any"})
    assert response.status_code == 200
    assert response.json()["calories_kcal"] is None

    # Bob sets goals
    bob_goals = {"calories_kcal": "3000.0"}
    client.put("/api/v1/goals/", headers={"X-API-Key": "any"}, json=bob_goals)

    # Alice still has her goals
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"
    response = client.get("/api/v1/goals/", headers={"X-API-Key": "any"})
    assert response.status_code == 200
    assert Decimal(response.json()["calories_kcal"]) == Decimal("2000.0")
    app.dependency_overrides.clear()
