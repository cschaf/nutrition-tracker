import time
from decimal import Decimal
from unittest.mock import patch

from app.domain.models import DataSource, GeneralizedProduct, Macronutrients
from app.services.product_cache import ProductCache


def test_cache_hit_and_miss() -> None:
    cache = ProductCache(ttl_seconds=60)
    product = GeneralizedProduct(
        id="123",
        source=DataSource.OPEN_FOOD_FACTS,
        name="Test Product",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("100"),
            protein_g=Decimal("10"),
            carbohydrates_g=Decimal("20"),
            fat_g=Decimal("5"),
        ),
    )

    # Miss
    assert cache.get(DataSource.OPEN_FOOD_FACTS, "123") is None

    # Set
    cache.set(DataSource.OPEN_FOOD_FACTS, "123", product)

    # Hit
    cached = cache.get(DataSource.OPEN_FOOD_FACTS, "123")
    assert cached == product


def test_cache_ttl_expiry() -> None:
    ttl = 10
    cache = ProductCache(ttl_seconds=ttl)
    product = GeneralizedProduct(
        id="123",
        source=DataSource.OPEN_FOOD_FACTS,
        name="Test Product",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("100"),
            protein_g=Decimal("10"),
            carbohydrates_g=Decimal("20"),
            fat_g=Decimal("5"),
        ),
    )

    now = time.time()
    with patch("time.time") as mock_time:
        mock_time.return_value = now
        cache.set(DataSource.OPEN_FOOD_FACTS, "123", product)

        # Still valid
        mock_time.return_value = now + ttl - 1
        assert cache.get(DataSource.OPEN_FOOD_FACTS, "123") == product

        # Expired
        mock_time.return_value = now + ttl + 1
        assert cache.get(DataSource.OPEN_FOOD_FACTS, "123") is None


def test_cache_different_sources() -> None:
    cache = ProductCache(ttl_seconds=60)
    product_off = GeneralizedProduct(
        id="123",
        source=DataSource.OPEN_FOOD_FACTS,
        name="OFF Product",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("100"),
            protein_g=Decimal("10"),
            carbohydrates_g=Decimal("20"),
            fat_g=Decimal("5"),
        ),
    )
    product_usda = GeneralizedProduct(
        id="123",
        source=DataSource.USDA_FOODDATA,
        name="USDA Product",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("200"),
            protein_g=Decimal("20"),
            carbohydrates_g=Decimal("40"),
            fat_g=Decimal("10"),
        ),
    )

    cache.set(DataSource.OPEN_FOOD_FACTS, "123", product_off)
    cache.set(DataSource.USDA_FOODDATA, "123", product_usda)

    assert cache.get(DataSource.OPEN_FOOD_FACTS, "123") == product_off
    assert cache.get(DataSource.USDA_FOODDATA, "123") == product_usda
