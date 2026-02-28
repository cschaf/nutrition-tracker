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
│       └── cd.yml              # Docker Build/Push to GHCR on git tag
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
| `DEBUG` | bool | `false` | Enables debug logging |
| `CORS_ORIGINS` | JSON list | `["*"]` | Allowed CORS origins |
| `RATE_LIMIT_REQUESTS` | int | `100` | Max requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | int | `60` | Rate limit window in seconds |

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

### Known CI Failure: pytest Exit Code 5

**Exit code 5 = no tests collected.** This happens when a test file exists but contains no `test_` functions — typically when placeholder files are left empty. Every `.py` file under `tests/` (except `conftest.py` and `__init__.py`) must contain at least one test function. The baseline integration tests covering health checks and 401/404 responses are the minimum acceptable content for `tests/integration/test_api_logs.py`.

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

### ADR-003: In-Memory Repository as default

**Decision:** Ship with `InMemoryLogRepository`, designed for easy replacement.
**Rationale:** Zero external dependencies for homelab. Interface is stable — swap to SQLite/Postgres in one file.

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
- [ ] **Persistent storage:** SQLite via SQLAlchemy async + aiosqlite (single-file, zero-ops for homelab)
- [ ] **Formal Repository ABC:** Introduce `AbstractLogRepository` to make the interface contract explicit
- [ ] **Redis cache:** Replace in-memory TTL cache with Redis for persistence across restarts
- [ ] **Prometheus metrics:** `GET /metrics` endpoint for Grafana dashboards (request count, external API latency, cache hit rate)
- [ ] **OpenAPI client generation:** Auto-generate typed Python/TypeScript client as part of CI pipeline
- [ ] **Pre-commit config:** Add `mypy` to pre-commit hooks

### 🔍 Product & Data
- [ ] **Product search endpoint:** `GET /api/v1/products/search?q=banana&source=open_food_facts`
- [ ] **Product caching:** TTL-based cache to avoid redundant external API calls
- [ ] **Manual product entry:** `POST /api/v1/products` with `source: manual`
- [ ] **Barcode shortcut:** `GET /api/v1/products/barcode/{code}` — auto-detects source, no need to specify
- [ ] **Allergen tracking:** Add allergen flags to `GeneralizedProduct` (gluten, lactose, nuts, etc.)
- [ ] **Recipes:** Combine multiple ingredients into a single product with auto-calculated nutrients

### 📊 Logging & Analysis
- [ ] **Meal templates:** Save named groups of log entries (e.g. "My usual breakfast") for one-click re-logging
- [ ] **Weekly/monthly aggregation:** `GET /api/v1/logs/range/nutrition?from=...&to=...`
- [ ] **CSV export:** `GET /api/v1/logs/export?format=csv&from=...&to=...`
- [ ] **Weekly PDF report:** Summarized nutrition and hydration report as downloadable PDF
- [ ] **Streak tracking:** How many consecutive days have been logged
- [ ] **Nutrient deficiency warnings:** Alert when a micronutrient stays below threshold for N days

### 🎯 Goals & Progress
- [ ] **Daily goals:** `PUT /api/v1/goals` — set targets for calories, macros, water intake
- [ ] **Goals progress:** `GET /api/v1/goals/progress?date=...` — actual vs. target with percentage
- [ ] **Body weight logging:** Track weight over time for TDEE-based calorie need calculation
- [ ] **Calorie balance:** Intake vs. expenditure when activity data is available

### 🔔 Notifications & Integrations
- [ ] **Webhook notifications:** Push to ntfy.sh or Gotify (homelab-friendly) when daily goal is reached
- [ ] **Rate limiting per tenant:** Replace IP-based rate limiting with per-API-key limits

---

---

## 🛠 Feature Implementation Prompts

> Use these prompts verbatim in a new chat session to implement each roadmap feature.
> Every prompt instructs the agent to read `AGENTS.md` first and enforces ruff + mypy as hard acceptance criteria.
>
> **Known pitfalls pre-documented in every prompt:**
> - `Query(alias=...)` directly on endpoint parameters — never via `Depends()` with a Pydantic model
> - `StrEnum` instead of `str, Enum`
> - `dict[str, str]` for httpx params
> - `Annotated` deps without `= None` defaults
> - Test files must contain at least one `test_` function (pytest exit code 5)

