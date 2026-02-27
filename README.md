# 🥗 Nutrition & Hydration Tracking API

> A cloud-native, multi-tenant REST API for tracking daily nutrition and hydration intake.
> Built with FastAPI, Python 3.12, and designed for Kubernetes/Homelab deployment.

[![CI Pipeline](https://img.shields.io/github/actions/workflow/status/your-org/nutrition-tracker/ci.yml?label=CI&logo=github)](/.github/workflows/ci.yml)
[![Helm Lint](https://img.shields.io/badge/helm-lint%20passing-blue?logo=helm)](deploy/charts/nutrition-tracker)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Repository Structure](#-repository-structure)
- [Domain Model](#-domain-model)
- [API Reference](#-api-reference)
- [Quick Start (Local)](#-quick-start-local)
- [Configuration](#-configuration)
- [Docker](#-docker)
- [Kubernetes / Helm Deployment](#-kubernetes--helm-deployment)
- [CI/CD Pipeline](#-cicd-pipeline)
- [Testing](#-testing)
- [AI Agent Guide](#-ai-agent-guide)
- [Design Decisions & ADRs](#-design-decisions--adrs)
- [Roadmap](#-roadmap)

---

## 🌐 Overview

This API enables users to log consumed food and beverages, automatically fetching and normalizing nutritional data from **two external sources** (Open Food Facts & USDA FoodData Central). It provides separate daily aggregation endpoints for **nutrition totals** and **hydration tracking**.

### Key Features

| Feature | Detail |
|---|---|
| **Multi-Tenancy** | Strict data isolation per user via static API keys |
| **Adapter Pattern** | Source-agnostic product normalization (OFF + USDA) |
| **Hydration Tracking** | Separate liquid volume aggregation in ml |
| **Nutrition Aggregation** | Daily macro/micronutrient totals |
| **CRUD Logging** | Full create/read/update/delete for daily log entries |
| **Production-Ready** | Multi-stage Docker, Helm charts, Health-checks, Graceful shutdown |

---

## 🏛 Architecture

### System Overview

```
HTTP Request
     │
     ▼
┌─────────────────────────────────────────────┐
│  FastAPI Layer                              │
│  ┌───────────────┐  ┌─────────────────────┐│
│  │ API-Key Auth  │  │  Rate Limiter       ││
│  │ (X-API-Key)   │  │  (slowapi)          ││
│  └───────────────┘  └─────────────────────┘│
│            │                               │
│  ┌─────────▼───────────────────────────┐   │
│  │  Routers: /api/v1/logs              │   │
│  └─────────────────────┬───────────────┘   │
└────────────────────────┼───────────────────┘
                         │
              ┌──────────▼──────────┐
              │     LogService      │  ← Core Domain
              │  (tenant-isolated)  │
              └──────┬──────────────┘
                     │
        ┌────────────┴──────────────────┐
        │                               │
┌───────▼───────┐           ┌───────────▼──────────────┐
│ LogRepository │           │     Adapter Registry     │
│ (In-Memory /  │           │  ┌────────────────────┐  │
│  pluggable)   │           │  │  OFF Adapter       │  │
└───────────────┘           │  ├────────────────────┤  │
                            │  │  USDA Adapter      │  │
                            │  └────────────────────┘  │
                            │  ↑ ProductSourcePort      │
                            └──────────────────────────┘
                                         │
                         ┌───────────────┴───────────────┐
                         │                               │
                ┌────────▼────────┐             ┌────────▼────────┐
                │ Open Food Facts │             │ USDA FoodData   │
                │ API             │             │ Central API     │
                └─────────────────┘             └─────────────────┘
```

### Architectural Principles

- **Hexagonal Architecture (Ports & Adapters):** The `ProductSourcePort` interface decouples the core domain from all external APIs. Swap or add data sources without touching business logic.
- **Strict Tenant Isolation:** Every repository operation is scoped to `tenant_id`, derived exclusively from the validated API key. Cross-tenant data access is architecturally impossible.
- **Immutable Domain Objects:** All Pydantic models use `model_config = {"frozen": True}`. Computed properties (`scaled_macros`, `consumed_volume_ml`) are derived on-the-fly, never stored redundantly.
- **Dependency Injection throughout:** FastAPI's `Depends()` wires all components. Every dependency is mockable for testing without patching globals.

---

## 📁 Repository Structure

```
nutrition-tracker/
│
├── .github/
│   └── workflows/
│       ├── ci.yml              # Lint, Type-Check, Unit + Integration Tests, Helm Lint
│       └── cd.yml              # Docker Build/Push to GHCR, Helm Deploy on git tag
│
├── src/
│   └── app/
│       ├── main.py             # FastAPI app factory, lifespan, middleware registration
│       ├── core/
│       │   ├── config.py       # Pydantic Settings (env-based configuration)
│       │   └── security.py     # API-Key validation dependency → returns tenant_id
│       ├── domain/
│       │   ├── models.py       # ALL Pydantic schemas: GeneralizedProduct, LogEntry, Summaries
│       │   └── ports.py        # Abstract interfaces + custom domain exceptions
│       ├── adapters/
│       │   ├── open_food_facts.py  # OFF API adapter (barcode/search → GeneralizedProduct)
│       │   └── usda_fooddata.py    # USDA API adapter (fdcId/search → GeneralizedProduct)
│       ├── services/
│       │   └── log_service.py  # Business logic: create/read/update/delete + daily aggregations
│       ├── api/
│       │   ├── dependencies.py # DI factory functions for adapters, service, repository
│       │   └── v1/
│       │       ├── router.py   # Mounts all v1 sub-routers under /api/v1
│       │       └── logs.py     # All /logs endpoints (CRUD + daily/nutrition + daily/hydration)
│       └── repositories/
│           └── log_repository.py  # In-memory store, keyed by tenant_id → entry_id
│
├── tests/
│   ├── conftest.py             # Shared fixtures: test client, settings override, auth headers
│   ├── unit/
│   │   ├── test_adapters.py    # Adapter normalization logic (mocked HTTP)
│   │   └── test_log_service.py # Service business logic (tenant isolation, aggregation)
│   └── integration/
│       └── test_api_logs.py    # Full HTTP cycle tests via TestClient
│
├── deploy/
│   └── charts/
│       └── nutrition-tracker/
│           ├── Chart.yaml          # Chart metadata (name, version, appVersion)
│           ├── values.yaml         # All configurable values with defaults
│           └── templates/
│               ├── _helpers.tpl    # fullname, labels, selectorLabels helpers
│               ├── deployment.yaml # Pod spec with security context, probes, env injection
│               ├── service.yaml    # ClusterIP service
│               ├── ingress.yaml    # Optional ingress (nginx by default)
│               ├── configmap.yaml  # Non-sensitive env vars
│               └── secret.yaml     # API_KEYS + USDA_API_KEY (b64 encoded)
│
├── Dockerfile                  # Multi-stage: builder + distroless runtime, non-root
├── .dockerignore
├── pyproject.toml              # Project metadata, deps, dev deps, tool configs (ruff, mypy, pytest)
└── README.md                   # This file
```

---

## 🧩 Domain Model

### Core Entities

```
GeneralizedProduct (frozen, source-agnostic)
│
├── id: str                        # Source-native ID (barcode or fdcId)
├── source: DataSource             # Enum: OPEN_FOOD_FACTS | USDA_FOODDATA | MANUAL
├── name: str
├── brand: str | None
├── barcode: str | None
│
├── macronutrients: Macronutrients (per 100g/100ml)
│   ├── calories_kcal: Decimal
│   ├── protein_g: Decimal
│   ├── carbohydrates_g: Decimal
│   ├── fat_g: Decimal
│   ├── fiber_g: Decimal | None
│   └── sugar_g: Decimal | None
│
├── micronutrients: Micronutrients | None
│   ├── sodium_mg, potassium_mg, calcium_mg, iron_mg
│   └── vitamin_c_mg, vitamin_d_ug
│
├── is_liquid: bool                # Drives hydration tracking
└── volume_ml_per_100g: Decimal | None  # Required when is_liquid=True


LogEntry
│
├── id: str (UUID)
├── tenant_id: str                 # Derived from API key — enforces isolation
├── log_date: date
├── product: GeneralizedProduct    # Embedded snapshot
├── quantity_g: Decimal            # Consumed amount in grams (or g-equivalent for liquids)
├── consumed_at: datetime (UTC)
├── note: str | None
│
├── [property] scaled_macros       # Computes absolute macros for quantity_g
└── [property] consumed_volume_ml  # Returns ml if is_liquid, else None
```

### Data Flow: External API → Internal Domain

```
User Request: POST /api/v1/logs  { product_id: "5449000000996", source: "open_food_facts", quantity_g: 330 }
                │
                ▼
        LogService.create_entry()
                │
                ▼
        AdapterRegistry.get(DataSource.OPEN_FOOD_FACTS)
                │
                ▼
        OpenFoodFactsAdapter.fetch_by_id("5449000000996")
                │   [HTTP GET world.openfoodfacts.org/api/v0/product/...]
                │   [Parse _OffResponse → _OffProduct]
                │   [Normalize: detect liquid, convert units, map nulls]
                ▼
        GeneralizedProduct(source=OPEN_FOOD_FACTS, is_liquid=True, ...)
                │
                ▼
        LogEntry(tenant_id="tenant_alice", product=..., quantity_g=330)
                │
                ▼
        InMemoryLogRepository.save(entry)
                │
                ▼
        HTTP 201 Created → LogEntry JSON
```

---

## 📡 API Reference

**Base URL:** `http://localhost:8000`
**Auth Header:** `X-API-Key: <your-key>`
**Versioning:** URI-based (`/api/v1/`)
**Docs:** `/docs` (Swagger UI) | `/redoc` (ReDoc)

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/healthz` | Liveness check |
| `GET` | `/readyz` | Readiness check |
| `POST` | `/api/v1/logs/` | Create a new log entry |
| `GET` | `/api/v1/logs/daily` | Get all entries for a date |
| `GET` | `/api/v1/logs/daily/nutrition` | Daily macro/micronutrient totals |
| `GET` | `/api/v1/logs/daily/hydration` | Daily fluid intake in ml |
| `GET` | `/api/v1/logs/{entry_id}` | Get a single log entry |
| `PATCH` | `/api/v1/logs/{entry_id}` | Update quantity or note |
| `DELETE` | `/api/v1/logs/{entry_id}` | Delete a log entry |

### Example Requests

**Log a beverage (Coca-Cola by barcode):**
```bash
curl -X POST http://localhost:8000/api/v1/logs/ \
  -H "X-API-Key: your-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "5449000000996",
    "source": "open_food_facts",
    "quantity_g": 330
  }'
```

**Log a USDA food item:**
```bash
curl -X POST http://localhost:8000/api/v1/logs/ \
  -H "X-API-Key: your-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "171705",
    "source": "usda_fooddata",
    "quantity_g": 150,
    "note": "Lunch"
  }'
```

**Get today's hydration summary:**
```bash
curl http://localhost:8000/api/v1/logs/daily/hydration \
  -H "X-API-Key: your-key-here"

# Response:
# {
#   "log_date": "2025-06-15",
#   "total_volume_ml": "825.0",
#   "contributing_entries": 3
# }
```

**Get daily nutrition totals for a specific date:**
```bash
curl "http://localhost:8000/api/v1/logs/daily/nutrition?log_date=2025-06-14" \
  -H "X-API-Key: your-key-here"

# Response:
# {
#   "log_date": "2025-06-14",
#   "total_entries": 5,
#   "totals": {
#     "calories_kcal": "1842.30",
#     "protein_g": "98.40",
#     "carbohydrates_g": "210.75",
#     "fat_g": "62.10",
#     "fiber_g": "24.50",
#     "sugar_g": "88.20"
#   }
# }
```

**Update a log entry:**
```bash
curl -X PATCH http://localhost:8000/api/v1/logs/<entry-uuid> \
  -H "X-API-Key: your-key-here" \
  -H "Content-Type: application/json" \
  -d '{"quantity_g": 200, "note": "corrected portion"}'
```

---

## 🚀 Quick Start (Local)

### Prerequisites

- Python 3.12+
- `pip` or `uv`

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-org/nutrition-tracker.git
cd nutrition-tracker

# 2. Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. Create local configuration
cat > .env << 'EOF'
# JSON map of API_KEY -> tenant_id
API_KEYS={"dev-key-alice": "tenant_alice", "dev-key-bob": "tenant_bob"}
USDA_API_KEY=DEMO_KEY
DEBUG=true
CORS_ORIGINS=["*"]
EOF

# 4. Run the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. Open Swagger UI
open http://localhost:8000/docs
```

---

## ⚙️ Configuration

All configuration is managed via environment variables (or a `.env` file). The app uses `pydantic-settings` for typed, validated config loading.

| Variable | Type | Default | Description |
|---|---|---|---|
| `API_KEYS` | `JSON dict` | `{}` | Maps API keys to tenant IDs: `{"key": "tenant_id"}` |
| `USDA_API_KEY` | `string` | `DEMO_KEY` | USDA FoodData Central API key ([get one here](https://fdc.nal.usda.gov/api-key-signup.html)) |
| `DEBUG` | `bool` | `false` | Enables debug logging |
| `CORS_ORIGINS` | `JSON list` | `["*"]` | Allowed CORS origins |
| `RATE_LIMIT_REQUESTS` | `int` | `100` | Max requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `int` | `60` | Rate limit window in seconds |

> ⚠️ **Security Note:** Never commit `.env` to version control. In Kubernetes, inject `API_KEYS` and `USDA_API_KEY` via Kubernetes Secrets (see Helm section below).

---

## 🐳 Docker

### Build

```bash
docker build -t nutrition-tracker:latest .
```

### Run

```bash
docker run -d \
  --name nutrition-tracker \
  -p 8000:8000 \
  -e API_KEYS='{"prod-key-alice":"tenant_alice"}' \
  -e USDA_API_KEY="your-usda-key" \
  nutrition-tracker:latest
```

### Image Details

| Property | Value |
|---|---|
| Base image | `python:3.12-slim` |
| Build strategy | Multi-stage (builder + runtime) |
| Runtime user | Non-root (`uid=1001`) |
| Filesystem | Read-only root (`/tmp` as `emptyDir`) |
| Exposed port | `8000` |
| Shutdown | Graceful via `SIGTERM` (uvicorn native) |

---

## ☸️ Kubernetes / Helm Deployment

### Prerequisites

- Kubernetes cluster (k3s, k8s, etc.)
- Helm 3.x
- `kubectl` configured

### Install

```bash
# 1. Encode your secrets
API_KEYS_B64=$(echo -n '{"your-prod-key":"tenant_alice"}' | base64)
USDA_KEY_B64=$(echo -n 'your-usda-api-key' | base64)

# 2. Install the Helm chart
helm install nutrition-tracker ./deploy/charts/nutrition-tracker \
  --namespace homelab \
  --create-namespace \
  --set image.repository=ghcr.io/your-org/nutrition-tracker \
  --set image.tag=1.0.0 \
  --set secrets.apiKeys="${API_KEYS_B64}" \
  --set secrets.usdaApiKey="${USDA_KEY_B64}" \
  --set ingress.hosts[0].host=nutrition.homelab.local
```

### Upgrade

```bash
helm upgrade nutrition-tracker ./deploy/charts/nutrition-tracker \
  --namespace homelab \
  --set image.tag=1.1.0
```

### Key Helm Values

```yaml
# values.yaml excerpt — most important overrides

replicaCount: 2                  # Minimum for HA

image:
  repository: ghcr.io/your-org/nutrition-tracker
  tag: "1.0.0"

ingress:
  enabled: true
  hosts:
    - host: nutrition.homelab.local

resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"

# Secrets: base64-encoded values
secrets:
  apiKeys: ""       # echo -n '{"key":"tenant"}' | base64
  usdaApiKey: ""    # echo -n 'your-key' | base64
```

### Health Checks

| Probe | Endpoint | Initial Delay | Period |
|---|---|---|---|
| Liveness | `GET /healthz` | 10s | 15s |
| Readiness | `GET /readyz` | 5s | 10s |

---

## 🔄 CI/CD Pipeline

### CI (`.github/workflows/ci.yml`)

Triggers on every push to `main`/`develop` and all pull requests.

```
Push / PR
    │
    ├── lint-and-test
    │   ├── ruff check src/ tests/       (linting)
    │   ├── mypy src/app --strict        (type checking)
    │   ├── pytest tests/unit/           (unit tests + coverage)
    │   └── pytest tests/integration/   (integration tests)
    │
    ├── helm-lint
    │   └── helm lint deploy/charts/nutrition-tracker/
    │
    └── docker-build (PR only)
        └── docker build (no push, validation only)
```

### CD (`.github/workflows/cd.yml`)

Triggers on semantic version tags (`v*.*.*`).

```
git tag v1.2.0 && git push --tags
    │
    ├── build-and-push
    │   ├── docker build --target runtime
    │   └── docker push ghcr.io/your-org/nutrition-tracker:1.2.0
    │
    └── helm-package-and-deploy
        ├── helm lint
        └── helm upgrade --install (homelab environment)
```

### Release Process

```bash
# Bump version in pyproject.toml and Chart.yaml, then:
git tag v1.2.0
git push origin main --tags
# → CD pipeline fires automatically
```

---

## 🧪 Testing

### Run All Tests

```bash
# Unit tests only (fast, no external deps)
pytest tests/unit/ -v

# Integration tests (uses TestClient, still no real HTTP calls)
pytest tests/integration/ -v

# All tests with coverage report
pytest --cov=app --cov-report=term-missing --cov-report=html
open htmlcov/index.html
```

### Test Architecture

| Layer | Location | Strategy |
|---|---|---|
| **Unit** | `tests/unit/` | Mock `httpx.AsyncClient`; test adapter normalization and service logic in isolation |
| **Integration** | `tests/integration/` | FastAPI `TestClient`; full HTTP cycle with overridden `get_settings()` dependency |

### Coverage Targets

| Module | Target |
|---|---|
| `adapters/` | ≥ 90% (normalization branches) |
| `services/` | ≥ 95% (tenant isolation, aggregation) |
| `api/` | ≥ 85% (HTTP status codes, auth failures) |
| `domain/` | 100% (pure logic, no I/O) |

### Adding a New Adapter (Test-Driven)

```bash
# 1. Write the failing test first
tests/unit/test_adapters.py::test_new_source_normalizes_correctly

# 2. Implement the adapter
src/app/adapters/new_source.py

# 3. Register in dependencies.py
# 4. Add DataSource enum value in models.py
```

---

## 🤖 AI Agent Guide

> **This section is specifically written for AI coding assistants (GitHub Copilot, Cursor, Claude, etc.) to understand the project context quickly and contribute effectively.**

### Mental Model

This project is a **hexagonal architecture** FastAPI service. The core invariant is: **business logic never imports from adapters, and adapters never import from services.** Data flows inward through the `ProductSourcePort` interface.

### Critical Files to Read First

| File | Why |
|---|---|
| `src/app/domain/models.py` | The single source of truth for all data shapes. Read this before touching any other file. |
| `src/app/domain/ports.py` | Defines the adapter contract. Any new data source must implement `ProductSourcePort`. |
| `src/app/api/dependencies.py` | Central DI wiring. If you add a new service or adapter, register it here. |
| `src/app/core/config.py` | All environment variables. If you need a new config value, add it here first. |

### How to Add a New External Data Source

1. Create `src/app/adapters/my_source.py`
2. Implement `ProductSourcePort` (both `fetch_by_id` and `search`)
3. Add `MY_SOURCE = "my_source"` to `DataSource` enum in `models.py`
4. Add factory function to `dependencies.py`
5. Register in `get_adapter_registry()` in `dependencies.py`
6. Add unit tests in `tests/unit/test_adapters.py` with mocked `httpx.AsyncClient`

```python
# Minimal adapter skeleton
class MySourceAdapter(ProductSourcePort):
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    async def fetch_by_id(self, product_id: str) -> GeneralizedProduct:
        # 1. HTTP GET to your external API
        # 2. Parse raw response into internal Pydantic raw model
        # 3. Call self._normalize(raw) → GeneralizedProduct
        ...

    async def search(self, query: str, limit: int = 10) -> list[GeneralizedProduct]:
        ...

    def _normalize(self, raw: ...) -> GeneralizedProduct:
        # ALWAYS return GeneralizedProduct — never return raw external types
        # Set is_liquid=True and volume_ml_per_100g=Decimal("100") for beverages
        # Use _safe_decimal() helper for nullable float → Decimal conversion
        ...
```

### How to Add a New API Endpoint

1. Add route to `src/app/api/v1/logs.py` (or create a new router file)
2. Use `Annotated[str, Security(get_tenant_id)]` for the tenant dep — **always**
3. All business logic goes in `LogService`, not in the router
4. Write integration test in `tests/integration/test_api_logs.py`

### Tenant Isolation Rules — Never Violate These

- Every `LogRepository` method takes `tenant_id: str` as first argument
- `tenant_id` is **always** derived from `get_tenant_id()` security dependency
- **Never** accept `tenant_id` as a query/body parameter from the client
- Cross-tenant queries are architecturally prevented by the repository layer

### Unit Conversion Conventions

| Source | Field | Unit in API | Conversion |
|---|---|---|---|
| Open Food Facts | `sodium_100g` | grams | multiply × 1000 → mg |
| Open Food Facts | `energy-kcal_100g` | kcal | no conversion |
| USDA | `sodium` (nutrient 1093) | mg | no conversion |
| All sources | Macros | per 100g | scaled by `quantity_g / 100` in `scaled_macros` |
| All liquids | Volume | ml | `volume_ml_per_100g * (quantity_g / 100)` |

### Common Pitfalls

```python
# ❌ WRONG: Importing adapter in service
from app.adapters.open_food_facts import OpenFoodFactsAdapter  # Never in services/

# ✅ CORRECT: Depend on the port interface only
from app.domain.ports import ProductSourcePort

# ❌ WRONG: Using float for nutritional values
calories: float = 42.0

# ✅ CORRECT: Always use Decimal for financial/nutritional precision
from decimal import Decimal
calories: Decimal = Decimal("42.0")

# ❌ WRONG: Directly accessing repository in router
from app.repositories.log_repository import InMemoryLogRepository  # Never in API layer

# ✅ CORRECT: Always go through the service
from app.services.log_service import LogService
```

### Replacing the In-Memory Repository

The `InMemoryLogRepository` is a placeholder. To switch to a real database:

1. Create `src/app/repositories/postgres_log_repository.py`
2. Implement the same public interface (same method signatures as `InMemoryLogRepository`)
3. Update `get_log_repository()` in `dependencies.py`
4. No changes needed in `LogService` — it's fully decoupled

```python
# The interface contract (implicit — no ABC currently, but these are the required methods):
def save(self, entry: LogEntry) -> LogEntry: ...
def find_by_id(self, tenant_id: str, entry_id: str) -> LogEntry | None: ...
def find_by_date(self, tenant_id: str, log_date: date) -> list[LogEntry]: ...
def delete(self, tenant_id: str, entry_id: str) -> bool: ...
def update(self, entry: LogEntry) -> LogEntry: ...
```

### Environment for Local Development

```bash
# Minimum viable .env for local dev
API_KEYS={"dev-key":"tenant_dev"}
USDA_API_KEY=DEMO_KEY      # 1000 req/hour limit — sufficient for dev
DEBUG=true
```

---

## 📐 Design Decisions & ADRs

### ADR-001: Static API Keys over JWT

**Decision:** Use static `X-API-Key` header auth instead of JWT/OAuth2.
**Rationale:** Homelab context — no auth server available. Static keys provide sufficient security for a single-user or family deployment. Replace with OAuth2 + Keycloak for enterprise use.
**Consequence:** Key rotation requires a config update and pod restart.

### ADR-002: Decimal over float for nutritional values

**Decision:** All nutritional values use `decimal.Decimal`.
**Rationale:** Floating-point arithmetic accumulates errors over many log entries. Daily totals must be precise. `Decimal("0.1") + Decimal("0.2") == Decimal("0.3")` is true; the float equivalent is false.

### ADR-003: In-Memory Repository as default

**Decision:** Ship with `InMemoryLogRepository` as the default, designed for easy replacement.
**Rationale:** Minimizes external dependencies for homelab/single-node deployments. The repository interface is stable — replacing the implementation is a one-file change.

### ADR-004: Embedded product snapshot in LogEntry

**Decision:** `LogEntry` stores a full `GeneralizedProduct` snapshot, not just a product ID reference.
**Rationale:** External product data changes over time (OFF community edits, USDA corrections). Historical log accuracy requires capturing the nutritional values at the time of logging.

### ADR-005: is_liquid flag over category hierarchy

**Decision:** A simple `is_liquid: bool` flag drives hydration tracking rather than food category hierarchies.
**Rationale:** Keeps the domain model simple. Heuristic detection in adapters (PNNS groups for OFF, food category for USDA) covers 95% of cases. Edge cases can be overridden manually.

---

## 🗺 Roadmap

- [ ] **Persistent storage:** SQLite via SQLAlchemy (single-file, zero-ops for homelab)
- [ ] **Product caching:** Redis or in-memory TTL cache to avoid redundant external API calls
- [ ] **Search endpoint:** `GET /api/v1/products/search?q=banana&source=open_food_facts`
- [ ] **Weekly/monthly aggregation:** Trend endpoints for nutrition over time
- [ ] **Manual product entry:** `POST /api/v1/products` with `source: manual`
- [ ] **Export:** `GET /api/v1/logs/export?format=csv&from=...&to=...`
- [ ] **Goals tracking:** Daily targets for calories, protein, water intake
- [ ] **Formal Repository ABC:** Introduce `AbstractLogRepository` to make the interface contract explicit

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details. :D

---

*Built for the homelab. Designed for the enterprise.*
