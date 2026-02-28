# src/app/api/dependencies.py
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends

from app.adapters.manual import ManualProductAdapter
from app.adapters.open_food_facts import OpenFoodFactsAdapter
from app.adapters.usda_fooddata import UsdaFoodDataAdapter
from app.core.config import Settings, get_settings
from app.domain.models import DataSource
from app.domain.ports import ProductSourcePort
from app.repositories.base import AbstractLogRepository
from app.repositories.goals_repository import GoalsRepository
from app.repositories.manual_product_repository import ManualProductRepository
from app.repositories.sqlite_log_repository import SQLiteLogRepository
from app.repositories.template_repository import TemplateRepository
from app.services.barcode_service import BarcodeService
from app.services.export_service import ExportService
from app.services.goals_service import GoalsService
from app.services.log_service import LogService
from app.services.product_cache import ProductCache
from app.services.product_service import ProductService
from app.services.template_service import TemplateService


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


# Singleton Manual Product Repository
_manual_product_repo: ManualProductRepository | None = None


def get_manual_product_repository() -> ManualProductRepository:
    global _manual_product_repo
    if _manual_product_repo is None:
        _manual_product_repo = ManualProductRepository()
    return _manual_product_repo


def get_manual_adapter(
    repo: ManualProductRepository = Depends(get_manual_product_repository),
) -> ManualProductAdapter:
    return ManualProductAdapter(repository=repo)


def get_adapter_registry(
    off: OpenFoodFactsAdapter = Depends(get_off_adapter),
    usda: UsdaFoodDataAdapter = Depends(get_usda_adapter),
    manual: ManualProductAdapter = Depends(get_manual_adapter),
) -> dict[DataSource, ProductSourcePort]:
    """Liefert die Registry aller verfügbaren Adapter."""
    return {
        DataSource.OPEN_FOOD_FACTS: off,
        DataSource.USDA_FOODDATA: usda,
        DataSource.MANUAL: manual,
    }


def get_product_service(
    repo: ManualProductRepository = Depends(get_manual_product_repository),
) -> ProductService:
    return ProductService(manual_repo=repo)


def get_barcode_service(
    adapter_registry: dict[DataSource, ProductSourcePort] = Depends(get_adapter_registry),
    settings: Settings = Depends(get_settings),
) -> BarcodeService:
    return BarcodeService(
        adapter_registry=adapter_registry,
        lookup_order=settings.barcode_lookup_order,
    )


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


@lru_cache
def get_goals_repository() -> GoalsRepository:
    return GoalsRepository()


@lru_cache
def get_template_repository() -> TemplateRepository:
    return TemplateRepository()


def get_template_service(
    repository: TemplateRepository = Depends(get_template_repository),
    log_service: LogService = Depends(get_log_service),
) -> TemplateService:
    return TemplateService(repository=repository, log_service=log_service)


def get_goals_service(
    repository: GoalsRepository = Depends(get_goals_repository),
    log_service: LogService = Depends(get_log_service),
) -> GoalsService:
    return GoalsService(repository=repository, log_service=log_service)


def get_export_service() -> ExportService:
    return ExportService()


TenantIdDep = Annotated[str, Depends(get_settings)]  # wird in Endpoints via get_tenant_id genutzt