Use these prompts verbatim in a new chat session to implement each roadmap feature.
Every prompt instructs the agent to read `AGENTS.md` first and enforces ruff + mypy as hard acceptance criteria.

**Known pitfalls pre-documented in every prompt:**
- `Query(alias=...)` directly on endpoint parameters — never via `Depends()` with a Pydantic model
- `StrEnum` instead of `str, Enum`
- `dict[str, str]` for httpx params
- `Annotated` deps without `= None` defaults
- Test files must contain at least one `test_` function (pytest exit code 5)

---

### Prompt 1 — Persistent Storage (SQLite)

```
Du arbeitest am Projekt "Nutrition & Hydration Tracking API".
Lies zuerst AGENTS.md vollständig (insbesondere Abschnitt 4a und 5.4),
dann src/app/repositories/log_repository.py und src/app/api/dependencies.py.

Implementiere eine SQLite-Persistenzschicht als Ersatz für das InMemoryLogRepository.

Technische Vorgaben:
- Verwende SQLAlchemy async + aiosqlite
- Alle Enum-Felder: StrEnum statt str, Enum (siehe AGENTS.md 4a.1)
- Alle dict-Typannotierungen vollständig: dict[str, str] nie dict allein
- Keine = None Defaults bei Annotated FastAPI-Dependencies

Schritte:
1. Erstelle src/app/repositories/base.py mit AbstractLogRepository (ABC).
   Methoden: save(), find_by_id(), find_by_date(), find_by_date_range(), delete(), update()
   Alle mit vollständigen Typannotierungen die mypy --strict bestehen.
2. Aktualisiere src/app/repositories/log_repository.py:
   InMemoryLogRepository erbt von AbstractLogRepository.
3. Erstelle src/app/repositories/sqlite_log_repository.py:
   SQLiteLogRepository erbt von AbstractLogRepository.
   Nutze async Session, mapped_column(), DeclarativeBase.
   Speichere GeneralizedProduct als JSON-Blob (product_json: str).
   Deserialisiere mit GeneralizedProduct.model_validate_json() beim Lesen.
4. Aktualisiere get_log_repository() in src/app/api/dependencies.py
   auf SQLiteLogRepository. Datenbankpfad via Settings: DB_PATH: str = "nutrition.db"
5. Ergänze in pyproject.toml: sqlalchemy[asyncio]>=2.0 und aiosqlite>=0.19
6. Schreibe tests/unit/test_sqlite_repository.py mit pytest-asyncio.
   Nutze eine In-Memory SQLite DB (:memory:) für Tests — nie die produktive DB.
7. Stelle sicher:
   - ruff check src/ tests/ gibt 0 Fehler
   - mypy src/app --strict gibt 0 Fehler
   - pytest tests/unit/test_sqlite_repository.py läuft durch
```

---

### Prompt 2 — Product Cache (TTL)

```
Du arbeitest am Projekt "Nutrition & Hydration Tracking API".
Lies zuerst AGENTS.md vollständig (insbesondere Abschnitt 4a und 5.4),
dann src/app/adapters/open_food_facts.py, src/app/adapters/usda_fooddata.py
und src/app/services/log_service.py.

Implementiere einen TTL-basierten Produkt-Cache.

Technische Vorgaben:
- Kein externes Package (kein Redis, kein cachetools) — reines Python dict mit timestamp
- Cache-Key: f"{source}:{product_id}" als str
- Alle Typannotierungen vollständig für mypy --strict
- Der Cache ist ein Singleton der via DI injiziert wird — nicht als globale Variable

Schritte:
1. Erstelle src/app/services/product_cache.py:
   class ProductCache mit get(key) -> GeneralizedProduct | None und set(key, product).
   TTL-Prüfung beim get(): wenn Eintrag älter als ttl_seconds → None zurückgeben und löschen.
   Interner Store: dict[str, tuple[GeneralizedProduct, float]] (product, timestamp).
2. Ergänze in src/app/core/config.py: CACHE_TTL_SECONDS: int = 3600
3. Ergänze get_product_cache() Factory in src/app/api/dependencies.py.
   ProductCache als Singleton via @lru_cache auf der Factory-Funktion.
4. Injiziere ProductCache in LogService.__init__() als optionalen Parameter:
   cache: ProductCache | None = None
   In create_entry(): vor adapter.fetch_by_id() Cache prüfen, nach Fetch in Cache schreiben.
5. Schreibe tests/unit/test_product_cache.py:
   - test_cache_hit: Produkt liegt im Cache → Adapter wird nicht aufgerufen
   - test_cache_miss: Produkt nicht im Cache → Adapter wird aufgerufen, Ergebnis gecacht
   - test_cache_ttl_expiry: Eintrag nach TTL abgelaufen → Cache-Miss
6. Stelle sicher:
   - ruff check src/ tests/ gibt 0 Fehler
   - mypy src/app --strict gibt 0 Fehler
   - pytest tests/unit/test_product_cache.py läuft durch
```

