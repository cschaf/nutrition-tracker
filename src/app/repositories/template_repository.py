from __future__ import annotations

from app.domain.models import MealTemplate


class TemplateRepository:
    def __init__(self) -> None:
        # Structure: tenant_id -> template_id -> MealTemplate
        self._storage: dict[str, dict[str, MealTemplate]] = {}

    def save(self, tenant_id: str, template: MealTemplate) -> MealTemplate:
        if tenant_id not in self._storage:
            self._storage[tenant_id] = {}
        self._storage[tenant_id][template.id] = template
        return template

    def find_by_id(self, tenant_id: str, template_id: str) -> MealTemplate | None:
        return self._storage.get(tenant_id, {}).get(template_id)

    def find_all(self, tenant_id: str) -> list[MealTemplate]:
        return list(self._storage.get(tenant_id, {}).values())

    def delete(self, tenant_id: str, template_id: str) -> bool:
        if tenant_id in self._storage and template_id in self._storage[tenant_id]:
            del self._storage[tenant_id][template_id]
            return True
        return False
