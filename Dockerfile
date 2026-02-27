# Dockerfile
# ============================================================
# Stage 1: Builder — Abhängigkeiten installieren
# ============================================================
FROM python:3.12-slim AS builder

WORKDIR /build

# System-Deps für Compilation (falls nötig)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install .

# ============================================================
# Stage 2: Runtime — minimales produktionsreifes Image
# ============================================================
FROM python:3.12-slim AS runtime

# Security: Non-Root User
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

# Installierte Packages aus Builder übernehmen
COPY --from=builder /install /usr/local
COPY src/app ./app

USER appuser

EXPOSE 8000

# Graceful Shutdown via SIGTERM wird von uvicorn nativ unterstützt
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info", \
     "--no-access-log"]
```
```