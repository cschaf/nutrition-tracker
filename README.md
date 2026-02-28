# 🥗 Nutrition & Hydration Tracking API

> A cloud-native, multi-tenant REST API for tracking daily nutrition and hydration intake.
> Built with FastAPI, Python 3.12, and designed for Kubernetes/Homelab deployment via FluxCD.

[![CI Pipeline](https://img.shields.io/github/actions/workflow/status/cschaf/nutrition-tracker/ci.yml?label=CI&logo=github)](/.github/workflows/ci.yml)
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
- [Linting & Code Quality](#-linting--code-quality)
- [Docker](#-docker)
- [Kubernetes / Helm Deployment](#-kubernetes--helm-deployment)
- [CI/CD Pipeline](#-cicd-pipeline)
- [Testing](#-testing)
- [AI Agent Guide](#-ai-agent-guide)
- [Design Decisions & ADRs](#-design-decisions--adrs)
- [Roadmap](#-roadmap)
- [Feature Implementation Prompts](#-feature-implementation-prompts)

---

## 🌐 Overview

This API enables users to log consumed food and beverages, automatically fetching and normalizing nutritional data from **two external sources** (Open Food Facts & USDA FoodData Central). It provides separate daily aggregation endpoints for **nutrition totals** and **hydration tracking**.

### Key Features

| Feature | Detail |
|---|---|
| **Multi-Tenancy** | Strict data isolation per user via static API keys |
| **Adapter Pattern** | Source-agnostic product normalization (OFF + USDA + Manual) |
| **Hydration Tracking** | Separate liquid volume aggregation in ml with range reports |
| **Nutrition Aggregation** | Daily & range macro/micronutrient totals |
| **CRUD Logging** | Full create/read/update/delete for daily log entries |
| **SQLite Persistence** | Async SQLAlchemy + aiosqlite — survives restarts, zero-ops for homelab |
| **Product Cache** | In-process TTL cache to reduce external API calls |
| **Barcode Lookup** | `GET /api/v1/products/barcode/{code}` — auto-detects source, configurable fallback order |
| **Manual Products** | Create custom products without any external API |
| **Meal Templates** | Save named groups of entries for one-click re-logging |
| **Daily Goals** | Set per-tenant macro + hydration targets and track progress |
| **CSV Export** | Streaming export for any date range |
| **Prometheus Metrics** | `/metrics` endpoint for Grafana dashboards |
| **Webhook Notifications** | Push to ntfy.sh or Gotify on goal milestones |
| **Rate Limiting** | Per-IP via slowapi |
| **CORS** | Configurable allowed origins |
| **Production-Ready** | Multi-stage Docker, Helm charts, health-checks, graceful shutdown |

---

## 🏛 Architecture

### System Overview

```
HTTP Request
     │
     ▼
┌──────────────────────────────────────────────────────────────────┐
│  FastAPI Layer                                                   │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  API-Key Auth   │  │ Rate Limiter │  │ Prometheus         │  │
│  │  (X-API-Key)    │  │  (slowapi)   │  │ Middleware         │  │
│  └────────┬────────┘  └──────────────┘  └────────────────────┘  │
│           │                                                      │
│  ┌────────▼─────────────────────────────────────────────────┐   │
│  │  Routers  /logs  /products  /goals  /templates  /metrics │   │
│  └────────────────────────────┬─────────────────────────────┘   │
└───────────────────────────────┼──────────────────────────────────┘
                                │
          ┌─────────────────────┼──────────────────────┐
          │                     │                      │
┌─────────▼──────────┐ ┌───────▼────────┐  ┌──────────▼──────────┐
│    LogService      │ │  GoalsService  │  │  TemplateService    │
│  (tenant-isolated) │ │                │  │                     │
└──────┬─────────────┘ └───────┬────────┘  └──────────┬──────────┘
       │                       │                      │
       │               ┌───────▼────────┐             │
       │               │GoalsRepository │             │
       │               │  (in-memory)   │             │
       │               └────────────────┘             │
       │                                              │
       ├───────────────────────┐          ┌───────────┘
       │                       │          │
┌──────▼──────────┐   ┌────────▼──────────────────────────────┐
│ SQLiteLogRepo   │   │          Service Layer                │
│ (aiosqlite)     │   │  ┌──────────────┐  ┌───────────────┐  │
└─────────────────┘   │  │BarcodeService│  │ ExportService │  │
                      │  └──────┬───────┘  └───────────────┘  │
                      │         │                              │
                      │  ┌──────▼──────────────────────────┐  │
                      │  │  ProductCache (TTL, in-process) │  │
                      │  └──────┬──────────────────────────┘  │
                      │         │  cache miss                  │
                      │  ┌──────▼──────────────────────────┐  │
                      │  │       Adapter Registry          │  │
                      │  │  ┌───────────┐  ┌────────────┐  │  │
                      │  │  │OFF Adapter│  │USDA Adapter│  │  │
                      │  │  ├───────────┤  ├────────────┤  │  │
                      │  │  │  Manual   │  │            │  │  │
                      │  │  │  Adapter  │  │            │  │  │
                      │  │  └─────┬─────┘  └─────┬──────┘  │  │
                      │  └────────┼───────────────┼─────────┘  │
                      │           │  ProductSourcePort          │
                      └───────────┼─────────────────────────────┘
                                  │
                    ┌─────────────┴──────────────┐
                    │                            │
           ┌────────▼────────┐        ┌──────────▼───────┐
           │ Open Food Facts │        │  USDA FoodData   │
           │      API        │        │   Central API    │
           └─────────────────┘        └──────────────────┘

Side channels (fire-and-forget / scrape):
  LogService ──► NotificationService ──► ntfy.sh / Gotify
  Middleware ──► Prometheus metrics  ──► GET /metrics ──► Grafana
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
│       └── cd.yml              # Docker Build/Push to GHCR on git tag
│
├── src/
│   └── app/
│       ├── main.py             # FastAPI app factory, lifespan, middleware, /metrics
│       ├── core/
│       │   ├── config.py       # Pydantic Settings (env-based configuration)
│       │   ├── metrics.py      # Prometheus counters/histograms (module-level singletons)
│       │   └── security.py     # API-Key validation dependency → returns tenant_id
│       ├── domain/
│       │   ├── models.py       # ALL Pydantic schemas: GeneralizedProduct, LogEntry, Goals, Templates
│       │   └── ports.py        # Abstract interfaces + custom domain exceptions
│       ├── adapters/
│       │   ├── manual.py           # Manual product adapter (delegates to ManualProductRepository)
│       │   ├── open_food_facts.py  # OFF API adapter (barcode/search → GeneralizedProduct)
│       │   └── usda_fooddata.py    # USDA API adapter (fdcId/search → GeneralizedProduct)
│       ├── services/
│       │   ├── barcode_service.py      # Configurable-order barcode lookup across adapters
│       │   ├── export_service.py       # Streaming CSV generation
│       │   ├── goals_service.py        # Daily goals CRUD + progress calculation
│       │   ├── log_service.py          # Core logging: CRUD + daily aggregations + notifications
│       │   ├── notification_service.py # Fire-and-forget webhooks (ntfy.sh / Gotify)
│       │   ├── product_cache.py        # In-process TTL cache for GeneralizedProduct
│       │   ├── product_service.py      # Manual product creation
│       │   └── template_service.py     # Meal template CRUD + one-click re-logging
│       ├── api/
│       │   ├── dependencies.py # DI factory functions for all services, repositories, adapters
│       │   └── v1/
│       │       ├── router.py       # Mounts all v1 sub-routers under /api/v1
│       │       ├── goals.py        # GET/PUT/PATCH /goals + /goals/progress
│       │       ├── logs.py         # /logs CRUD + daily summaries + range aggregations + export
│       │       ├── products.py     # /products/search + /products/barcode/{code} + POST /products
│       │       └── templates.py    # /templates CRUD + /templates/{id}/log
│       └── repositories/
│           ├── base.py                     # AbstractLogRepository (ABC)
│           ├── goals_repository.py         # In-memory per-tenant goals store
│           ├── log_repository.py           # In-memory log store (legacy / tests)
│           ├── manual_product_repository.py # In-memory manual product store
│           ├── sqlite_log_repository.py    # Async SQLite via SQLAlchemy + aiosqlite
│           └── template_repository.py      # In-memory per-tenant template store
│
├── tests/
│   ├── conftest.py             # Shared fixtures: test client, in-memory SQLite settings, auth headers
│   ├── unit/
│   │   ├── test_adapters.py        # Adapter normalization (OFF, USDA, Manual) — mocked HTTP
│   │   ├── test_barcode_service.py # Fallback order, error propagation
│   │   ├── test_export_service.py  # CSV header, zero-value handling, scaling
│   │   ├── test_goals_service.py   # Goals CRUD + progress calculation
│   │   ├── test_log_service.py     # Service business logic (tenant isolation, aggregation)
│   │   ├── test_metrics.py         # Prometheus counter increments
│   │   ├── test_models.py          # Domain model validators, computed properties
│   │   ├── test_notification_service.py  # ntfy / Gotify payload, disabled webhook
│   │   ├── test_product_cache.py   # Cache hit/miss/TTL expiry
│   │   ├── test_sqlite_repository.py     # Async SQLite CRUD + tenant isolation
│   │   └── test_template_service.py      # Template CRUD + tenant isolation
│   └── integration/
│       ├── test_api_export.py      # /logs/export streaming CSV
│       ├── test_api_goals.py       # /goals and /goals/progress endpoints
│       ├── test_api_logs.py        # Full HTTP cycle: CRUD, nutrition/hydration summaries, ranges
│       ├── test_api_products.py    # /products/search, /products/barcode, POST /products
│       └── test_api_templates.py   # /templates CRUD + /log
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
├── AGENTS.md                   # AI contributor guide (read before coding)
├── Dockerfile                  # Multi-stage: builder + runtime, non-root user
├── .dockerignore
├── .pre-commit-config.yaml     # ruff auto-fix on every local commit
├── pyproject.toml              # Project metadata, deps, dev deps, tool configs
└── README.md                   # This file
```

---

## 🧩 Domain Model

### Core Entities

```
GeneralizedProduct (frozen, source-agnostic)
│
├── id: str                        # Source-native ID (barcode or fdcId)
├── source: DataSource             # StrEnum: OPEN_FOOD_FACTS | USDA_FOODDATA | MANUAL
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
├── product: GeneralizedProduct    # Embedded snapshot at time of logging
├── quantity_g: Decimal
├── consumed_at: datetime (UTC)
├── note: str | None
│
├── [property] scaled_macros       # Absolute macros for quantity_g
└── [property] consumed_volume_ml  # ml if is_liquid, else None
```

### Data Flow: External API → Internal Domain

```
POST /api/v1/logs  { product_id: "5449000000996", source: "open_food_facts", quantity_g: 330 }
        │
        ▼
LogService.create_entry()
        │
        ▼
AdapterRegistry[DataSource.OPEN_FOOD_FACTS].fetch_by_id("5449000000996")
        │   HTTP GET → world.openfoodfacts.org
        │   Parse _OffResponse → normalize → GeneralizedProduct
        ▼
LogEntry(tenant_id="tenant_alice", product=..., quantity_g=330)
        │
        ▼
InMemoryLogRepository.save(entry)
        │
        ▼
HTTP 201 Created
```

---

## 📡 API Reference

**Base URL:** `http://localhost:8000`
**Auth Header:** `X-API-Key: <your-key>`
**Versioning:** URI-based (`/api/v1/`)
**Docs:** `/docs` (Swagger UI) | `/redoc` (ReDoc)

### Endpoints

#### System

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/healthz` | — | Liveness check |
| `GET` | `/readyz` | — | Readiness check |
| `GET` | `/metrics` | — | Prometheus metrics (scrape target for Grafana) |

#### Log Entries

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/logs/` | Create a new log entry |
| `GET` | `/api/v1/logs/daily` | All entries for today (or `?log_date=YYYY-MM-DD`) |
| `GET` | `/api/v1/logs/daily/nutrition` | Daily macro/micronutrient totals |
| `GET` | `/api/v1/logs/daily/hydration` | Daily fluid intake in ml |
| `GET` | `/api/v1/logs/range/nutrition` | Nutrition totals for a date range (`?from=&to=`) |
| `GET` | `/api/v1/logs/range/hydration` | Hydration totals for a date range (`?from=&to=`) |
| `GET` | `/api/v1/logs/export` | Streaming CSV export for a date range (`?from=&to=`) |
| `GET` | `/api/v1/logs/{entry_id}` | Get a single log entry |
| `PATCH` | `/api/v1/logs/{entry_id}` | Update quantity or note |
| `DELETE` | `/api/v1/logs/{entry_id}` | Delete a log entry |

#### Products

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/products/search` | Search products (`?q=&source=&limit=`) |
| `GET` | `/api/v1/products/barcode/{code}` | Lookup by barcode — auto-detects source |
| `POST` | `/api/v1/products` | Create a manual product (HTTP 201) |

#### Goals

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/goals` | Get current daily goals |
| `PUT` | `/api/v1/goals` | Replace daily goals |
| `PATCH` | `/api/v1/goals` | Partially update daily goals |
| `GET` | `/api/v1/goals/progress` | Today's actual vs. target (`?date=YYYY-MM-DD`) |

#### Meal Templates

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/templates` | List all meal templates |
| `POST` | `/api/v1/templates` | Create a new template (HTTP 201) |
| `DELETE` | `/api/v1/templates/{template_id}` | Delete a template (HTTP 204) |
| `POST` | `/api/v1/templates/{template_id}/log` | Log all entries from a template (`?date=YYYY-MM-DD`) |

> All `/api/v1/` endpoints require `X-API-Key` header authentication.

### Example Requests

**Log a beverage (Coca-Cola by barcode):**
```powershell
# PowerShell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/logs/" `
  -Method POST `
  -Headers @{"X-API-Key"="your-key-here"; "Content-Type"="application/json"} `
  -Body '{"product_id":"5449000000996","source":"open_food_facts","quantity_g":330}'
```

```bash
# bash/curl
curl -X POST http://localhost:8000/api/v1/logs/ \
  -H "X-API-Key: your-key-here" \
  -H "Content-Type: application/json" \
  -d '{"product_id":"5449000000996","source":"open_food_facts","quantity_g":330}'
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

**Get daily nutrition totals:**
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
#     "fat_g": "62.10"
#   }
# }
```

---

## 🚀 Quick Start (Local)

### Prerequisites

- Python 3.12+
- pip

### Setup

```bash
# 1. Clone
git clone https://github.com/your-org/nutrition-tracker.git
cd nutrition-tracker

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1

# 3. Install
pip install -e ".[dev]"

# 4. Install pre-commit hooks (runs ruff automatically on every commit)
pip install pre-commit
pre-commit install

# 5. Create .env
cat > .env << 'EOF'
API_KEYS={"dev-key-alice": "tenant_alice", "dev-key-bob": "tenant_bob"}
USDA_API_KEY=DEMO_KEY
DATABASE_URL=sqlite+aiosqlite:///nutrition_tracker.db
DEBUG=true
CORS_ORIGINS=["*"]
EOF

# 6. Run
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 7. Open docs
open http://localhost:8000/docs
```

---

## ⚙️ Configuration

All configuration via environment variables or `.env`. Managed by `pydantic-settings`.

| Variable | Type | Default | Description |
|---|---|---|---|
| `API_KEYS` | JSON dict | `{}` | Maps API keys to tenant IDs: `{"key": "tenant_id"}` |
| `USDA_API_KEY` | string | `DEMO_KEY` | USDA FoodData Central API key ([signup](https://fdc.nal.usda.gov/api-key-signup.html)) |
| `DATABASE_URL` | string | `sqlite+aiosqlite:///nutrition_tracker.db` | SQLAlchemy async connection URL |
| `DEBUG` | bool | `false` | Enables debug logging |
| `CORS_ORIGINS` | JSON list | `["*"]` | Allowed CORS origins |
| `RATE_LIMIT_REQUESTS` | int | `100` | Max requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | int | `60` | Rate limit window in seconds |
| `CACHE_TTL_SECONDS` | int | `3600` | Product cache TTL (1 hour default) |
| `BARCODE_LOOKUP_ORDER` | JSON list | `["open_food_facts","usda_fooddata"]` | Adapter fallback order for barcode lookups |
| `WEBHOOK_ENABLED` | bool | `false` | Enable webhook notifications |
| `WEBHOOK_URL` | string | `null` | Target URL for ntfy.sh or Gotify |

> ⚠️ Never commit `.env`. In Kubernetes, inject secrets via Helm `--set secrets.*` or External Secrets Operator.

---

## 🧹 Linting & Code Quality

This project enforces code quality automatically at three levels.

### Local: Pre-commit Hook

Install once after cloning:

```bash
pip install pre-commit
pre-commit install
```

After this, every `git commit` automatically runs ruff. A commit with lint errors is **rejected before it leaves your machine**.

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

### Manual: Run Anytime

```bash
# Fix all auto-fixable issues
ruff check src/ tests/ --fix
ruff check src/ tests/ --fix --unsafe-fixes

# Final check (must be zero errors before pushing)
ruff check src/ tests/

# Type checking
mypy src/app --strict
```

### CI: Automatic on Every Push

The CI pipeline runs ruff with `--fix`, commits any auto-fixes back to the branch, then runs a final check. If manual fixes are still required, the build fails and shows exactly which lines need attention.

### Suppressed Rules

| Rule | File | Reason |
|---|---|---|
| `B008` | `pyproject.toml` | `Depends()` in function signatures is the standard FastAPI DI pattern |

---

## 🐳 Docker

### Build

```bash
docker build -t nutrition-tracker:latest .
```

### Run (PowerShell)

```powershell
docker run -d `
  --name nutrition-tracker `
  -p 8000:8000 `
  -e API_KEYS='{"prod-key-alice":"tenant_alice"}' `
  -e USDA_API_KEY="your-usda-key" `
  nutrition-tracker:latest
```

### Run (bash)

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
| Shutdown | Graceful via `SIGTERM` |

---

## ☸️ Kubernetes / Helm Deployment

Deployment to the homelab k3s cluster is handled by **FluxCD**. Never deploy manually after the initial install.

### Initial Install (once)

```powershell
# From your machine with kubectl access to the cluster

# Create namespace
kubectl create namespace homelab

# Create secrets
kubectl create secret generic nutrition-tracker-secret `
  --namespace homelab `
  --from-literal=api-keys='{"your-prod-key":"tenant_alice"}' `
  --from-literal=usda-api-key="your-usda-key"

# Helm install
helm upgrade --install nutrition-tracker ./deploy/charts/nutrition-tracker `
  --namespace homelab `
  --set image.repository=ghcr.io/YOUR-GITHUB-USERNAME/nutrition-tracker `
  --set image.tag=latest
```

After this, FluxCD takes over. Push a new tag → CI builds the image → FluxCD rolls it out automatically.

### Key Helm Values

```yaml
replicaCount: 2

image:
  repository: ghcr.io/your-username/nutrition-tracker
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
```

### Health Checks

| Probe | Endpoint | Initial Delay | Period |
|---|---|---|---|
| Liveness | `GET /healthz` | 10s | 15s |
| Readiness | `GET /readyz` | 5s | 10s |

---

## 🔄 CI/CD Pipeline

### CI (every push to `main` and PRs)

```
Push / PR
    │
    ├── ruff --fix (auto-commits fixes)
    ├── ruff check (fails if manual fixes needed)
    ├── mypy --strict
    ├── pytest tests/unit/
    ├── pytest tests/integration/
    └── helm lint
```

### CD (on `git tag v*.*.*`)

```
git tag v1.2.0 && git push --tags
    │
    ├── Docker build
    └── Push ghcr.io/your-username/nutrition-tracker:1.2.0
                          │
                    FluxCD polls ghcr.io
                          │
                    kubectl rollout (automatic)
```

### Release — How to Trigger the CD Pipeline

The CD workflow is **only triggered by a Git tag** matching `v*.*.*`. A regular `git push` to `main` never triggers it.

**Required flow — do not skip steps:**

```powershell
# Step 1: Make sure everything is committed and pushed
git status
git push origin main

# Step 2: Wait for CI (ci.yml) to go green on GitHub Actions
# → github.com/your-username/nutrition-tracker/actions
# Never tag a commit that has failing CI

# Step 3: Create and push the tag — this triggers cd.yml
git tag v1.0.0
git push origin v1.0.0
```

After `git push origin v1.0.0` the CD workflow appears under GitHub Actions within seconds.

**If you need to redo a tag:**

```powershell
# Delete locally
git tag -d v1.0.0

# Delete on remote
git push origin --delete v1.0.0

# Re-create and push
git tag v1.0.0
git push origin v1.0.0
```

**List all existing tags:**

```powershell
git tag -l
```

**Versioning convention:** follow [Semantic Versioning](https://semver.org).

| Change type | Example |
|---|---|
| Bug fix | `v1.0.1` |
| New feature (backwards compatible) | `v1.1.0` |
| Breaking change | `v2.0.0` |

### GitHub Repository Settings Required

| Setting | Value |
|---|---|
| `Settings → Actions → Permissions` | Read and write permissions |
| `Settings → Environments` | Create environment named `homelab` |
| ghcr.io Package visibility | Set to **Public** so FluxCD can pull without image pull secret |

---

## 🧪 Testing

```bash
# Unit tests (fast, no external deps)
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# All with coverage
pytest --cov=app --cov-report=term-missing
```

The test suite contains **118 tests** across 16 files (11 unit, 5 integration).

### Test Isolation — In-Memory SQLite

Every integration test uses an isolated in-memory SQLite database (`sqlite+aiosqlite:///:memory:`) via the `test_settings` fixture in `conftest.py`. The `client` fixture:

1. Resets the `_repository` singleton before and after each test
2. Uses `app.dependency_overrides[get_settings]` — **not** `unittest.mock.patch` — to inject test settings into FastAPI's DI system
3. Yields a `TestClient` that connects to the in-memory DB

> **Why `app.dependency_overrides` instead of `patch`?** FastAPI captures `Depends()` function object references at import time. `unittest.mock.patch` replaces the name in the module namespace, but FastAPI's DI still calls the original function. `app.dependency_overrides` is the correct mechanism to replace a FastAPI dependency in tests.

For integration tests that need to control service behaviour, use `patch` on the *service method* (not on `get_settings`) and override `get_tenant_id` via `dependency_overrides`:

```python
from app.core.security import get_tenant_id

app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"
try:
    with patch("app.services.log_service.LogService.get_entry", new_callable=AsyncMock) as m:
        m.return_value = None
        response = client.get("/api/v1/logs/some-id", headers={"X-API-Key": "any"})
        assert response.status_code == 404
finally:
    app.dependency_overrides.clear()
```

### Known CI Failure: pytest Exit Code 5

**Exit code 5 = no tests collected.** This happens when a test file exists but contains no `test_` functions — typically when placeholder files are left empty. Every `.py` file under `tests/` (except `conftest.py` and `__init__.py`) must contain at least one test function.

### Known CI Failure: mypy --strict

This project enforces `mypy src/app --strict`. Common patterns that break it are documented in `AGENTS.md` Section 4a with correct/incorrect examples. The most frequent causes of failures are using `str, Enum` instead of `StrEnum`, untyped `dict` for httpx params, raw strings where Enum members are expected, and FastAPI endpoint arguments with `= None` defaults.

### Coverage Targets

| Module | Minimum |
|---|---|
| `domain/` | 100% |
| `services/` | 95% |
| `adapters/` | 90% |
| `api/` | 85% |

---

## 🤖 AI Agent Guide

> AI agents (Claude, Copilot, Cursor, etc.) **must read [`AGENTS.md`](AGENTS.md) before making any changes** to this repository. It contains the complete contributor specification including architecture rules, linting requirements, testing patterns, and common pitfalls.

### Quick Reference for AI

| Task | Where to look |
|---|---|
| All architecture rules | `AGENTS.md` Section 2 |
| Linting requirements | `AGENTS.md` Section 4 |
| **mypy --strict patterns (read before touching any file)** | **`AGENTS.md` Section 4a** |
| Adding a new data source | `AGENTS.md` Section 6 |
| Adding a new endpoint | `AGENTS.md` Section 7 |
| Replacing the repository | `AGENTS.md` Section 8 |
| Unit conversion table | `AGENTS.md` Section 10 |
| **pytest exit code 5 fix + integration test baseline** | **`AGENTS.md` Section 5.4** |
| **FastAPI test isolation (dependency_overrides vs patch)** | **`AGENTS.md` Section 5.6** |
| What NOT to do | `AGENTS.md` Section 12 |

### Critical Files (read in this order)

1. `AGENTS.md` — contributor rules, **especially Section 4a (mypy) and Section 5.4 (pytest)**
2. `src/app/domain/models.py` — all data shapes
3. `src/app/domain/ports.py` — adapter interface contract
4. `src/app/api/dependencies.py` — DI wiring
5. `src/app/core/config.py` — all config values

---

## 📐 Design Decisions & ADRs

### ADR-001: Static API Keys over JWT

**Decision:** `X-API-Key` header auth instead of JWT/OAuth2.
**Rationale:** Homelab context — no auth server. Sufficient for single-user/family deployment.
**Consequence:** Key rotation requires config update and pod restart.

### ADR-002: Decimal over float

**Decision:** All nutritional values use `decimal.Decimal`.
**Rationale:** Float arithmetic accumulates errors. `Decimal("0.1") + Decimal("0.2") == Decimal("0.3")` is true; the float equivalent is false.

### ADR-003: SQLite as default persistence

**Decision:** Default to `SQLiteLogRepository` backed by async SQLAlchemy + aiosqlite. `InMemoryLogRepository` is retained for tests only.
**Rationale:** Zero external dependencies for homelab, survives pod restarts, single `.db` file easy to back up. Interface (defined in `AbstractLogRepository`) is stable — swap to Postgres in one file by changing `DATABASE_URL`.

### ADR-004: Embedded product snapshot in LogEntry

**Decision:** `LogEntry` stores a full `GeneralizedProduct` snapshot.
**Rationale:** External product data changes over time. Historical accuracy requires capturing values at logging time.

### ADR-005: is_liquid flag

**Decision:** Simple `is_liquid: bool` flag instead of category hierarchy.
**Rationale:** Covers 95% of cases with minimal complexity. Edge cases handled by adapter heuristics.

### ADR-006: FluxCD over push-based deploy

**Decision:** FluxCD polls ghcr.io instead of GitHub Actions pushing to the cluster.
**Rationale:** Homelab k3s cluster is not externally reachable. Pull-based GitOps fits the network topology.

---

## 🗺 Roadmap

### 🏗 Infrastructure & Persistence
- [x] **Persistent storage:** SQLite via SQLAlchemy async + aiosqlite (single-file, zero-ops for homelab)
- [x] **Formal Repository ABC:** `AbstractLogRepository` in `repositories/base.py`
- [ ] **Redis cache:** Replace in-memory TTL cache with Redis for persistence across restarts
- [x] **Prometheus metrics:** `GET /metrics` endpoint for Grafana dashboards (request count, external API latency, cache hit rate)
- [ ] **OpenAPI client generation:** Auto-generate typed Python/TypeScript client as part of CI pipeline
- [ ] **Pre-commit config:** Add `mypy` to pre-commit hooks

### 🔍 Product & Data
- [x] **Product search endpoint:** `GET /api/v1/products/search?q=banana&source=open_food_facts`
- [x] **Product caching:** TTL-based in-process cache to avoid redundant external API calls
- [x] **Manual product entry:** `POST /api/v1/products` with `source: manual`
- [x] **Barcode shortcut:** `GET /api/v1/products/barcode/{code}` — auto-detects source, configurable fallback order
- [ ] **Allergen tracking:** Add allergen flags to `GeneralizedProduct` (gluten, lactose, nuts, etc.)
- [ ] **Recipes:** Combine multiple ingredients into a single product with auto-calculated nutrients

### 📊 Logging & Analysis
- [x] **Meal templates:** Save named groups of log entries (e.g. "My usual breakfast") for one-click re-logging
- [x] **Weekly/monthly aggregation:** `GET /api/v1/logs/range/nutrition?from=...&to=...`
- [x] **CSV export:** `GET /api/v1/logs/export?from=...&to=...` (streaming, zero memory overhead)
- [ ] **Weekly PDF report:** Summarized nutrition and hydration report as downloadable PDF
- [ ] **Streak tracking:** How many consecutive days have been logged
- [ ] **Nutrient deficiency warnings:** Alert when a micronutrient stays below threshold for N days

### 🎯 Goals & Progress
- [x] **Daily goals:** `PUT /api/v1/goals` — set targets for calories, macros, water intake
- [x] **Goals progress:** `GET /api/v1/goals/progress?date=...` — actual vs. target with percentage
- [ ] **Body weight logging:** Track weight over time for TDEE-based calorie need calculation
- [ ] **Calorie balance:** Intake vs. expenditure when activity data is available

### 🔔 Notifications & Integrations
- [x] **Webhook notifications:** Push to ntfy.sh or Gotify (homelab-friendly) when daily goal is reached
- [ ] **Rate limiting per tenant:** Replace IP-based rate limiting with per-API-key limits

---

## 🛠 Feature Implementation Prompt Template

> Use this template when starting a new chat session to implement a roadmap feature.
> Fill in the `<FEATURE>` and `<STEPS>` placeholders. The pitfalls listed below are
> pre-documented so the agent avoids the most common CI failures.

```
You are working on the "Nutrition & Hydration Tracking API" project.
Read AGENTS.md in full (especially Sections 4a and 5.6) before writing any code,
then read the relevant source files for the feature you are implementing.

Feature: <FEATURE NAME>

Steps:
<STEPS>

Known pitfalls — apply these rules without being asked:
- Query parameters with alias="from"/"to" must be defined DIRECTLY on the endpoint
  (from_date: date = Query(..., alias="from")), NOT in a Pydantic model via Depends().
- Use StrEnum, not str + Enum (see AGENTS.md 4a.1).
- httpx params dicts must be typed as dict[str, str] (see AGENTS.md 4a.2).
- FastAPI Annotated deps (Depends/Security) never need a = None default (see AGENTS.md 4a.5).
- Every test file must contain at least one test_ function (see AGENTS.md 5.4).
- Use app.dependency_overrides[fn] to replace FastAPI dependencies in tests,
  never unittest.mock.patch on the dependency function (see AGENTS.md 5.6).
- Use Decimal, never float, for all nutritional values (see AGENTS.md 2.3).
- Check Decimal | None fields with "is not None", never bare truthiness (see AGENTS.md 4a.9).

Acceptance criteria (all must pass with zero errors before you are done):
- ruff check src/ tests/
- mypy src/app --strict
- pytest tests/
```

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---

*Built for the homelab. Designed for the enterprise.*