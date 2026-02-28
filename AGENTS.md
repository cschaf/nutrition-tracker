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

# Type checking — must return zero errors
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
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.15.0
    hooks:
      - id: mypy
        args: [--strict, --ignore-missing-imports]
        additional_dependencies:
          - pydantic-settings
          - pydantic>=2
          - fastapi
          - httpx
          - sqlalchemy[asyncio]
          - prometheus-client
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

## 4a. mypy --strict Compliance Rules

**This project runs `mypy src/app --strict`. Every file you touch must pass with zero errors.**
These are the patterns that have caused CI failures in the past — memorize them.

### 4a.1 Never use `str, Enum` — use `StrEnum`

The `str, Enum` multiple-inheritance pattern causes MRO conflicts under mypy strict.

```python
# ❌ BREAKS mypy --strict
from enum import Enum
class DataSource(str, Enum):
    OPEN_FOOD_FACTS = "open_food_facts"

# ✅ CORRECT — Python 3.11+
from enum import StrEnum
class DataSource(StrEnum):
    OPEN_FOOD_FACTS = "open_food_facts"
```

### 4a.2 HTTP params dicts must be `dict[str, str]`

`httpx.AsyncClient.get(params=...)` expects a typed mapping. A plain `dict` with mixed `int`/`str`/`float` values fails mypy strict. Convert all values to `str`.

```python
# ❌ BREAKS mypy — dict[str, object] inferred
params = {
    "search_simple": 1,       # int — not allowed
    "page_size": limit,       # int — not allowed
    "action": "process",
}

# ✅ CORRECT — explicit dict[str, str]
params: dict[str, str] = {
    "search_simple": "1",
    "page_size": str(limit),
    "action": "process",
}
```

### 4a.3 Always pass Enum members — never raw strings — to Pydantic models

```python
# ❌ BREAKS mypy — str is not DataSource
GeneralizedProduct(source="open_food_facts", ...)

# ✅ CORRECT
GeneralizedProduct(source=DataSource.OPEN_FOOD_FACTS, ...)
```

### 4a.4 Adapter registry keys must be Enum members

```python
# ❌ BREAKS mypy — dict[str, Adapter] is not dict[DataSource, ProductSourcePort]
return {
    "open_food_facts": off_adapter,
    "usda_fooddata": usda_adapter,
}

# ✅ CORRECT
return {
    DataSource.OPEN_FOOD_FACTS: off_adapter,
    DataSource.USDA_FOODDATA: usda_adapter,
}
```

### 4a.5 FastAPI endpoints — use `Annotated` deps, never `= None` default

mypy strict prohibits implicit `Optional`. FastAPI dependency arguments with `= None` as default break this rule.

```python
# ❌ BREAKS mypy — default None is incompatible with LogService type
@router.get("/daily")
def get_daily_log(
    tenant_id: TenantDep = "",
    service: ServiceDep = None,    # ← mypy error
) -> list[LogEntry]: ...

# ✅ CORRECT — Annotated deps need no default value
TenantDep = Annotated[str, Security(get_tenant_id)]
ServiceDep = Annotated[LogService, Depends(get_log_service)]

@router.get("/daily")
def get_daily_log(
    tenant_id: TenantDep,          # no default needed
    service: ServiceDep,           # no default needed
    log_date: date | None = None,  # optional query param goes last
) -> list[LogEntry]: ...
```

**Rule:** `Annotated[Type, Depends(...)]` and `Annotated[str, Security(...)]` dependency arguments never need a default value. Put all optional query/path parameters after them.

### 4a.6 Health check endpoints must return `dict[str, str]`

```python
# ❌ BREAKS mypy — missing type parameters for generic type "dict"
async def health_check() -> dict:
    return {"status": "ok"}

# ✅ CORRECT
async def health_check() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}
```

### 4a.7 Complex internal dicts need explicit type annotations

When a dict maps to another dict with mixed value types, mypy cannot infer the type correctly. Annotate explicitly and use `cast()` where needed.

