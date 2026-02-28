# tests/unit/test_export_service.py
from datetime import UTC, date, datetime
from decimal import Decimal

from app.domain.models import (
    DataSource,
    GeneralizedProduct,
    LogEntry,
    Macronutrients,
    Micronutrients,
)
from app.services.export_service import ExportService


def test_generate_csv_header() -> None:
    service = ExportService()
    entries: list[LogEntry] = []

    csv_gen = service.generate_csv(entries)
    header = next(csv_gen)

    expected_header = (
        "date,time,product_name,brand,source,quantity_g,calories_kcal,"
        "protein_g,carbohydrates_g,fat_g,fiber_g,sugar_g,is_liquid,volume_ml,note\r\n"
    )
    assert header == expected_header


def test_generate_csv_with_data() -> None:
    service = ExportService()

    product = GeneralizedProduct(
        id="test-1",
        source=DataSource.MANUAL,
        name="Test Product",
        brand="Test Brand",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("100"),
            protein_g=Decimal("10"),
            carbohydrates_g=Decimal("20"),
            fat_g=Decimal("5"),
            fiber_g=Decimal("2"),
            sugar_g=Decimal("10"),
        ),
        micronutrients=Micronutrients(),
        is_liquid=False,
    )

    entry = LogEntry(
        tenant_id="alice",
        log_date=date(2024, 5, 20),
        consumed_at=datetime(2024, 5, 20, 12, 0, 0, tzinfo=UTC),
        product=product,
        quantity_g=Decimal("200"),
        note="Lunch",
    )

    csv_gen = service.generate_csv([entry])
    next(csv_gen)  # Skip header
    row = next(csv_gen)

    # 200g of 100kcal/100g -> 200kcal
    # protein 10 -> 20
    # carbs 20 -> 40
    # fat 5 -> 10
    # fiber 2 -> 4
    # sugar 10 -> 20

    expected_row = (
        "2024-05-20,12:00:00,Test Product,Test Brand,manual,200,"
        "200.00,20.00,40.00,10.00,4.00,20.00,false,,Lunch\r\n"
    )
    assert row == expected_row


def test_generate_csv_liquid() -> None:
    service = ExportService()

    product = GeneralizedProduct(
        id="test-liquid",
        source=DataSource.MANUAL,
        name="Water",
        brand=None,
        macronutrients=Macronutrients(
            calories_kcal=Decimal("0"),
            protein_g=Decimal("0"),
            carbohydrates_g=Decimal("0"),
            fat_g=Decimal("0"),
        ),
        is_liquid=True,
        volume_ml_per_100g=Decimal("100"),
    )

    entry = LogEntry(
        tenant_id="alice",
        log_date=date(2024, 5, 20),
        consumed_at=datetime(2024, 5, 20, 10, 0, 0, tzinfo=UTC),
        product=product,
        quantity_g=Decimal("250"),
    )

    csv_gen = service.generate_csv([entry])
    next(csv_gen)  # Skip header
    row = next(csv_gen)

    # 250g liquid with 100ml/100g -> 250ml
    expected_row = "2024-05-20,10:00:00,Water,,manual,250,0.00,0.00,0.00,0.00,,,true,250.0,\r\n"
    assert row == expected_row


def test_generate_csv_zero_values() -> None:
    service = ExportService()

    product = GeneralizedProduct(
        id="test-zero",
        source=DataSource.MANUAL,
        name="Zero Product",
        macronutrients=Macronutrients(
            calories_kcal=Decimal("0"),
            protein_g=Decimal("0"),
            carbohydrates_g=Decimal("0"),
            fat_g=Decimal("0"),
            fiber_g=Decimal("0"),
            sugar_g=Decimal("0"),
        ),
        is_liquid=True,
        volume_ml_per_100g=Decimal("0"),
    )

    entry = LogEntry(
        tenant_id="alice",
        log_date=date(2024, 5, 20),
        consumed_at=datetime(2024, 5, 20, 10, 0, 0, tzinfo=UTC),
        product=product,
        quantity_g=Decimal("100"),
    )

    csv_gen = service.generate_csv([entry])
    next(csv_gen)  # Skip header
    row = next(csv_gen)

    expected_row = (
        "2024-05-20,10:00:00,Zero Product,,manual,100,0.00,0.00,"
        "0.00,0.00,0.00,0.00,true,0.0,\r\n"
    )
    assert row == expected_row