---

### Prompt 3 — Product Search Endpoint

```
Du arbeitest am Projekt "Nutrition & Hydration Tracking API".
Lies zuerst AGENTS.md vollständig (insbesondere Abschnitt 4a und 5.4),
dann src/app/domain/ports.py, src/app/api/v1/router.py,
src/app/api/v1/logs.py (als Muster für Endpoint-Struktur) und src/app/api/dependencies.py.

Implementiere einen Produkt-Suche Endpoint.

Technische Vorgaben:
- Query-Parameter direkt am Endpoint mit Query(...) — NICHT via Depends(PydanticModel)
  (Depends mit Pydantic Query-Modellen führt zu 422-Fehlern bei Alias-Parametern)
- TenantDep = Annotated[str, Security(get_tenant_id)] — kein = None Default
- Alle dict-Typannotierungen vollständig

Schritte:
1. Erstelle src/app/api/v1/products.py:
   GET /api/v1/products/search
   Query-Parameter direkt:
     q: str = Query(..., min_length=1, max_length=200)
     source: DataSource = Query(...)
     limit: int = Query(default=10, ge=1, le=20)
   Ruft adapter.search(query=q, limit=limit) aus der AdapterRegistry auf.
   Gibt list[GeneralizedProduct] zurück.
   Fehlerbehandlung:
     - KeyError bei unbekannter Source → HTTP 400
     - ExternalApiError → HTTP 502 mit detail
2. Registriere in src/app/api/v1/router.py:
   from app.api.v1 import products
   api_router.include_router(products.router, prefix="/products", tags=["Products"])
3. Schreibe tests/integration/test_api_products.py mit mindestens:
   - test_search_requires_auth → 403
   - test_search_invalid_source → 400
   - test_search_success (Mock den Adapter via dependency_overrides)
4. Stelle sicher:
   - ruff check src/ tests/ gibt 0 Fehler
   - mypy src/app --strict gibt 0 Fehler
   - pytest tests/integration/test_api_products.py läuft durch
```

---

### Prompt 4 — Weekly/Monthly Aggregation