```python
from typing import cast

# ❌ BREAKS mypy — inferred as dict[str, dict[str, object]]
_NUTRIENT_MAP = {
    "calories": {"ids": {1008}, "unit_factor": Decimal("1")},
}

# ✅ CORRECT
_NUTRIENT_MAP: dict[str, dict[str, set[int] | Decimal]] = {
    "calories": {"ids": {1008}, "unit_factor": Decimal("1")},
}

# When iterating, cast to concrete type:
for nid in cast(set[int], meta["ids"]):
    ...
```

### 4a.8 Third-party libraries with incompatible signatures — use `# type: ignore[arg-type]`

Some third-party libraries (e.g. `slowapi`) have handler signatures that do not match Starlette's expected type. Do not restructure your code to work around this — use a targeted ignore:

```python
# slowapi's handler signature is intentionally incompatible with Starlette's type
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,  # type: ignore[arg-type]
)
```

Only use `# type: ignore` for genuinely incompatible third-party signatures. Never use it to silence errors in your own code.

### 4a.9 Never use truthiness checks on `Decimal` values — always check `is not None`

`Decimal("0")` is falsy in Python. A truthiness check `if m.fiber_g` evaluates to `False` when the value is zero, incorrectly treating a legitimate zero nutrient value as absent. This causes zero values to silently disappear from CSV exports, API responses, and daily totals.

```python
# ❌ WRONG — Decimal("0") is falsy, zero values are lost
fiber_g=(m.fiber_g * factor).quantize(Decimal("0.01")) if m.fiber_g else None,
sugar_g=(m.sugar_g * factor).quantize(Decimal("0.01")) if m.sugar_g else None,

# ✅ CORRECT — explicit None check preserves zero values
fiber_g=(m.fiber_g * factor).quantize(Decimal("0.01")) if m.fiber_g is not None else None,
sugar_g=(m.sugar_g * factor).quantize(Decimal("0.01")) if m.sugar_g is not None else None,
```

**Rule:** For any `Decimal | None` field, always use `if value is not None` — never bare `if value`. This applies to `scaled_macros`, `consumed_volume_ml`, and all nutrient fields throughout the codebase.

The same rule applies to `int | None` and `float | None` fields where zero is a valid value.

---

## 5. Testing Requirements

Every code change requires corresponding tests. No exceptions.

### 5.1 Test Location Rules

| What you changed | Where to write tests |
|---|---|
| `adapters/` | `tests/unit/test_adapters.py` |
| `services/log_service.py` | `tests/unit/test_log_service.py` |
| `services/barcode_service.py` | `tests/unit/test_barcode_service.py` |
| `services/export_service.py` | `tests/unit/test_export_service.py` |
| `services/goals_service.py` | `tests/unit/test_goals_service.py` |
| `services/notification_service.py` | `tests/unit/test_notification_service.py` |
| `services/product_cache.py` | `tests/unit/test_product_cache.py` |
| `services/template_service.py` | `tests/unit/test_template_service.py` |
| `repositories/sqlite_log_repository.py` | `tests/unit/test_sqlite_repository.py` |
| `api/v1/logs.py` | `tests/integration/test_api_logs.py` |
| `api/v1/products.py` | `tests/integration/test_api_products.py` |
| `api/v1/goals.py` | `tests/integration/test_api_goals.py` |
| `api/v1/templates.py` | `tests/integration/test_api_templates.py` |
| `api/v1/logs.py` (export) | `tests/integration/test_api_export.py` |
| `domain/models.py` | `tests/unit/test_models.py` |
| `core/metrics.py` | `tests/unit/test_metrics.py` |
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

### 5.4 pytest Exit Code 5 — "No Tests Collected"

**Exit code 5 means pytest found no test functions.** CI treats this as a failure. This happens when:

- A test file exists but contains no functions starting with `test_`
- A test directory exists but has no `.py` files at all
- All test files are empty placeholders

