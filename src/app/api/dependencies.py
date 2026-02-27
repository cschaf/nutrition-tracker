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
from app.repositories.log_repository import InMemoryLogRepository
from app.services.log_service import LogService


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


# Singleton Repository (für Homelab: In-Memory; austauschbar gegen DB-Implementierung)
_repository = InMemoryLogRepository()


def get_log_repository() -> InMemoryLogRepository:
    return _repository


def get_log_service(
    adapter_registry: dict[DataSource, ProductSourcePort] = Depends(get_adapter_registry),
    repository: InMemoryLogRepository = Depends(get_log_repository),
) -> LogService:
    return LogService(adapter_registry=adapter_registry, repository=repository)


TenantIdDep = Annotated[str, Depends(get_settings)]  # wird in Endpoints via get_tenant_id genutzt