```
Du arbeitest am Projekt "Nutrition & Hydration Tracking API".
Lies zuerst AGENTS.md vollständig (insbesondere Abschnitt 4a und 5.4),
dann src/app/services/log_service.py, src/app/repositories/base.py
(oder log_repository.py falls base.py noch nicht existiert) und src/app/api/v1/logs.py.

Implementiere Trend-Endpunkte für Zeitraum-Aggregationen.

KRITISCH — Query-Parameter Alias-Problem:
FastAPI Query-Parameter mit alias="from" müssen DIREKT am Endpoint-Parameter
definiert werden, NICHT in einem Pydantic-Modell via Depends().
"from" ist ein Python-Keyword — intern als from_date benennen, alias="from" setzen.
Falsche Variante (führt zu 422):
  class DateRangeParams(BaseModel):
      from_date: date = Field(alias="from")  # FUNKTIONIERT NICHT mit Depends()
Korrekte Variante:
  from_date: date = Query(..., alias="from")  # direkt am Endpoint-Parameter

Technische Vorgaben:
- Alle Typannotierungen vollständig für mypy --strict
- StrEnum statt str, Enum
- TenantDep ohne = None Default

Schritte:
1. Ergänze find_by_date_range(tenant_id: str, start_date: date, end_date: date)
   in AbstractLogRepository (base.py) und beiden Implementierungen.
2. Ergänze in LogService:
   get_nutrition_range(tenant_id, start_date, end_date) -> list[DailyNutritionSummary]
   get_hydration_range(tenant_id, start_date, end_date) -> list[DailyHydrationSummary]
   Refaktoriere gemeinsame Logik in private Hilfsmethoden.
3. Neue Endpunkte in src/app/api/v1/logs.py:
   GET /api/v1/logs/range/nutrition?from=2025-01-01&to=2025-01-31
   GET /api/v1/logs/range/hydration?from=2025-01-01&to=2025-01-31
   Parameter DIREKT am Endpoint:
     from_date: date = Query(..., alias="from")
     to_date: date = Query(..., alias="to")
   Validierung im Endpoint-Body (nicht im Schema):
     if from_date > to_date → HTTP 400
     if (to_date - from_date).days > 366 → HTTP 400
4. DateRangeParams Schema in domain/models.py darf als Dokumentationsschema
   existieren, aber NICHT als Depends()-Modell im Endpoint verwendet werden.
5. Schreibe tests/unit/test_log_service.py (range-Methoden) und
   tests/integration/test_api_logs.py:
   Integrationstest-URLs mit params={"from": "...", "to": "..."}
   — NICHT als Query-String in der URL hartcodieren.
6. Stelle sicher:
   - ruff check src/ tests/ gibt 0 Fehler
   - mypy src/app --strict gibt 0 Fehler
   - pytest läuft durch ohne 422-Fehler
```

---

### Prompt 5 — Manual Product Entry

```
Du arbeitest am Projekt "Nutrition & Hydration Tracking API".
Lies zuerst AGENTS.md vollständig (insbesondere Abschnitt 4a und 5.4),
dann src/app/domain/models.py und src/app/api/v1/products.py
(anlegen falls nicht vorhanden — siehe Prompt 3 als Muster).

Implementiere manuellen Produkteintrag ohne externe API.

Technische Vorgaben:
- DataSource.MANUAL muss in der StrEnum vorhanden sein
- id wird als str(uuid.uuid4()) generiert — nicht als UUID-Typ (mypy-Kompatibilität)
- Alle Typannotierungen vollständig für mypy --strict

Schritte:
1. Stelle sicher dass DataSource(StrEnum) den Wert MANUAL = "manual" enthält.
2. Neues Schema ManualProductCreate in src/app/domain/models.py:
   Felder: name, brand, macronutrients, micronutrients, is_liquid, volume_ml_per_100g
   (identisch zu GeneralizedProduct ohne id, source, barcode).
3. Neue Methode in einem ManualProductService oder direkt als Funktion:
   def create_manual_product(payload: ManualProductCreate) -> GeneralizedProduct
   Setzt source=DataSource.MANUAL, generiert id=str(uuid.uuid4()).
4. POST /api/v1/products in src/app/api/v1/products.py:
   Body: ManualProductCreate, Response: GeneralizedProduct (HTTP 201)
   Das zurückgegebene Produkt kann direkt in POST /api/v1/logs/ genutzt werden:
   {"product_id": "<uuid>", "source": "manual", "quantity_g": 150}
5. Entscheide ob manuelle Produkte persistent gespeichert werden:
   Option A (empfohlen für Homelab): In-Memory ManualProductRepository (dict[str, GeneralizedProduct])
   Option B: Nur als Response zurückgeben, keine Persistenz
   Dokumentiere die Entscheidung als Kommentar-ADR in der Datei.
6. Schreibe Integrationstests in tests/integration/test_api_products.py.
7. Stelle sicher:
   - ruff check src/ tests/ gibt 0 Fehler
   - mypy src/app --strict gibt 0 Fehler
   - pytest läuft durch
```

---

### Prompt 6 — CSV Export

