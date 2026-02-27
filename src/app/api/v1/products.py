from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status

from app.api.dependencies import get_adapter_registry
from app.core.security import get_tenant_id
from app.domain.models import DataSource, GeneralizedProduct
from app.domain.ports import ExternalApiError, ProductSourcePort

router = APIRouter(prefix="/products", tags=["Products"])

TenantDep = Annotated[str, Security(get_tenant_id)]
AdapterRegistryDep = Annotated[
    dict[DataSource, ProductSourcePort], Depends(get_adapter_registry)
]


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
