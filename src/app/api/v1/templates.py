from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Security, status

from app.api.dependencies import get_template_service
from app.core.security import get_tenant_id
from app.domain.models import LogEntry, MealTemplate, MealTemplateCreate
from app.services.template_service import TemplateService

router = APIRouter(prefix="/templates", tags=["Templates"])

TenantDep = Annotated[str, Security(get_tenant_id)]
ServiceDep = Annotated[TemplateService, Depends(get_template_service)]


@router.get("/", response_model=list[MealTemplate])
async def get_templates(
    tenant_id: TenantDep,
    service: ServiceDep,
) -> list[MealTemplate]:
    return await service.get_all(tenant_id)


@router.post("/", response_model=MealTemplate, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: MealTemplateCreate,
    tenant_id: TenantDep,
    service: ServiceDep,
) -> MealTemplate:
    return await service.create(tenant_id=tenant_id, payload=payload)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    tenant_id: TenantDep,
    service: ServiceDep,
) -> None:
    if not await service.delete(tenant_id=tenant_id, template_id=template_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")


@router.post("/{template_id}/log", response_model=list[LogEntry])
async def log_template(
    template_id: str,
    tenant_id: TenantDep,
    service: ServiceDep,
    date: date | None = None,
) -> list[LogEntry]:
    target_date = date or datetime.now(UTC).date()
    entries = await service.log_template(
        tenant_id=tenant_id, template_id=template_id, log_date=target_date
    )
    if not entries:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

    return entries