```
Du arbeitest am Projekt "Nutrition & Hydration Tracking API".
Lies zuerst AGENTS.md vollständig (insbesondere Abschnitt 4a und 5.4),
dann src/app/services/log_service.py, src/app/domain/models.py
und src/app/api/v1/logs.py.

Implementiere einen CSV-Export-Endpoint.

KRITISCH 1 — Query-Parameter Alias-Problem (identisch zu Prompt 4):
from_date: date = Query(..., alias="from") direkt am Endpoint — nie via Depends(Model).

KRITISCH 2 — Decimal("0") Truthiness-Problem (siehe AGENTS.md 4a.9):
Alle optionalen Decimal-Felder (fiber_g, sugar_g, sodium_mg etc.) mit "is not None"
prüfen — nie mit bloßem "if value". Decimal("0") ist falsy und würde sonst als
leerer String in der CSV erscheinen statt als "0.00".
Falsch:  fiber_g=(m.fiber_g * factor) if m.fiber_g else None
Richtig: fiber_g=(m.fiber_g * factor) if m.fiber_g is not None else None
Prüfe src/app/domain/models.py → scaled_macros und consumed_volume_ml
auf dieses Muster und korrigiere alle betroffenen Stellen vor der Implementierung.

KRITISCH 3 — Keine DB-Dateien committen:
Stelle sicher dass *.db und nutrition_tracker.db in .gitignore stehen.
Falls nutrition_tracker.db bereits getrackt wird:
  git rm --cached nutrition_tracker.db
und dann .gitignore ergänzen.

Technische Vorgaben:
- StreamingResponse mit io.StringIO als Generator
- csv-Modul aus stdlib — keine externe Dependency
- Alle Typannotierungen vollständig für mypy --strict
- Nullwerte (0.00) erscheinen als "0.00" in der CSV, nicht als leerer String

Schritte:
1. Prüfe und korrigiere src/app/domain/models.py:
   In scaled_macros: alle "if m.field" → "if m.field is not None"
   In consumed_volume_ml: gleiches Muster
2. Erstelle src/app/services/export_service.py:
   class ExportService mit generate_csv(entries: list[LogEntry]) -> Iterator[str]
   Nutzt csv.writer mit io.StringIO.
   CSV-Spalten: date, time, product_name, brand, source, quantity_g,
   calories_kcal, protein_g, carbohydrates_g, fat_g, fiber_g, sugar_g,
   is_liquid, volume_ml, note
   Fehlende optionale Felder als "0.00" ausgeben, nicht als leeren String.
   Erste Zeile: Header.
3. Ergänze get_export_service() in src/app/api/dependencies.py.
4. GET /api/v1/logs/export in src/app/api/v1/logs.py:
   Parameter direkt am Endpoint:
     from_date: date = Query(..., alias="from")
     to_date: date = Query(..., alias="to")
   Validierung: from_date <= to_date, max. 366 Tage.
   Response: StreamingResponse(content=..., media_type="text/csv")
   Header: Content-Disposition: attachment; filename="nutrition_<from>_<to>.csv"
5. Schreibe tests/unit/test_export_service.py:
   - test_header_row: erste CSV-Zeile enthält alle erwarteten Spalten
   - test_zero_nutrients_appear_as_zero: fiber_g=Decimal("0") → "0.00" in CSV
   - test_none_nutrients_appear_as_zero: fiber_g=None → "0.00" in CSV
   - test_scaled_macros_calculation: quantity_g=200 → Werte korrekt skaliert
6. Schreibe Integrationstest: Response-Status 200, Content-Type text/csv,
   Content-Disposition Header vorhanden.
7. Stelle sicher:
   - *.db in .gitignore, git rm --cached falls nötig
   - ruff check src/ tests/ gibt 0 Fehler
   - mypy src/app --strict gibt 0 Fehler
   - pytest läuft durch
```

---

### Prompt 7 — Daily Goals & Progress Tracking

