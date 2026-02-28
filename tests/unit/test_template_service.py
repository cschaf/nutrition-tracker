from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models import DataSource, MealTemplateCreate, MealTemplateEntry
from app.repositories.template_repository import TemplateRepository
from app.services.log_service import LogService
from app.services.template_service import TemplateService


@pytest.fixture  # type: ignore[misc]
def template_repo() -> TemplateRepository:
    return TemplateRepository()


@pytest.fixture  # type: ignore[misc]
def log_service() -> MagicMock:
    return MagicMock(spec=LogService)


@pytest.fixture  # type: ignore[misc]
def template_service(template_repo: TemplateRepository, log_service: MagicMock) -> TemplateService:
    return TemplateService(repository=template_repo, log_service=log_service)


@pytest.mark.asyncio  # type: ignore[misc]
async def test_create_and_get_templates(template_service: TemplateService) -> None:
    tenant_id = "tenant_alice"
    payload = MealTemplateCreate(
        name="Healthy Breakfast",
        entries=[
            MealTemplateEntry(
                product_id="apple", source=DataSource.MANUAL, quantity_g=Decimal("150")
            ),
            MealTemplateEntry(
                product_id="oats", source=DataSource.MANUAL, quantity_g=Decimal("50")
            ),
        ],
    )

    template = await template_service.create(tenant_id, payload)
    assert template.name == "Healthy Breakfast"
    assert len(template.entries) == 2

    all_templates = await template_service.get_all(tenant_id)
    assert len(all_templates) == 1
    assert all_templates[0].id == template.id


@pytest.mark.asyncio  # type: ignore[misc]
async def test_tenant_isolation(template_service: TemplateService) -> None:
    alice_payload = MealTemplateCreate(
        name="Alice Meal",
        entries=[
            MealTemplateEntry(
                product_id="apple", source=DataSource.MANUAL, quantity_g=Decimal("100")
            )
        ],
    )
    await template_service.create("tenant_alice", alice_payload)

    bob_templates = await template_service.get_all("tenant_bob")
    assert len(bob_templates) == 0


@pytest.mark.asyncio  # type: ignore[misc]
async def test_delete_template(template_service: TemplateService) -> None:
    tenant_id = "tenant_alice"
    payload = MealTemplateCreate(
        name="To Delete",
        entries=[
            MealTemplateEntry(
                product_id="apple", source=DataSource.MANUAL, quantity_g=Decimal("100")
            )
        ],
    )
    template = await template_service.create(tenant_id, payload)

    deleted = await template_service.delete(tenant_id, template.id)
    assert deleted is True

    all_templates = await template_service.get_all(tenant_id)
    assert len(all_templates) == 0


@pytest.mark.asyncio  # type: ignore[misc]
async def test_log_template(template_service: TemplateService, log_service: MagicMock) -> None:
    tenant_id = "tenant_alice"
    payload = MealTemplateCreate(
        name="Log Me",
        entries=[
            MealTemplateEntry(
                product_id="apple",
                source=DataSource.MANUAL,
                quantity_g=Decimal("150"),
                note="Yummy",
            ),
            MealTemplateEntry(
                product_id="oats", source=DataSource.MANUAL, quantity_g=Decimal("50")
            ),
        ],
    )
    template = await template_service.create(tenant_id, payload)

    # Mock LogService.create_entry
    log_service.create_entry = AsyncMock()

    await template_service.log_template(tenant_id, template.id)

    assert log_service.create_entry.call_count == 2
    # Check calls
    calls = log_service.create_entry.call_args_list
    assert calls[0].args[0] == tenant_id
    assert calls[0].args[1].product_id == "apple"
    assert calls[0].args[1].quantity_g == Decimal("150")
    assert calls[0].args[1].note == "Yummy"

    assert calls[1].args[0] == tenant_id
    assert calls[1].args[1].product_id == "oats"
    assert calls[1].args[1].quantity_g == Decimal("50")
