# 🤖 AGENTS.md — AI Contributor Guide

> **This file is the single source of truth for any AI agent (Claude, Copilot, Cursor, Gemini, etc.) contributing to this project.**
> Read this file completely before writing a single line of code or making any file changes.

---

## 1. Project Identity

| Property | Value |
|---|---|
| **Name** | Nutrition & Hydration Tracking API |
| **Stack** | Python 3.12, FastAPI, Pydantic v2, httpx |
| **Architecture** | Hexagonal (Ports & Adapters) |
| **Deployment** | Docker → ghcr.io → k3s via FluxCD |
| **Package layout** | `src/` layout — app lives in `src/app/` |
| **Test framework** | pytest + pytest-asyncio |
| **Linter** | ruff (auto-fix on every commit, see Section 4) |
| **Type checker** | mypy --strict |

---

## 2. Absolute Architecture Rules

These rules are non-negotiable. Violating them will cause the CI to fail or introduce security bugs.

### 2.1 Dependency Direction

```
API Layer → Service Layer → Repository / Port Interface ← Adapters
```

- `api/` imports from `services/` and `domain/` only
- `services/` imports from `domain/` and `repositories/` only
- `adapters/` imports from `domain/` only
- `domain/` imports from nothing internal

```python
# ❌ NEVER — adapter import in service
from app.adapters.open_food_facts import OpenFoodFactsAdapter

# ❌ NEVER — repository import in API layer
from app.repositories.log_repository import InMemoryLogRepository

# ✅ ALWAYS — depend on the abstraction
from app.domain.ports import ProductSourcePort
```

### 2.2 Tenant Isolation — Security Critical

```python
# ❌ NEVER — accept tenant_id from client input
@router.get("/logs")
def get_logs(tenant_id: str = Query(...)):  # SECURITY BUG

# ✅ ALWAYS — derive tenant_id from validated API key only
@router.get("/logs")
def get_logs(tenant_id: Annotated[str, Security(get_tenant_id)]):
```

Every single repository method takes `tenant_id: str` as its first argument. This is what enforces data isolation between users. Never bypass it.

### 2.3 Numeric Types

```python
# ❌ NEVER — float for nutritional values
calories: float = 42.0

# ✅ ALWAYS — Decimal for all nutritional/volume values
from decimal import Decimal
calories: Decimal = Decimal("42.0")
```

Floating-point errors accumulate over many log entries and corrupt daily totals.

### 2.4 Domain Models are Immutable

All Pydantic models in `domain/models.py` use `model_config = {"frozen": True}`. Never remove this. Use `model_copy(update={...})` for modifications.

```python
# ❌ NEVER
entry.quantity_g = Decimal("200")

# ✅ ALWAYS
updated = entry.model_copy(update={"quantity_g": Decimal("200")})
```

---

## 3. Code Style & Conventions

### 3.1 Python Version

Target Python 3.12. Use modern syntax:

```python
# ✅ Use StrEnum (Python 3.11+)
from enum import StrEnum
class DataSource(StrEnum): ...

# ✅ Use datetime.UTC (Python 3.11+)
datetime.now(datetime.UTC)

# ✅ Use collections.abc for type hints
from collections.abc import AsyncGenerator

# ✅ Union types with | operator
def foo(x: str | None) -> int | None: ...
```

### 3.2 Import Order

ruff enforces `isort`-style import ordering automatically. The canonical order is:

```python
# 1. __future__
from __future__ import annotations

# 2. stdlib
import uuid
from datetime import date
from decimal import Decimal

# 3. third-party
import httpx
from fastapi import Depends
from pydantic import BaseModel

# 4. local (absolute, src-layout)
from app.domain.models import GeneralizedProduct
from app.domain.ports import ProductSourcePort
```

### 3.3 FastAPI Dependency Pattern

`B008` (Depends in function defaults) is intentionally ignored in this project because it is the standard FastAPI pattern. Do not "fix" it by restructuring dependencies.

```python
# ✅ This is correct FastAPI — B008 is suppressed in pyproject.toml
def get_log_service(
    registry: dict = Depends(get_adapter_registry),
    repo: InMemoryLogRepository = Depends(get_log_repository),
) -> LogService:
    return LogService(adapter_registry=registry, repository=repo)
```

### 3.4 Error Handling

Always raise domain exceptions from `domain/ports.py`, never raw `Exception`:

```python
from app.domain.ports import ProductNotFoundError, ExternalApiError

# ❌
raise Exception("not found")

# ✅
raise ProductNotFoundError(product_id=product_id, source="my_source")
```

In API routers, catch domain exceptions and map to HTTP status codes:

```python
try:
    entry = await service.create_entry(tenant_id, payload)
except ProductNotFoundError as e:
    raise HTTPException(status_code=404, detail=str(e))
except ExternalApiError as e:
    raise HTTPException(status_code=502, detail=str(e))
```

---

## 4. Linting & Formatting — Mandatory Before Every Commit

**ruff runs automatically in CI and will block merges if it fails.** Run it locally before every commit.

### 4.1 Commands

```bash
# Auto-fix everything fixable
ruff check src/ tests/ --fix
ruff check src/ tests/ --fix --unsafe-fixes

# Final check — must return zero errors
ruff check src/ tests/

# Type checking
mypy src/app --strict
```

### 4.2 Pre-commit Hook (install once)

```bash
pip install pre-commit
pre-commit install
```

`.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
```

After this, ruff runs automatically on every `git commit`. **A commit that fails ruff will be rejected locally** before it ever reaches CI.

### 4.3 Known Suppressions

These ruff rules are intentionally ignored in `pyproject.toml`:

| Rule | Reason |
|---|---|
| `B008` | FastAPI's `Depends()` in function signatures is the intended pattern |

Do not add new suppressions without documenting the reason here.

### 4.4 What CI Does

```
Push to main / PR
        │
        ▼
ruff --fix (auto-commits fixes back to branch)
        │
        ▼
ruff check (fails if manual fixes still needed)
        │
        ▼
mypy --strict
        │
        ▼
pytest tests/unit/
        │
        ▼
pytest tests/integration/
        │
        ▼
helm lint
```

If any step fails, the build is blocked. Fix locally, do not push and wait for CI to tell you.

---

## 5. Testing Requirements

Every code change requires corresponding tests. No exceptions.

### 5.1 Test Location Rules

| What you changed | Where to write tests |
|---|---|
| `adapters/` | `tests/unit/test_adapters.py` |
| `services/` | `tests/unit/test_log_service.py` |
| `api/v1/` | `tests/integration/test_api_logs.py` |
| `domain/models.py` | `tests/unit/test_models.py` (create if needed) |
| New adapter | New `tests/unit/test_<adapter_name>.py` |

### 5.2 Unit Test Pattern — Always Mock HTTP

```python
@pytest.mark.asyncio
async def test_adapter_normalizes_correctly():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {...}  # raw API response fixture
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    adapter = MyAdapter(http_client=mock_client)
    product = await adapter.fetch_by_id("test-id")

    assert product.source == DataSource.MY_SOURCE
    assert product.macronutrients.calories_kcal == Decimal("42.0")
```

Never make real HTTP calls in unit tests. If a test requires internet access, it belongs in integration tests and must be marked `@pytest.mark.integration`.

### 5.3 Tenant Isolation Must Always Be Tested

Every new service method that returns user data must have a test verifying that Tenant A cannot see Tenant B's data:

```python
async def test_tenant_isolation():
    await service.create_entry("tenant_alice", payload)
    result = service.get_entries_for_date("tenant_bob", date.today())
    assert len(result) == 0  # Bob sees nothing
```

### 5.4 Coverage Targets

| Module | Minimum |
|---|---|
| `domain/` | 100% |
| `services/` | 95% |
| `adapters/` | 90% |
| `api/` | 85% |

---

## 6. Adding a New External Data Source (Step-by-Step)

1. **Write the failing test first** in `tests/unit/test_adapters.py`
2. Create `src/app/adapters/my_source.py`
3. Implement `ProductSourcePort`:
   ```python
   class MySourceAdapter(ProductSourcePort):
       async def fetch_by_id(self, product_id: str) -> GeneralizedProduct: ...
       async def search(self, query: str, limit: int = 10) -> list[GeneralizedProduct]: ...
       def _normalize(self, raw: ...) -> GeneralizedProduct: ...
   ```
4. Add `MY_SOURCE = "my_source"` to `DataSource(StrEnum)` in `domain/models.py`
5. Add factory function to `api/dependencies.py`
6. Register in `get_adapter_registry()` in `api/dependencies.py`
7. The `_normalize()` method MUST:
   - Return `GeneralizedProduct` — never raw external types
   - Set `is_liquid=True` AND `volume_ml_per_100g=Decimal("100")` for beverages
   - Use `Decimal(str(value))` for float→Decimal conversion (never `Decimal(float)`)
   - Handle `None` values gracefully for all optional nutrient fields

