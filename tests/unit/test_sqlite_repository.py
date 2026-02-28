import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
import pytest_asyncio

from app.domain.models import DataSource, GeneralizedProduct, LogEntry, Macronutrients
from app.repositories.sqlite_log_repository import SQLiteLogRepository


@pytest_asyncio.fixture
async def sqlite_repo():
    # Use in-memory SQLite for testing
    repo = SQLiteLogRepository("sqlite+aiosqlite:///:memory:")
    await repo.initialize()
    return repo


def create_test_entry(tenant_id: str, entry_id: str = None) -> LogEntry:
    return LogEntry(
        id=entry_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        log_date=date(2024, 5, 20),
        product=GeneralizedProduct(
            id="test-prod",
            source=DataSource.MANUAL,
            name="Test Product",
            macronutrients=Macronutrients(
                calories_kcal=Decimal("100"),
                protein_g=Decimal("10"),
                carbohydrates_g=Decimal("20"),
                fat_g=Decimal("5"),
            ),
        ),
        quantity_g=Decimal("100"),
        consumed_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_save_and_find_by_id(sqlite_repo):
    tenant_id = "alice"
    entry = create_test_entry(tenant_id)

    await sqlite_repo.save(entry)

    found = await sqlite_repo.find_by_id(tenant_id, entry.id)
    assert found is not None
    assert found.id == entry.id
    assert found.tenant_id == tenant_id
    assert found.product.name == "Test Product"


@pytest.mark.asyncio
async def test_find_by_id_wrong_tenant(sqlite_repo):
    entry = create_test_entry("alice")
    await sqlite_repo.save(entry)

    found = await sqlite_repo.find_by_id("bob", entry.id)
    assert found is None


@pytest.mark.asyncio
async def test_find_by_date(sqlite_repo):
    tenant_id = "alice"
    entry1 = create_test_entry(tenant_id)
    entry2 = create_test_entry(tenant_id)
    entry2 = entry2.model_copy(update={"id": str(uuid.uuid4()), "log_date": date(2024, 5, 21)})

    await sqlite_repo.save(entry1)
    await sqlite_repo.save(entry2)

    entries_20 = await sqlite_repo.find_by_date(tenant_id, date(2024, 5, 20))
    assert len(entries_20) == 1
    assert entries_20[0].id == entry1.id

    entries_21 = await sqlite_repo.find_by_date(tenant_id, date(2024, 5, 21))
    assert len(entries_21) == 1
    assert entries_21[0].id == entry2.id


@pytest.mark.asyncio
async def test_delete(sqlite_repo):
    tenant_id = "alice"
    entry = create_test_entry(tenant_id)
    await sqlite_repo.save(entry)

    deleted = await sqlite_repo.delete(tenant_id, entry.id)
    assert deleted is True

    found = await sqlite_repo.find_by_id(tenant_id, entry.id)
    assert found is None


@pytest.mark.asyncio
async def test_delete_nonexistent(sqlite_repo):
    deleted = await sqlite_repo.delete("alice", "nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_update(sqlite_repo):
    tenant_id = "alice"
    entry = create_test_entry(tenant_id)
    await sqlite_repo.save(entry)

    updated_entry = entry.model_copy(update={"quantity_g": Decimal("200")})
    await sqlite_repo.update(updated_entry)

    found = await sqlite_repo.find_by_id(tenant_id, entry.id)
    assert found.quantity_g == Decimal("200")
