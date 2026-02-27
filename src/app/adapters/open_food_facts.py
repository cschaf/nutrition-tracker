# src/app/adapters/open_food_facts.py
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

import httpx
from pydantic import BaseModel, Field

from app.domain.models import (
    DataSource,
    GeneralizedProduct,
    Macronutrients,
    Micronutrients,
)
from app.domain.ports import ExternalApiError, ProductNotFoundError, ProductSourcePort

logger = logging.getLogger(__name__)

_BASE_URL = "https://world.openfoodfacts.org"

# ---------------------------------------------------------------------------
# Interne Rohdaten-Schemas (für typisiertes Parsing der OFF-Response)
# ---------------------------------------------------------------------------


class _OffNutriments(BaseModel):
    """Direkte Abbildung relevanter OFF-Felder. Alle optional, da OFF-Daten inkonsistent sind."""

    energy_kcal_100g: float | None = Field(default=None, alias="energy-kcal_100g")
    proteins_100g: float | None = None
    carbohydrates_100g: float | None = None
    fat_100g: float | None = None
    fiber_100g: float | None = None
    sugars_100g: float | None = None
    sodium_100g: float | None = None
    potassium_100g: float | None = None
    calcium_100g: float | None = None
    iron_100g: float | None = None

    model_config = {"populate_by_name": True}


class _OffProduct(BaseModel):
    code: str | None = None
    product_name: str | None = None
    brands: str | None = None
    nutriments: _OffNutriments = Field(default_factory=_OffNutriments)
    # OFF kategorisiert Flüssigkeiten über pnns_groups oder product_type
    pnns_groups_1: str | None = None
    product_type: str | None = None


class _OffResponse(BaseModel):
    status: int  # 1 = found, 0 = not found
    product: _OffProduct | None = None


# ---------------------------------------------------------------------------
# Adapter-Implementierung
# ---------------------------------------------------------------------------

_LIQUID_PNNS_GROUPS = frozenset({"Beverages"})
_LIQUID_PRODUCT_TYPES = frozenset({"beverages"})


def _safe_decimal(value: float | None, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return default


class OpenFoodFactsAdapter(ProductSourcePort):
    """
    Adapter für die Open Food Facts API.
    Normalisiert OFF-Rohdaten in das einheitliche GeneralizedProduct-Schema.
    """

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    async def fetch_by_id(self, product_id: str) -> GeneralizedProduct:
        """product_id entspricht dem EAN/UPC Barcode."""
        url = f"{_BASE_URL}/api/v0/product/{product_id}.json"
        try:
            response = await self._client.get(url, timeout=10.0)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ExternalApiError("open_food_facts", str(e)) from e
        except httpx.RequestError as e:
            raise ExternalApiError("open_food_facts", f"Connection error: {e}") from e

        raw = _OffResponse.model_validate(response.json())

        if raw.status == 0 or raw.product is None:
            raise ProductNotFoundError(product_id, "open_food_facts")

        return self._normalize(product_id, raw.product)

    async def search(self, query: str, limit: int = 10) -> list[GeneralizedProduct]:
        url = f"{_BASE_URL}/cgi/search.pl"
        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": limit,
            "fields": "code,product_name,brands,nutriments,pnns_groups_1,product_type",
        }
        try:
            response = await self._client.get(url, params=params, timeout=15.0)
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            raise ExternalApiError("open_food_facts", str(e)) from e

        data = response.json()
        products = []
        for raw_product in data.get("products", []):
            try:
                off_product = _OffProduct.model_validate(raw_product)
                if off_product.code:
                    products.append(self._normalize(off_product.code, off_product))
            except Exception:
                logger.warning("Skipping malformed product in OFF search results", exc_info=True)

        return products

    # ------------------------------------------------------------------
    # Private Normalisierungslogik
    # ------------------------------------------------------------------

    def _normalize(self, product_id: str, raw: _OffProduct) -> GeneralizedProduct:
        is_liquid = self._detect_liquid(raw)
        n = raw.nutriments

        macros = Macronutrients(
            calories_kcal=_safe_decimal(n.energy_kcal_100g),
            protein_g=_safe_decimal(n.proteins_100g),
            carbohydrates_g=_safe_decimal(n.carbohydrates_100g),
            fat_g=_safe_decimal(n.fat_100g),
            fiber_g=_safe_decimal(n.fiber_100g) if n.fiber_100g is not None else None,
            sugar_g=_safe_decimal(n.sugars_100g) if n.sugars_100g is not None else None,
        )

        micros: Micronutrients | None = None
        if any([n.sodium_100g, n.potassium_100g, n.calcium_100g, n.iron_100g]):
            # Sodium: OFF liefert Werte in Gramm, wir wollen Milligramm
            micros = Micronutrients(
                sodium_mg=_safe_decimal(n.sodium_100g) * 1000 if n.sodium_100g else None,
                potassium_mg=_safe_decimal(n.potassium_100g) * 1000 if n.potassium_100g else None,
                calcium_mg=_safe_decimal(n.calcium_100g) * 1000 if n.calcium_100g else None,
                iron_mg=_safe_decimal(n.iron_100g) * 1000 if n.iron_100g else None,
            )

        return GeneralizedProduct(
            id=product_id,
            source=DataSource.OPEN_FOOD_FACTS,
            name=raw.product_name or "Unknown Product",
            brand=raw.brands,
            barcode=product_id,
            macronutrients=macros,
            micronutrients=micros,
            is_liquid=is_liquid,
            volume_ml_per_100g=Decimal("100") if is_liquid else None,
        )

    @staticmethod
    def _detect_liquid(raw: _OffProduct) -> bool:
        return raw.pnns_groups_1 in _LIQUID_PNNS_GROUPS or bool(
            raw.product_type and raw.product_type.lower() in _LIQUID_PRODUCT_TYPES
        )
