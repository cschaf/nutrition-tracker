from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.domain.models import DataSource
from app.main import app
from app.services.product_cache import ProductCache


def test_request_count_middleware() -> None:
    client = TestClient(app)

    # Get initial value (if any)
    def get_count(method: str, path: str, status_code: str) -> float:
        return (
            REGISTRY.get_sample_value(
                "http_requests_total", {"method": method, "path": path, "status_code": status_code}
            )
            or 0.0
        )

    initial = get_count("GET", "/healthz", "200")

    # Make a request
    response = client.get("/healthz")
    assert response.status_code == 200

    final = get_count("GET", "/healthz", "200")
    assert final == initial + 1


def test_metrics_endpoint_unauthenticated() -> None:
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text


def test_cache_metrics() -> None:
    cache = ProductCache(ttl_seconds=60)

    def get_hits() -> float:
        return REGISTRY.get_sample_value("cache_hits_total") or 0.0

    def get_misses() -> float:
        return REGISTRY.get_sample_value("cache_misses_total") or 0.0

    initial_hits = get_hits()
    initial_misses = get_misses()

    # Miss
    cache.get(DataSource.OPEN_FOOD_FACTS, "nonexistent")
    assert get_misses() == initial_misses + 1
    assert get_hits() == initial_hits

    # Hit
    from decimal import Decimal

    from app.domain.models import GeneralizedProduct, Macronutrients

    product = GeneralizedProduct(
        id="123",
        source=DataSource.OPEN_FOOD_FACTS,
        name="Test",
        barcode="123",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("0"),
            protein_g=Decimal("0"),
            carbohydrates_g=Decimal("0"),
            fat_g=Decimal("0"),
        ),
    )
    cache.set(DataSource.OPEN_FOOD_FACTS, "123", product)
    cache.get(DataSource.OPEN_FOOD_FACTS, "123")

    assert get_hits() == initial_hits + 1
    assert get_misses() == initial_misses + 1
