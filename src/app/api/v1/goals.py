from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Security

from app.api.dependencies import get_goals_service
from app.core.security import get_tenant_id
from app.domain.models import DailyGoals, DailyGoalsProgress
from app.services.goals_service import GoalsService

router = APIRouter(prefix="/goals", tags=["Goals"])

TenantDep = Annotated[str, Security(get_tenant_id)]
ServiceDep = Annotated[GoalsService, Depends(get_goals_service)]


@router.get("/", response_model=DailyGoals)
async def get_goals(
    tenant_id: TenantDep,
    service: ServiceDep,
) -> DailyGoals:
    """Retrieves current daily goals."""
    return await service.get_goals(tenant_id)


@router.put("/", response_model=DailyGoals)
async def replace_goals(
    payload: DailyGoals,
    tenant_id: TenantDep,
    service: ServiceDep,
) -> DailyGoals:
    """Completely replaces daily goals."""
    return await service.update_goals(tenant_id, payload)


@router.patch("/", response_model=DailyGoals)
async def update_goals(
    payload: DailyGoals,
    tenant_id: TenantDep,
    service: ServiceDep,
) -> DailyGoals:
    """Updates daily goals (only provided fields)."""
    current = await service.get_goals(tenant_id)
    updated = current.model_copy(update=payload.model_dump(exclude_unset=True))
    return await service.update_goals(tenant_id, updated)


@router.get("/progress", response_model=DailyGoalsProgress)
async def get_progress(
    service: ServiceDep,
    tenant_id: TenantDep,
    date: date | None = Query(default=None),
) -> DailyGoalsProgress:
    """Retrieves progress towards daily goals for a specific date."""
    target = date or datetime.now(UTC).date()
    return await service.get_progress(tenant_id, target)
