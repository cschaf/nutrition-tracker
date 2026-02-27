# src/app/api/dependencies.py
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends

from app.adapters.open_food_facts import OpenFoodFactsAdapter
from app.adapters.usda_fooddata import UsdaFoodDataAdapter
from app.core.config import Settings, get_settings
from app.domain.models import DataSource
from app.domain.ports import ProductSourcePort
from app.repositories.base import AbstractLogRepository
from app.repositories.sqlite_log_repository import SQLiteLogRepository
from app.services.log_service import LogService
from app.services.product_cache import ProductCache


# Shared HTTP Client (Connection Pooling)
@lru_cache
def get_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": "NutritionTracker/1.0 (homelab)"},
        follow_redirects=True,
    )


def get_off_adapter(
    client: httpx.AsyncClient = Depends(get_http_client),
) -> OpenFoodFactsAdapter:
    return OpenFoodFactsAdapter(http_client=client)


def get_usda_adapter(
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings),
) -> UsdaFoodDataAdapter:
    return UsdaFoodDataAdapter(http_client=client, api_key=settings.usda_api_key)


def get_adapter_registry(
    off: OpenFoodFactsAdapter = Depends(get_off_adapter),
    usda: UsdaFoodDataAdapter = Depends(get_usda_adapter),
) -> dict[DataSource, ProductSourcePort]:
    """Liefert die Registry aller verfügbaren Adapter."""
    return {
        DataSource.OPEN_FOOD_FACTS: off,
        DataSource.USDA_FOODDATA: usda,
    }


# Singleton Product Cache
_product_cache: ProductCache | None = None


def get_product_cache(
    settings: Settings = Depends(get_settings),
) -> ProductCache:
    global _product_cache
    if _product_cache is None:
        _product_cache = ProductCache(ttl_seconds=settings.cache_ttl_seconds)
    return _product_cache


# Singleton Repository (Initialisiert beim ersten Zugriff)
_repository: AbstractLogRepository | None = None


async def get_log_repository(
    settings: Settings = Depends(get_settings),
) -> AbstractLogRepository:
    global _repository
    if _repository is None:
        repo = SQLiteLogRepository(database_url=settings.database_url)
        await repo.initialize()
        _repository = repo
    return _repository


def get_log_service(
    adapter_registry: dict[DataSource, ProductSourcePort] = Depends(get_adapter_registry),
    repository: AbstractLogRepository = Depends(get_log_repository),
    product_cache: ProductCache = Depends(get_product_cache),
) -> LogService:
    return LogService(
        adapter_registry=adapter_registry, repository=repository, product_cache=product_cache
    )


TenantIdDep = Annotated[str, Depends(get_settings)]  # wird in Endpoints via get_tenant_id genutzt