```
Du arbeitest am Projekt "Nutrition & Hydration Tracking API".
Lies zuerst AGENTS.md vollständig (insbesondere Abschnitt 4a und 5.4),
dann src/app/domain/models.py, src/app/services/log_service.py
und src/app/api/v1/logs.py (als Muster für Endpoint-Struktur).

Implementiere tägliche Zielwerte mit Fortschrittsanzeige.

Technische Vorgaben:
- Alle Decimal-Felder als Decimal, nie float
- TenantDep ohne = None Default
- GoalsRepository als Singleton via @lru_cache in dependencies.py

Schritte:
1. Neue Domain-Modelle in src/app/domain/models.py:
   class DailyGoals(BaseModel):
     calories_kcal: Decimal | None = None
     protein_g: Decimal | None = None
     carbohydrates_g: Decimal | None = None
     fat_g: Decimal | None = None
     water_ml: Decimal | None = None
   class GoalProgress(BaseModel):
     target: Decimal
     actual: Decimal
     remaining: Decimal
     percent_achieved: Decimal
   class DailyGoalsProgress(BaseModel):
     log_date: date
     calories: GoalProgress | None = None
     protein: GoalProgress | None = None
     carbohydrates: GoalProgress | None = None
     fat: GoalProgress | None = None
     water: GoalProgress | None = None
2. Erstelle src/app/repositories/goals_repository.py:
   In-Memory, ein DailyGoals-Eintrag pro Tenant.
   Methoden: get(tenant_id) -> DailyGoals | None, save(tenant_id, goals) -> DailyGoals
3. Erstelle src/app/services/goals_service.py:
   get_goals(tenant_id) -> DailyGoals
   update_goals(tenant_id, goals) -> DailyGoals
   get_progress(tenant_id, log_date) -> DailyGoalsProgress
   (nutzt LogService für Tageswerte + GoalsRepository für Ziele)
4. Erstelle src/app/api/v1/goals.py:
   GET   /api/v1/goals
   PUT   /api/v1/goals    (Body: DailyGoals, ersetzt komplett)
   PATCH /api/v1/goals    (Body: DailyGoals mit allen Feldern optional)
   GET   /api/v1/goals/progress?date=2025-01-15
   (date optional, default: heute)
5. Registriere in src/app/api/v1/router.py.
6. Schreibe Unit-Tests für GoalsService und Integrationstests für alle 4 Endpoints.
7. Stelle sicher:
   - ruff check src/ tests/ gibt 0 Fehler
   - mypy src/app --strict gibt 0 Fehler
   - pytest läuft durch
```

---

### Prompt 8 — Meal Templates

```
Du arbeitest am Projekt "Nutrition & Hydration Tracking API".
Lies zuerst AGENTS.md vollständig (insbesondere Abschnitt 4a und 5.4),
dann src/app/domain/models.py, src/app/services/log_service.py
und src/app/api/v1/logs.py (als Muster).

Implementiere wiederverwendbare Mahlzeiten-Templates.

Technische Vorgaben:
- DataSource muss StrEnum sein
- Alle IDs als str (uuid.uuid4()) — nicht UUID-Typ
- Tenant-Isolation: jede Repository-Methode nimmt tenant_id als ersten Parameter
- TenantDep ohne = None Default

Schritte:
1. Neue Domain-Modelle in src/app/domain/models.py:
   class MealTemplateEntry(BaseModel):
     product_id: str
     source: DataSource
     quantity_g: Decimal = Field(gt=0)
     note: str | None = None
   class MealTemplate(BaseModel):
     id: str = Field(default_factory=lambda: str(uuid.uuid4()))
     tenant_id: str
     name: str = Field(min_length=1, max_length=200)
     entries: list[MealTemplateEntry] = Field(min_length=1)
   class MealTemplateCreate(BaseModel):
     name: str = Field(min_length=1, max_length=200)
     entries: list[MealTemplateEntry] = Field(min_length=1)
2. Erstelle src/app/repositories/template_repository.py:
   In-Memory, strukturiert als dict[str, dict[str, MealTemplate]] (tenant → id → template).
   Methoden: save(), find_by_id(), find_all(), delete()
3. Erstelle src/app/services/template_service.py:
   create(tenant_id, payload) -> MealTemplate
   get_all(tenant_id) -> list[MealTemplate]
   delete(tenant_id, template_id) -> bool
   log_template(tenant_id, template_id, log_date) -> list[LogEntry]
     (ruft für jeden Entry LogService.create_entry() auf)
4. Erstelle src/app/api/v1/templates.py:
   GET    /api/v1/templates
   POST   /api/v1/templates                (Body: MealTemplateCreate, HTTP 201)
   DELETE /api/v1/templates/{template_id}  (HTTP 204)
   POST   /api/v1/templates/{template_id}/log?date=2025-01-15
     (date optional, default: heute, gibt list[LogEntry] zurück)
5. Registriere in src/app/api/v1/router.py.
6. Schreibe Unit-Tests für TemplateService (inkl. Tenant-Isolation)
   und Integrationstests für alle Endpoints.
7. Stelle sicher:
   - ruff check src/ tests/ gibt 0 Fehler
   - mypy src/app --strict gibt 0 Fehler
   - pytest läuft durch
```

