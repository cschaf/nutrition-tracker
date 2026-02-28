# tests/unit/test_models.py
from datetime import date
from decimal import Decimal

import pytest

from app.domain.models import (
    DataSource,
    DateRangeParams,
    GeneralizedProduct,
    LogEntry,
    Macronutrients,
    ManualProductCreate,
    Micronutrients,
)


def _make_product(
    calories: str = "200",
    protein: str = "10",
    carbs: str = "30",
    fat: str = "5",
    fiber: str | None = None,
    sugar: str | None = None,
    is_liquid: bool = False,
) -> GeneralizedProduct:
    return GeneralizedProduct(
        id="prod-1",
        source=DataSource.MANUAL,
        name="Test Product",
        macronutrients=Macronutrients(
            calories_kcal=Decimal(calories),
            protein_g=Decimal(protein),
            carbohydrates_g=Decimal(carbs),
            fat_g=Decimal(fat),
            fiber_g=Decimal(fiber) if fiber is not None else None,
            sugar_g=Decimal(sugar) if sugar is not None else None,
        ),
        is_liquid=is_liquid,
        volume_ml_per_100g=Decimal("100") if is_liquid else None,
    )


# ---------------------------------------------------------------------------
# LogEntry.scaled_macros
# ---------------------------------------------------------------------------


def test_scaled_macros_scales_proportionally():
    product = _make_product(calories="200", protein="10", carbs="30", fat="5")
    entry = LogEntry(
        tenant_id="alice",
        product=product,
        quantity_g=Decimal("50"),  # 50g = 50% of 100g
    )

    scaled = entry.scaled_macros
    assert scaled.calories_kcal == Decimal("100.00")
    assert scaled.protein_g == Decimal("5.00")
    assert scaled.carbohydrates_g == Decimal("15.00")
    assert scaled.fat_g == Decimal("2.50")


def test_scaled_macros_optional_fields_none_when_product_has_none():
    product = _make_product(fiber=None, sugar=None)
    entry = LogEntry(tenant_id="alice", product=product, quantity_g=Decimal("100"))

    scaled = entry.scaled_macros
    assert scaled.fiber_g is None
    assert scaled.sugar_g is None


def test_scaled_macros_optional_fields_scaled_when_present():
    product = _make_product(fiber="4", sugar="8")
    entry = LogEntry(tenant_id="alice", product=product, quantity_g=Decimal("200"))

    scaled = entry.scaled_macros
    assert scaled.fiber_g == Decimal("8.00")
    assert scaled.sugar_g == Decimal("16.00")


def test_scaled_macros_zero_optional_fields_not_lost():
    """Decimal('0') is falsy — ensure zero optional fields are preserved."""
    product = _make_product(fiber="0", sugar="0")
    entry = LogEntry(tenant_id="alice", product=product, quantity_g=Decimal("100"))

    scaled = entry.scaled_macros
    assert scaled.fiber_g == Decimal("0.00")
    assert scaled.sugar_g == Decimal("0.00")


# ---------------------------------------------------------------------------
# LogEntry.consumed_volume_ml
# ---------------------------------------------------------------------------


def test_consumed_volume_ml_for_liquid():
    product = _make_product(is_liquid=True)
    entry = LogEntry(tenant_id="alice", product=product, quantity_g=Decimal("250"))

    # 250g * (100ml / 100g) = 250ml
    assert entry.consumed_volume_ml == Decimal("250.0")


def test_consumed_volume_ml_for_non_liquid_is_none():
    product = _make_product(is_liquid=False)
    entry = LogEntry(tenant_id="alice", product=product, quantity_g=Decimal("100"))

    assert entry.consumed_volume_ml is None


# ---------------------------------------------------------------------------
# GeneralizedProduct validator: liquid_requires_volume
# ---------------------------------------------------------------------------


def test_generalized_product_liquid_without_volume_raises():
    with pytest.raises(ValueError, match="volume_ml_per_100g"):
        GeneralizedProduct(
            id="p1",
            source=DataSource.MANUAL,
            name="Mystery Liquid",
            macronutrients=Macronutrients(
                calories_kcal=Decimal("0"),
                protein_g=Decimal("0"),
                carbohydrates_g=Decimal("0"),
                fat_g=Decimal("0"),
            ),
            is_liquid=True,
            volume_ml_per_100g=None,
        )


def test_generalized_product_non_liquid_without_volume_is_valid():
    product = GeneralizedProduct(
        id="p1",
        source=DataSource.MANUAL,
        name="Solid Food",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("100"),
            protein_g=Decimal("5"),
            carbohydrates_g=Decimal("20"),
            fat_g=Decimal("3"),
        ),
        is_liquid=False,
    )
    assert product.volume_ml_per_100g is None


# ---------------------------------------------------------------------------
# ManualProductCreate validator: liquid_requires_volume
# ---------------------------------------------------------------------------


def test_manual_product_create_liquid_without_volume_raises():
    with pytest.raises(ValueError, match="volume_ml_per_100g"):
        ManualProductCreate(
            name="Juice",
            macronutrients=Macronutrients(
                calories_kcal=Decimal("40"),
                protein_g=Decimal("0"),
                carbohydrates_g=Decimal("10"),
                fat_g=Decimal("0"),
            ),
            is_liquid=True,
            volume_ml_per_100g=None,
        )


def test_manual_product_create_liquid_with_volume_is_valid():
    product = ManualProductCreate(
        name="Homemade Lemonade",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("30"),
            protein_g=Decimal("0"),
            carbohydrates_g=Decimal("8"),
            fat_g=Decimal("0"),
        ),
        is_liquid=True,
        volume_ml_per_100g=Decimal("100"),
    )
    assert product.volume_ml_per_100g == Decimal("100")


# ---------------------------------------------------------------------------
# DateRangeParams validator
# ---------------------------------------------------------------------------


def test_date_range_params_valid():
    dr = DateRangeParams(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
    assert dr.start_date == date(2025, 1, 1)
    assert dr.end_date == date(2025, 1, 31)


def test_date_range_params_same_day_valid():
    dr = DateRangeParams(start_date=date(2025, 6, 15), end_date=date(2025, 6, 15))
    assert dr.start_date == dr.end_date


def test_date_range_params_end_before_start_raises():
    with pytest.raises(ValueError, match="after or equal"):
        DateRangeParams(start_date=date(2025, 2, 1), end_date=date(2025, 1, 1))


def test_date_range_params_too_long_raises():
    with pytest.raises(ValueError, match="366 days"):
        DateRangeParams(start_date=date(2024, 1, 1), end_date=date(2025, 2, 2))


# ---------------------------------------------------------------------------
# Macronutrients / GeneralizedProduct immutability
# ---------------------------------------------------------------------------


def test_macronutrients_are_frozen():
    macros = Macronutrients(
        calories_kcal=Decimal("100"),
        protein_g=Decimal("5"),
        carbohydrates_g=Decimal("20"),
        fat_g=Decimal("3"),
    )
    with pytest.raises(Exception):
        macros.calories_kcal = Decimal("999")  # type: ignore[misc]


def test_micronutrients_default_all_none():
    micros = Micronutrients()
    assert micros.sodium_mg is None
    assert micros.potassium_mg is None
    assert micros.calcium_mg is None
    assert micros.iron_mg is None
    assert micros.vitamin_c_mg is None
    assert micros.vitamin_d_ug is None
