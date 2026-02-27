# src/app/api/v1/logs.py
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Security, status

from app.api.dependencies import get_log_service
from app.core.security import get_tenant_id
from app.domain.models import (
    DailyHydrationSummary,
    DailyNutritionSummary,
    LogEntry,
    LogEntryCreate,
    LogEntryUpdate,
)
from app.services.log_service import LogService

router = APIRouter(prefix="/logs", tags=["Logs"])

TenantDep = Annotated[str, Security(get_tenant_id)]
ServiceDep = Annotated[LogService, Depends(get_log_service)]


@router.post("/", response_model=LogEntry, status_code=status.HTTP_201_CREATED)
async def create_log_entry(
    payload: LogEntryCreate,
    tenant_id: TenantDep,
    service: ServiceDep,
) -> LogEntry:
    return await service.create_entry(tenant_id=tenant_id, payload=payload)


@router.get("/daily", response_model=list[LogEntry])
def get_daily_log(
    service: ServiceDep,
    log_date: date | None = None,
    tenant_id: TenantDep = "",
) -> list[LogEntry]:
    target = log_date or datetime.now(UTC).date()
    return service.get_entries_for_date(tenant_id=tenant_id, log_date=target)


@router.get("/{entry_id}", response_model=LogEntry)
def get_log_entry(entry_id: str, tenant_id: TenantDep, service: ServiceDep) -> LogEntry:
    entry = service.get_entry(tenant_id=tenant_id, entry_id=entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found.")
    return entry


@router.patch("/{entry_id}", response_model=LogEntry)
def update_log_entry(
    entry_id: str,
    payload: LogEntryUpdate,
    tenant_id: TenantDep,
    service: ServiceDep,
) -> LogEntry:
    updated = service.update_entry(tenant_id=tenant_id, entry_id=entry_id, payload=payload)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found.")
    return updated


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_log_entry(entry_id: str, tenant_id: TenantDep, service: ServiceDep) -> None:
    if not service.delete_entry(tenant_id=tenant_id, entry_id=entry_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found.")


@router.get("/daily/nutrition", response_model=DailyNutritionSummary)
def get_daily_nutrition(
    service: ServiceDep,
    log_date: date | None = None,
    tenant_id: TenantDep = "",
) -> DailyNutritionSummary:
    target = log_date or datetime.now(UTC).date()
    return service.get_daily_nutrition(tenant_id=tenant_id, log_date=target)


@router.get("/daily/hydration", response_model=DailyHydrationSummary)
def get_daily_hydration(
    service: ServiceDep,
    log_date: date | None = None,
    tenant_id: TenantDep = "",
) -> DailyHydrationSummary:
    target = log_date or datetime.now(UTC).date()
    return service.get_daily_hydration(tenant_id=tenant_id, log_date=target)
