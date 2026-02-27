# src/app/main.py
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.dependencies import get_http_client
from app.api.v1.router import api_router
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: HTTP Client initialisieren
    yield
    # Shutdown: Gracefully schließen
    client = get_http_client()
    await client.aclose()


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type"],
)

app.include_router(api_router)


@app.get("/healthz", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}


@app.get("/readyz", tags=["Health"])
async def readiness_check() -> dict[str, str]:
    return {"status": "ready"}
