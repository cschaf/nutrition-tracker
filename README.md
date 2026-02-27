# 🥗 Nutrition & Hydration Tracking API

> A cloud-native, multi-tenant REST API for tracking daily nutrition and hydration intake.
> Built with FastAPI, Python 3.12, and designed for Kubernetes/Homelab deployment via FluxCD.

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
- [Linting & Code Quality](#-linting--code-quality)
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

### Release

```bash
git tag v1.2.0
git push --tags
# Done — CI builds and pushes, FluxCD deploys
```

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

- [ ] **Persistent storage:** SQLite via SQLAlchemy (single-file, zero-ops for homelab)
- [ ] **Product caching:** In-memory TTL cache to avoid redundant external API calls
- [ ] **Search endpoint:** `GET /api/v1/products/search?q=banana&source=open_food_facts`
- [ ] **Weekly/monthly aggregation:** Trend endpoints for nutrition over time
- [ ] **Manual product entry:** `POST /api/v1/products` with `source: manual`
- [ ] **Export:** `GET /api/v1/logs/export?format=csv&from=...&to=...`
- [ ] **Goals tracking:** Daily targets for calories, protein, water intake
- [ ] **Formal Repository ABC:** Introduce `AbstractLogRepository` for explicit interface contract
- [ ] **Pre-commit config:** Add `mypy` to pre-commit hooks

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---

*Built for the homelab. Designed for the enterprise.*