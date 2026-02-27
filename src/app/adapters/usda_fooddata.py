# src/app/adapters/usda_fooddata.py
from __future__ import annotations

import logging
from decimal import Decimal

import httpx
from pydantic import BaseModel, Field

from app.domain.models import DataSource, GeneralizedProduct, Macronutrients, Micronutrients
from app.domain.ports import ExternalApiError, ProductNotFoundError, ProductSourcePort

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.nal.usda.gov/fdc/v1"

# USDA Nutrient Number Mapping
_NUTRIENT_MAP = {
    "calories":      {"ids": {1008}, "unit_factor": Decimal("1")},
    "protein":       {"ids": {1003}, "unit_factor": Decimal("1")},
    "carbohydrates": {"ids": {1005}, "unit_factor": Decimal("1")},
    "fat":           {"ids": {1004}, "unit_factor": Decimal("1")},
    "fiber":         {"ids": {1079}, "unit_factor": Decimal("1")},
    "sugar":         {"ids": {2000}, "unit_factor": Decimal("1")},
    "sodium":        {"ids": {1093}, "unit_factor": Decimal("1")},    # in mg
    "potassium":     {"ids": {1092}, "unit_factor": Decimal("1")},    # in mg
    "calcium":       {"ids": {1087}, "unit_factor": Decimal("1")},    # in mg
    "iron":          {"ids": {1089}, "unit_factor": Decimal("1")},    # in mg
    "vitamin_c":     {"ids": {1162}, "unit_factor": Decimal("1")},    # in mg
    "vitamin_d":     {"ids": {1110}, "unit_factor": Decimal("1")},    # in µg
}

_LIQUID_FOOD_CATEGORIES = frozenset({
    "Beverages", "Soups, Sauces, and Gravies"
})


class _UsdaNutrient(BaseModel):
    nutrient_id: int = Field(alias="nutrientId")
    name: str = Field(alias="nutrientName")
    amount: float | None = None

    model_config = {"populate_by_name": True}


class _UsdaFoodNutrient(BaseModel):
    nutrient: _UsdaNutrient
    amount: float | None = None


class _UsdaFoodItem(BaseModel):
    fdc_id: int = Field(alias="fdcId")
    description: str
    brand_owner: str | None = Field(default=None, alias="brandOwner")
    food_nutrients: list[_UsdaFoodNutrient] = Field(default_factory=list, alias="foodNutrients")
    food_category: str | None = Field(default=None, alias="foodCategory")

    model_config = {"populate_by_name": True}


class UsdaFoodDataAdapter(ProductSourcePort):
    """Adapter für die USDA FoodData Central API."""

    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        self._client = http_client
        self._api_key = api_key

    async def fetch_by_id(self, product_id: str) -> GeneralizedProduct:
        url = f"{_BASE_URL}/food/{product_id}"
        try:
            response = await self._client.get(
                url, params={"api_key": self._api_key}, timeout=10.0
            )
            if response.status_code == 404:
                raise ProductNotFoundError(product_id, "usda_fooddata")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ExternalApiError("usda_fooddata", str(e)) from e
        except httpx.RequestError as e:
            raise ExternalApiError("usda_fooddata", f"Connection error: {e}") from e

        raw = _UsdaFoodItem.model_validate(response.json())
        return self._normalize(raw)

    async def search(self, query: str, limit: int = 10) -> list[GeneralizedProduct]:
        url = f"{_BASE_URL}/foods/search"
        params = {"api_key": self._api_key, "query": query, "pageSize": limit}
        try:
            response = await self._client.get(url, params=params, timeout=15.0)
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            raise ExternalApiError("usda_fooddata", str(e)) from e

        foods = response.json().get("foods", [])
        result = []
        for food_data in foods:
            try:
                result.append(self._normalize(_UsdaFoodItem.model_validate(food_data)))
            except Exception:
                logger.warning("Skipping malformed USDA food item", exc_info=True)
        return result

    def _normalize(self, raw: _UsdaFoodItem) -> GeneralizedProduct:
        nutrient_values = self._extract_nutrients(raw.food_nutrients)
        is_liquid = raw.food_category in _LIQUID_FOOD_CATEGORIES

        macros = Macronutrients(
            calories_kcal=nutrient_values.get("calories", Decimal("0")),
            protein_g=nutrient_values.get("protein", Decimal("0")),
            carbohydrates_g=nutrient_values.get("carbohydrates", Decimal("0")),
            fat_g=nutrient_values.get("fat", Decimal("0")),
            fiber_g=nutrient_values.get("fiber"),
            sugar_g=nutrient_values.get("sugar"),
        )

        has_micros = any(k in nutrient_values for k in ("sodium", "potassium", "calcium", "iron"))
        micros = Micronutrients(
            sodium_mg=nutrient_values.get("sodium"),
            potassium_mg=nutrient_values.get("potassium"),
            calcium_mg=nutrient_values.get("calcium"),
            iron_mg=nutrient_values.get("iron"),
            vitamin_c_mg=nutrient_values.get("vitamin_c"),
            vitamin_d_ug=nutrient_values.get("vitamin_d"),
        ) if has_micros else None

        return GeneralizedProduct(
            id=str(raw.fdc_id),
            source=DataSource.USDA_FOODDATA,
            name=raw.description,
            brand=raw.brand_owner,
            macronutrients=macros,
            micronutrients=micros,
            is_liquid=is_liquid,
            volume_ml_per_100g=Decimal("100") if is_liquid else None,
        )

    @staticmethod
    def _extract_nutrients(food_nutrients: list[_UsdaFoodNutrient]) -> dict[str, Decimal]:
        values: dict[str, Decimal] = {}
        nutrient_id_to_key = {
            nid: key
            for key, meta in _NUTRIENT_MAP.items()
            for nid in meta["ids"]
        }
        for fn in food_nutrients:
            key = nutrient_id_to_key.get(fn.nutrient.nutrient_id)
            if key and fn.amount is not None:
                values[key] = Decimal(str(fn.amount))
        return values