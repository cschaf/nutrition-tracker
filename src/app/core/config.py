# src/app/core/config.py
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    app_name: str = "Nutrition Tracker API"
    app_version: str = "1.0.0"
    debug: bool = False

    # API Keys: Mapping von API-Key zu Tenant-ID (JSON-String als Env-Var)
    # Format: '{"key_abc123": "tenant_alice", "key_xyz789": "tenant_bob"}'
    api_keys: dict[str, str] = Field(default_factory=dict)

    # External APIs
    usda_api_key: str = Field(default="DEMO_KEY")

    # CORS
    cors_origins: list[str] = Field(default=["*"])

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