**Rules to prevent exit code 5:**

1. Every file in `tests/` that ends in `.py` (other than `conftest.py` and `__init__.py`) **must contain at least one test function**.
2. Never leave a test file as an empty placeholder — use a minimal skeleton instead:

```python
# tests/integration/test_api_logs.py
# MINIMUM REQUIRED CONTENT — add real tests here

import pytest
from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200


def test_readiness_check(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200


def test_unauthenticated_request_returns_401(client: TestClient) -> None:
    response = client.post("/api/v1/logs/", json={})
    assert response.status_code == 403  # missing header → 403 from APIKeyHeader


def test_invalid_api_key_returns_401(client: TestClient) -> None:
    response = client.post(
        "/api/v1/logs/",
        headers={"X-API-Key": "invalid-key"},
        json={},
    )
    assert response.status_code == 401


def test_get_daily_log_empty(client: TestClient, alice_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/logs/daily", headers=alice_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_get_daily_nutrition_empty(client: TestClient, alice_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/logs/daily/nutrition", headers=alice_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_entries"] == 0
    assert data["totals"]["calories_kcal"] == "0"


def test_get_daily_hydration_empty(client: TestClient, alice_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/logs/daily/hydration", headers=alice_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_volume_ml"] == "0"
    assert data["contributing_entries"] == 0


def test_get_nonexistent_entry_returns_404(
    client: TestClient, alice_headers: dict[str, str]
) -> None:
    response = client.get(
        "/api/v1/logs/00000000-0000-0000-0000-000000000000",
        headers=alice_headers,
    )
    assert response.status_code == 404


def test_delete_nonexistent_entry_returns_404(
    client: TestClient, alice_headers: dict[str, str]
) -> None:
    response = client.delete(
        "/api/v1/logs/00000000-0000-0000-0000-000000000000",
        headers=alice_headers,
    )
    assert response.status_code == 404
```

3. If `tests/integration/` will be empty for a sprint, configure pytest to not fail on empty collections by adding to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
# Prevent exit code 5 when a directory has no tests yet:
# Remove this line once all test files are populated
addopts = "--ignore=tests/integration"
```

But prefer option 2 — always have at least the baseline HTTP tests above.

### 5.5 Coverage Targets

| Module | Minimum |
|---|---|
| `domain/` | 100% |
| `services/` | 95% |
| `adapters/` | 90% |
| `api/` | 85% |

### 5.6 FastAPI Test Isolation — `app.dependency_overrides` vs `unittest.mock.patch`

**This is the most common source of hard-to-diagnose test failures in this project.**

FastAPI captures `Depends()` function object references at **import time**, not at call time. When you call `unittest.mock.patch("app.core.config.get_settings", ...)`, you replace the name `get_settings` in the `app.core.config` module namespace — but FastAPI's DI system already holds a reference to the *original* function object. The patch is invisible to FastAPI.

```python
# ❌ BROKEN — FastAPI ignores this patch
with patch("app.core.config.get_settings", return_value=test_settings):
    response = client.get("/api/v1/logs/daily")
    # FastAPI still calls the REAL get_settings → uses production DB
```

**The correct approach is `app.dependency_overrides`:**

```python
# ✅ CORRECT — FastAPI honours dependency_overrides
from app.core.config import get_settings
app.dependency_overrides[get_settings] = lambda: test_settings
try:
    response = client.get("/api/v1/logs/daily")
finally:
    app.dependency_overrides.pop(get_settings, None)
```

The `client` fixture in `tests/conftest.py` already handles `get_settings` override correctly. For per-test overrides of other dependencies (e.g. `get_tenant_id`), always use the same pattern:

```python
from app.core.security import get_tenant_id

app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"
try:
    response = client.get("/api/v1/logs/daily", headers={"X-API-Key": "any"})
    assert response.status_code == 200
finally:
    app.dependency_overrides.clear()
