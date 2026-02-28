from __future__ import annotations

from datetime import date

from app.domain.models import LogEntry, LogEntryCreate, MealTemplate, MealTemplateCreate
from app.repositories.template_repository import TemplateRepository
from app.services.log_service import LogService


class TemplateService:
    def __init__(
        self,
        repository: TemplateRepository,
        log_service: LogService,
    ) -> None:
        self._repo = repository
        self._log_service = log_service

    async def create(self, tenant_id: str, payload: MealTemplateCreate) -> MealTemplate:
        template = MealTemplate(
            tenant_id=tenant_id,
            name=payload.name,
            entries=payload.entries,
        )
        return self._repo.save(tenant_id, template)

    async def get_all(self, tenant_id: str) -> list[MealTemplate]:
        return self._repo.find_all(tenant_id)

    async def delete(self, tenant_id: str, template_id: str) -> bool:
        return self._repo.delete(tenant_id, template_id)

    async def log_template(
        self, tenant_id: str, template_id: str, log_date: date | None = None
    ) -> list[LogEntry]:
        template = self._repo.find_by_id(tenant_id, template_id)
        if not template:
            return []

        entries: list[LogEntry] = []
        for entry in template.entries:
            log_payload = LogEntryCreate(
                product_id=entry.product_id,
                source=entry.source,
                quantity_g=entry.quantity_g,
                log_date=log_date,
                note=entry.note,
            )
            created = await self._log_service.create_entry(tenant_id, log_payload)
            entries.append(created)

        return entries