---

## 7. Adding a New API Endpoint (Step-by-Step)

1. Add route to `src/app/api/v1/logs.py` (or new router file for new resource)
2. **Always** use the tenant security dependency:
   ```python
   TenantDep = Annotated[str, Security(get_tenant_id)]
   ```
3. All business logic goes in `LogService` — routers only handle HTTP concerns
4. Map domain exceptions to HTTP status codes in the router
5. Write integration test in `tests/integration/test_api_logs.py`
6. If adding a new router file, register it in `api/v1/router.py`

---

## 8. Replacing the Repository (Persistence Upgrade)

The current `InMemoryLogRepository` loses all data on restart. To add persistence:

1. Create `src/app/repositories/sqlite_log_repository.py` (or postgres)
2. Implement the same method signatures:
   ```python
   def save(self, entry: LogEntry) -> LogEntry: ...
   def find_by_id(self, tenant_id: str, entry_id: str) -> LogEntry | None: ...
   def find_by_date(self, tenant_id: str, log_date: date) -> list[LogEntry]: ...
   def delete(self, tenant_id: str, entry_id: str) -> bool: ...
   def update(self, entry: LogEntry) -> LogEntry: ...
   ```
3. Update `get_log_repository()` in `api/dependencies.py`
4. `LogService` requires zero changes

---

## 9. Environment & Configuration

All config lives in `src/app/core/config.py` as a `pydantic-settings` model. Never hardcode values.

```bash
# Minimum .env for local development
API_KEYS={"dev-key":"tenant_dev"}
USDA_API_KEY=DEMO_KEY
DEBUG=true
CORS_ORIGINS=["*"]
```

To add a new config value:
1. Add the field to `Settings` in `core/config.py` with a sensible default
2. Document it in this file and in `README.md`'s Configuration table
3. Add it to `deploy/charts/nutrition-tracker/templates/configmap.yaml` (non-secret) or `secret.yaml` (secret)

---

## 10. Unit Conversion Reference

When normalizing external API data, apply these conversions:

| Source | Field | Raw Unit | Target Unit | Conversion |
|---|---|---|---|---|
| Open Food Facts | `sodium_100g` | grams | mg | × 1000 |
| Open Food Facts | `potassium_100g` | grams | mg | × 1000 |
| Open Food Facts | `calcium_100g` | grams | mg | × 1000 |
| Open Food Facts | `iron_100g` | grams | mg | × 1000 |
| Open Food Facts | `energy-kcal_100g` | kcal | kcal | none |
| USDA | all nutrients | already mg/kcal | same | none |
| All sources | macros | per 100g | scaled | `× (quantity_g / 100)` in `scaled_macros` |
| All liquids | volume | ml per 100g | ml consumed | `× (quantity_g / 100)` in `consumed_volume_ml` |

---

## 11. CI/CD Overview

| Trigger | Pipeline | What happens |
|---|---|---|
| Push to `main` | `ci.yml` | ruff fix → ruff check → mypy → pytest → helm lint |
| Pull Request | `ci.yml` | same as above + docker build (no push) |
| `git tag v*.*.*` | `cd.yml` | Docker build → push to `ghcr.io` |
| Image in ghcr.io | FluxCD (in-cluster) | Automatic rollout to k3s homelab |

**Never manually deploy to the cluster.** Push a tag, let the pipeline handle it.

```bash
# Correct release flow
git tag v1.2.0
git push --tags
# CI builds and pushes image
# FluxCD picks up new image within polling interval
```

---

## 12. What NOT to Do

| Don't | Why |
|---|---|
| Use `float` for nutrients | Precision errors corrupt daily totals |
| Accept `tenant_id` from request body/query | Security: cross-tenant data leak |
| Import adapters in services | Violates hexagonal architecture |
| Import repositories in API layer | Violates separation of concerns |
| Call external APIs in unit tests | Flaky, slow, requires internet |
| Remove `frozen=True` from domain models | Breaks immutability guarantee |
| Commit without running ruff | CI will reject the push |
| Push directly to `main` without PR | Use pull requests for review |
| Hardcode config values | Use `core/config.py` + env vars |
| Add new ruff suppressions without documenting | Creates undocumented tech debt |