```

**Rules:**

1. Use `app.dependency_overrides[fn] = lambda: value` to replace any FastAPI `Depends()` or `Security()` dependency in tests.
2. Always restore in a `finally` block (`app.dependency_overrides.clear()` or `.pop(fn, None)`).
3. Use `unittest.mock.patch` only for **service method** patching (e.g. `patch("app.services.log_service.LogService.get_entry", ...)`), not for FastAPI dependency functions.
4. The `_repository` singleton in `app.api.dependencies` must be reset (`_deps._repository = None`) before and after each test that uses a real repository — the `client` fixture already does this.

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

## 8. Repository Layer (Persistence)

The project ships with **SQLite as the default** (`SQLiteLogRepository` in `repositories/sqlite_log_repository.py`). `InMemoryLogRepository` is kept for unit tests only.

The abstract interface lives in `repositories/base.py`:

```python
class AbstractLogRepository(ABC):
    async def save(self, entry: LogEntry) -> LogEntry: ...
    async def find_by_id(self, tenant_id: str, entry_id: str) -> LogEntry | None: ...
    async def find_by_date(self, tenant_id: str, log_date: date) -> list[LogEntry]: ...
    async def find_by_date_range(
        self, tenant_id: str, start_date: date, end_date: date
    ) -> list[LogEntry]: ...
    async def delete(self, tenant_id: str, entry_id: str) -> bool: ...
    async def update(self, entry: LogEntry) -> LogEntry: ...
```

To **switch to Postgres** or another backend:

1. Create `src/app/repositories/postgres_log_repository.py`
2. Inherit from `AbstractLogRepository` and implement all methods
3. Change `DATABASE_URL` in your `.env` / Helm secret
4. Update `get_log_repository()` in `api/dependencies.py`
5. `LogService` requires zero changes

**Important for tests:** Always use `sqlite+aiosqlite:///:memory:` in test fixtures. Never let tests write to the production `.db` file. The `test_settings` fixture in `conftest.py` already sets `database_url="sqlite+aiosqlite:///:memory:`.

---

## 9. Environment & Configuration

All config lives in `src/app/core/config.py` as a `pydantic-settings` model. Never hardcode values.

```bash
# Minimum .env for local development
API_KEYS={"dev-key":"tenant_dev"}
USDA_API_KEY=DEMO_KEY
DATABASE_URL=sqlite+aiosqlite:///nutrition_tracker.db
DEBUG=true
CORS_ORIGINS=["*"]
# Optional — webhook notifications
WEBHOOK_ENABLED=false
WEBHOOK_URL=
# Optional — product lookup
BARCODE_LOOKUP_ORDER=["open_food_facts","usda_fooddata"]
CACHE_TTL_SECONDS=3600
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
| Use `str, Enum` instead of `StrEnum` | MRO conflict breaks mypy strict |
| Pass raw strings where Enum members are expected | mypy strict type error |
| Use `dict` without type parameters | mypy strict requires `dict[K, V]` |
| Use untyped `dict` as httpx `params` | Incompatible type error in mypy strict |
| Add `= None` default to FastAPI `Annotated` deps | Implicit Optional breaks mypy strict |
| Leave test files empty or with no test functions | pytest exits with code 5, CI fails |
| Use `# type: ignore` in your own code | Only allowed for third-party signature mismatches |
| Use `if value` on `Decimal \| None` fields | `Decimal("0")` is falsy — zero values silently disappear |
| Commit `*.db` files | Generated runtime files do not belong in version control |
| Use `if value` truthiness on any nullable numeric field | Zero is a valid value for `int \| None` and `float \| None` too |
| Use `unittest.mock.patch` to replace a FastAPI `Depends()` function | FastAPI captures function references at import time — use `app.dependency_overrides[fn]` instead (see Section 5.6) |
| Let integration tests write to the real `.db` file | Always use `sqlite+aiosqlite:///:memory:` in test settings; reset `_deps._repository = None` per test |