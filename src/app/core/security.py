# src/app/core/security.py
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=True)


async def get_tenant_id(
    api_key: str = Security(_API_KEY_HEADER),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    FastAPI Dependency: Validiert den API-Key und gibt die Tenant-ID zurück.
    Wirft HTTP 401 bei ungültigem Key.
    """
    tenant_id = settings.api_keys.get(api_key)
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return tenant_id