---

### Prompt 9 — Barcode Shortcut

```
Du arbeitest am Projekt "Nutrition & Hydration Tracking API".
Lies zuerst AGENTS.md vollständig (insbesondere Abschnitt 4a und 5.4),
dann src/app/adapters/open_food_facts.py, src/app/domain/ports.py
und src/app/api/v1/products.py (anlegen falls nicht vorhanden).

Implementiere einen Barcode-Lookup ohne Source-Angabe.

Technische Vorgaben:
- Suchreihenfolge konfigurierbar via Settings als list[str]
- Adapter-Fallback: ProductNotFoundError wird gefangen, nächster Adapter versucht
- ExternalApiError bei Netzwerkproblemen wird direkt als HTTP 502 weitergegeben
- Alle Typannotierungen vollständig für mypy --strict

Schritte:
1. Ergänze in src/app/core/config.py:
   BARCODE_LOOKUP_ORDER: list[str] = ["open_food_facts", "usda_fooddata"]
2. Erstelle src/app/services/barcode_service.py:
   class BarcodeService mit lookup(barcode: str) -> GeneralizedProduct
   Iteriert über BARCODE_LOOKUP_ORDER, holt Adapter aus Registry.
   Fängt ProductNotFoundError → nächster Adapter.
   Wenn alle Adapter ProductNotFoundError → raise ProductNotFoundError.
   Wenn ein Adapter ExternalApiError → sofort weiterwerfen.
3. GET /api/v1/products/barcode/{barcode} in src/app/api/v1/products.py:
   Authentifizierung via TenantDep.
   Ruft BarcodeService.lookup() auf.
   ProductNotFoundError → HTTP 404
   ExternalApiError → HTTP 502
4. Registriere BarcodeService in src/app/api/dependencies.py.
5. Schreibe tests/unit/test_barcode_service.py:
   - test_found_in_first_adapter: OFF findet Produkt → USDA nicht aufgerufen
   - test_fallback_to_second_adapter: OFF wirft ProductNotFoundError → USDA aufgerufen
   - test_not_found_anywhere: beide werfen ProductNotFoundError → ProductNotFoundError
   - test_external_api_error_propagates: OFF wirft ExternalApiError → sofort weitergeworfen
6. Schreibe Integrationstests in tests/integration/test_api_products.py.
7. Stelle sicher:
   - ruff check src/ tests/ gibt 0 Fehler
   - mypy src/app --strict gibt 0 Fehler
   - pytest läuft durch
```

---

### Prompt 10 — Prometheus Metrics

