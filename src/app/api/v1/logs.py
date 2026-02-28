# src/app/api/v1/logs.py
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_export_service, get_log_service
from app.core.security import get_tenant_id
from app.domain.models import (
    DailyHydrationSummary,
    DailyNutritionSummary,
    DateRangeParams,
    LogEntry,
    LogEntryCreate,
    LogEntryUpdate,
)
from app.services.export_service import ExportService
from app.services.log_service import LogService

router = APIRouter(prefix="/logs", tags=["Logs"])

TenantDep = Annotated[str, Security(get_tenant_id)]
ServiceDep = Annotated[LogService, Depends(get_log_service)]
ExportServiceDep = Annotated[ExportService, Depends(get_export_service)]


@router.post("/", response_model=LogEntry, status_code=status.HTTP_201_CREATED)
async def create_log_entry(
    payload: LogEntryCreate,
    tenant_id: TenantDep,
    service: ServiceDep,
) -> LogEntry:
    return await service.create_entry(tenant_id=tenant_id, payload=payload)


@router.get("/daily", response_model=list[LogEntry])
async def get_daily_log(
    service: ServiceDep,
    log_date: date | None = None,
    tenant_id: TenantDep = "",
) -> list[LogEntry]:
    target = log_date or datetime.now(UTC).date()
    return await service.get_entries_for_date(tenant_id=tenant_id, log_date=target)


@router.get("/{entry_id}", response_model=LogEntry)
async def get_log_entry(entry_id: str, tenant_id: TenantDep, service: ServiceDep) -> LogEntry:
    entry = await service.get_entry(tenant_id=tenant_id, entry_id=entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found.")
    return entry


@router.patch("/{entry_id}", response_model=LogEntry)
async def update_log_entry(
    entry_id: str,
    payload: LogEntryUpdate,
    tenant_id: TenantDep,
    service: ServiceDep,
) -> LogEntry:
    updated = await service.update_entry(tenant_id=tenant_id, entry_id=entry_id, payload=payload)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found.")
    return updated


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_log_entry(entry_id: str, tenant_id: TenantDep, service: ServiceDep) -> None:
    if not await service.delete_entry(tenant_id=tenant_id, entry_id=entry_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found.")


@router.get("/daily/nutrition", response_model=DailyNutritionSummary)
async def get_daily_nutrition(
    service: ServiceDep,
    log_date: date | None = None,
    tenant_id: TenantDep = "",
) -> DailyNutritionSummary:
    target = log_date or datetime.now(UTC).date()
    return await service.get_daily_nutrition(tenant_id=tenant_id, log_date=target)


@router.get("/daily/hydration", response_model=DailyHydrationSummary)
async def get_daily_hydration(
    service: ServiceDep,
    log_date: date | None = None,
    tenant_id: TenantDep = "",
) -> DailyHydrationSummary:
    target = log_date or datetime.now(UTC).date()
    return await service.get_daily_hydration(tenant_id=tenant_id, log_date=target)


@router.get("/range/nutrition", response_model=list[DailyNutritionSummary])
async def get_nutrition_range(
    tenant_id: TenantDep,
    service: ServiceDep,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
) -> list[DailyNutritionSummary]:
    try:
        dr = DateRangeParams(start_date=from_date, end_date=to_date)
    except ValueError as e:
        # Map to 400 as per common practice for range errors, or 422 if strict
        raise HTTPException(status_code=400, detail=str(e))

    return await service.get_nutrition_range(
        tenant_id=tenant_id, start_date=dr.start_date, end_date=dr.end_date
    )


@router.get("/export/csv")
async def export_logs_csv(
    tenant_id: TenantDep,
    service: ServiceDep,
    export_service: ExportServiceDep,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
) -> StreamingResponse:
    try:
        dr = DateRangeParams(start_date=from_date, end_date=to_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    entries = await service._repo.find_by_date_range(
        tenant_id=tenant_id, start_date=dr.start_date, end_date=dr.end_date
    )
    # Sort entries by date and time (consumed_at)
    entries.sort(key=lambda e: (e.log_date, e.consumed_at))

    content = export_service.generate_csv(entries)
    filename = f"nutrition_{dr.start_date}_{dr.end_date}.csv"

    return StreamingResponse(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/range/hydration", response_model=list[DailyHydrationSummary])
async def get_hydration_range(
    tenant_id: TenantDep,
    service: ServiceDep,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
) -> list[DailyHydrationSummary]:
    try:
        dr = DateRangeParams(start_date=from_date, end_date=to_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return await service.get_hydration_range(
        tenant_id=tenant_id, start_date=dr.start_date, end_date=dr.end_date
    )
