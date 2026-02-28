from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status

from app.api.dependencies import (
    get_adapter_registry,
    get_barcode_service,
    get_product_service,
)
from app.core.security import get_tenant_id
from app.domain.models import DataSource, GeneralizedProduct, ManualProductCreate
from app.domain.ports import ExternalApiError, ProductNotFoundError, ProductSourcePort
from app.services.barcode_service import BarcodeService
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])

TenantDep = Annotated[str, Security(get_tenant_id)]
AdapterRegistryDep = Annotated[dict[DataSource, ProductSourcePort], Depends(get_adapter_registry)]
ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
BarcodeServiceDep = Annotated[BarcodeService, Depends(get_barcode_service)]


@router.get("/barcode/{barcode}", response_model=GeneralizedProduct)
async def lookup_barcode(
    tenant_id: TenantDep,
    service: BarcodeServiceDep,
    barcode: str,
) -> GeneralizedProduct:
    """
    Sucht ein Produkt anhand seines Barcodes in allen konfigurierten Quellen.
    """
    try:
        return await service.lookup(barcode)
    except ProductNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ExternalApiError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/search", response_model=list[GeneralizedProduct])
async def search_products(
    tenant_id: TenantDep,
    registry: AdapterRegistryDep,
    q: str,
    source: str,
    limit: int = Query(10, ge=1, le=20),
) -> list[GeneralizedProduct]:
    """
    Sucht nach Produkten in einer bestimmten Quelle.
    """
    try:
        source_enum = DataSource(source)
    except ValueError:
        available = ", ".join([s.value for s in DataSource])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source '{source}'. Available: {available}",
        )

    adapter = registry.get(source_enum)
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source '{source}' is not supported for search.",
        )

    try:
        return await adapter.search(query=q, limit=limit)
    except ExternalApiError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/", response_model=GeneralizedProduct, status_code=status.HTTP_201_CREATED)
async def create_manual_product(
    tenant_id: TenantDep,
    service: ProductServiceDep,
    payload: ManualProductCreate,
) -> GeneralizedProduct:
    """
    Erstellt ein manuelles Produkt.
    """
    return service.create_manual_product(payload)