```
Du arbeitest am Projekt "Nutrition & Hydration Tracking API".
Lies zuerst AGENTS.md vollständig (insbesondere Abschnitt 4a und 5.4),
dann src/app/main.py und src/app/adapters/open_food_facts.py.

Implementiere einen Prometheus Metrics Endpoint.

Technische Vorgaben:
- prometheus-client als einzige neue Dependency
- Metrics als Modul-Level Singletons in core/metrics.py — nie als Instanzvariablen
- /metrics ohne Authentifizierung (internes Monitoring)
- Alle Typannotierungen vollständig für mypy --strict

Schritte:
1. Ergänze prometheus-client>=0.20 in pyproject.toml.
2. Erstelle src/app/core/metrics.py:
   REQUEST_COUNT = Counter("http_requests_total", "...", ["method", "path", "status_code"])
   EXTERNAL_API_COUNT = Counter("external_api_requests_total", "...", ["source", "status"])
   EXTERNAL_API_DURATION = Histogram("external_api_duration_seconds", "...", ["source"])
   CACHE_HITS = Counter("cache_hits_total", "...")
   CACHE_MISSES = Counter("cache_misses_total", "...")
3. Ergänze Starlette Middleware in src/app/main.py:
   Inkrementiert REQUEST_COUNT nach jedem Request mit method, path, status_code.
   Nutze BaseHTTPMiddleware — Signatur muss mypy --strict bestehen:
   async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response
4. Instrumentiere beide Adapter (open_food_facts.py, usda_fooddata.py):
   EXTERNAL_API_DURATION.labels(source="...").time() als Context-Manager um HTTP-Calls.
   EXTERNAL_API_COUNT inkrementieren nach jedem Call (status: "success" oder "error").
5. GET /metrics in src/app/main.py:
   from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
   return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
6. Ergänze in deploy/charts/nutrition-tracker/values.yaml:
   podAnnotations:
     prometheus.io/scrape: "true"
     prometheus.io/port: "8000"
     prometheus.io/path: "/metrics"
7. Schreibe tests/unit/test_metrics.py:
   Prüfe dass Counter nach einem simulierten Request inkrementiert wurde.
8. Stelle sicher:
   - ruff check src/ tests/ gibt 0 Fehler
   - mypy src/app --strict gibt 0 Fehler
   - pytest läuft durch
```

---

### Prompt 11 — Webhook Notifications (ntfy.sh / Gotify)

```
Du arbeitest am Projekt "Nutrition & Hydration Tracking API".
Lies zuerst AGENTS.md vollständig (insbesondere Abschnitt 4a und 5.4),
dann src/app/core/config.py und src/app/services/log_service.py.

Implementiere Webhook-Benachrichtigungen für Homelab-Notification-Dienste.

Technische Vorgaben:
- Fire-and-forget: asyncio.create_task() — Fehler werden geloggt, nie weitergereicht
- Auto-Detection des Dienstes anhand der URL
- NotificationService via DI in LogService injiziert — nie als globale Variable
- Alle Typannotierungen vollständig für mypy --strict
- httpx.AsyncClient für HTTP-Calls (bereits im Projekt vorhanden)

Schritte:
1. Ergänze in src/app/core/config.py:
   WEBHOOK_URL: str | None = None
   WEBHOOK_ENABLED: bool = False
2. Erstelle src/app/services/notification_service.py:
   class NotificationService mit send(title: str, message: str) -> None (async).
   Auto-Detection:
     "ntfy.sh" in url → POST {url}/{topic} mit Text-Body und Title-Header
     sonst (Gotify) → POST {url}/message mit JSON {"title": ..., "message": ..., "priority": 5}
   Fire-and-forget via asyncio.create_task().
   Wenn WEBHOOK_ENABLED=False → sofort return ohne HTTP-Call.
3. Trigger-Events in LogService (nach erfolgreichem save()):
   - Erster Log-Eintrag des Tages: "Logging started for {date}"
   - Optional: Kalorienziel erreicht (nur wenn GoalsService verfügbar)
4. Injiziere NotificationService in LogService.__init__():
   notification_service: NotificationService | None = None
   Wenn None → keine Notifications (rückwärtskompatibel).
5. Ergänze get_notification_service() in src/app/api/dependencies.py.
6. Schreibe tests/unit/test_notification_service.py:
   Mocke httpx.AsyncClient.
   - test_ntfy_sends_correct_request: URL-Format und Header prüfen
   - test_gotify_sends_correct_json: JSON-Body prüfen
   - test_disabled_webhook_skips_http: kein HTTP-Call wenn WEBHOOK_ENABLED=False
   - test_error_is_not_propagated: HTTP-Fehler wird geloggt, nicht weitergereicht
7. Stelle sicher:
   - ruff check src/ tests/ gibt 0 Fehler
   - mypy src/app --strict gibt 0 Fehler
   - pytest läuft durch
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---

*Built for the homelab. Designed for the enterprise.*