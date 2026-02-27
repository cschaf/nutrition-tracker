# src/app/domain/models.py
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------

class DataSource(str, Enum):
    OPEN_FOOD_FACTS = "open_food_facts"
    USDA_FOODDATA = "usda_fooddata"
    MANUAL = "manual"


class Macronutrients(BaseModel):
    calories_kcal: Decimal = Field(ge=0, description="Kilokalorien per 100g/100ml")
    protein_g: Decimal = Field(ge=0, description="Protein in Gramm per 100g/100ml")
    carbohydrates_g: Decimal = Field(ge=0, description="Kohlenhydrate in Gramm per 100g/100ml")
    fat_g: Decimal = Field(ge=0, description="Fett in Gramm per 100g/100ml")
    fiber_g: Decimal | None = Field(default=None, ge=0)
    sugar_g: Decimal | None = Field(default=None, ge=0)

    model_config = {"frozen": True}


class Micronutrients(BaseModel):
    sodium_mg: Decimal | None = Field(default=None, ge=0)
    potassium_mg: Decimal | None = Field(default=None, ge=0)
    calcium_mg: Decimal | None = Field(default=None, ge=0)
    iron_mg: Decimal | None = Field(default=None, ge=0)
    vitamin_c_mg: Decimal | None = Field(default=None, ge=0)
    vitamin_d_ug: Decimal | None = Field(default=None, ge=0)

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Aggregate: GeneralizedProduct
# Kernkonzept: Source-agnostisches, normalisiertes Produktmodell.
# ---------------------------------------------------------------------------

class GeneralizedProduct(BaseModel):
    """
    Einheitliches internes Produktmodell.
    Die Core-Domain ist vollständig von der Datenquelle entkoppelt.
    """
    id: str = Field(description="Source-spezifischer Identifier (z.B. Barcode oder USDA fdcId)")
    source: DataSource
    name: str = Field(min_length=1, max_length=512)
    brand: str | None = None
    barcode: str | None = None

    # Nährwertangaben immer per 100g oder 100ml
    macronutrients: Macronutrients
    micronutrients: Micronutrients | None = None

    # Hydration-Flag: entscheidet, ob Volumen für Hydration-Tracking gezählt wird
    is_liquid: bool = False
    volume_ml_per_100g: Decimal | None = Field(
        default=None,
        ge=0,
        description="Für Flüssigkeiten: Milliliter pro 100g (oft 100ml/100g = 1:1)"
    )

    @field_validator("volume_ml_per_100g", mode="after")
    @classmethod
    def liquid_requires_volume(cls, v: Decimal | None, info: object) -> Decimal | None:
        # Pydantic v2: info.data enthält bereits validierte Felder
        data = getattr(info, "data", {})
        if data.get("is_liquid") and v is None:
            raise ValueError("volume_ml_per_100g muss gesetzt sein, wenn is_liquid=True")
        return v

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Aggregate: LogEntry
# ---------------------------------------------------------------------------

class LogEntryId(str):
    """Typisierter Wrapper für LogEntry-IDs."""


class LogEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = Field(description="Aus dem API-Key abgeleitete Tenant-ID")
    log_date: date = Field(default_factory=lambda: datetime.now(timezone.utc).date())
    product: GeneralizedProduct
    quantity_g: Decimal = Field(
        gt=0,
        description="Konsumierte Menge in Gramm (auch für Flüssigkeiten als Referenzgewicht)"
    )
    consumed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    note: str | None = Field(default=None, max_length=1024)

    @property
    def scaled_macros(self) -> Macronutrients:
        """Berechnet die absoluten Nährwerte basierend auf der tatsächlichen Menge."""
        factor = self.quantity_g / Decimal("100")
        m = self.product.macronutrients
        return Macronutrients(
            calories_kcal=(m.calories_kcal * factor).quantize(Decimal("0.01")),
            protein_g=(m.protein_g * factor).quantize(Decimal("0.01")),
            carbohydrates_g=(m.carbohydrates_g * factor).quantize(Decimal("0.01")),
            fat_g=(m.fat_g * factor).quantize(Decimal("0.01")),
            fiber_g=(m.fiber_g * factor).quantize(Decimal("0.01")) if m.fiber_g else None,
            sugar_g=(m.sugar_g * factor).quantize(Decimal("0.01")) if m.sugar_g else None,
        )

    @property
    def consumed_volume_ml(self) -> Decimal | None:
        """Liefert die konsumierte Flüssigkeit in ml, nur wenn is_liquid=True."""
        if not self.product.is_liquid or self.product.volume_ml_per_100g is None:
            return None
        factor = self.quantity_g / Decimal("100")
        return (self.product.volume_ml_per_100g * factor).quantize(Decimal("0.1"))


# ---------------------------------------------------------------------------
# API Request/Response Schemas
# ---------------------------------------------------------------------------

class LogEntryCreate(BaseModel):
    product_id: str = Field(description="Produkt-ID aus der externen Quelle")
    source: DataSource
    quantity_g: Decimal = Field(gt=0)
    log_date: date | None = None
    note: str | None = Field(default=None, max_length=1024)


class LogEntryUpdate(BaseModel):
    quantity_g: Decimal | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=1024)


class DailyNutritionSummary(BaseModel):
    log_date: date
    total_entries: int
    totals: Macronutrients


class DailyHydrationSummary(BaseModel):
    log_date: date
    total_volume_ml: Decimal
    contributing_entries: int