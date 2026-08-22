from functools import lru_cache
import json
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from pydantic import BeforeValidator, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

def normalize_database_url(url: str) -> str:
    """Neon/Supabase → asyncpg-compatible SQLAlchemy URL."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]

    parts = urlsplit(url)
    query: list[tuple[str, str]] = []
    has_ssl = False
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        # asyncpg rejects libpq sslmode= and Neon channel_binding=
        if lowered == "channel_binding":
            continue
        if lowered == "sslmode":
            query.append(("ssl", "require"))
            has_ssl = True
            continue
        if lowered == "ssl":
            has_ssl = True
            query.append((key, value if value else "require"))
            continue
        query.append((key, value))

    # Neon requires TLS; ensure ssl is present for remote hosts
    host = (parts.hostname or "").lower()
    if not has_ssl and host and host not in {"localhost", "127.0.0.1"}:
        query.append(("ssl", "require"))

    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )

def sync_database_url(url: str) -> str:
    """Alembic/psycopg2 URL (no +asyncpg; sslmode instead of ssl)."""
    url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parts = urlsplit(url)
    query: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() == "ssl":
            query.append(("sslmode", "require"))
        else:
            query.append((key, value))
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )

def parse_cors_origins(value: object) -> list[str]:
    if value is None:
        return ["http://localhost:3000"]
    if isinstance(value, list):
        return [str(item).strip().rstrip("/") for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return ["http://localhost:3000"]
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip().rstrip("/") for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    return [part.strip().rstrip("/") for part in text.split(",") if part.strip()]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="OPERAI_", extra="ignore")
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/operai"
    jwt_secret: str = Field("development-secret-change-this-now", min_length=32)
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    # NoDecode: Render often sets a plain URL or empty string; skip JSON env decode.
    cors_origins: Annotated[list[str], NoDecode, BeforeValidator(parse_cors_origins)] = [
        "http://localhost:3000"
    ]
    asaas_api_key: str = ""
    asaas_api_url: str = "https://sandbox.asaas.com/api/v3"
    asaas_webhook_token: str = "dev-asaas-webhook"
    trial_days: int = 14
    encryption_key: str = ""
    evolution_api_url: str = "http://127.0.0.1:8080"
    evolution_api_key: str = ""
    public_api_url: str = "http://127.0.0.1:8001"
    frontend_url: str = "http://localhost:3000"

    @field_validator("database_url", mode="before")
    @classmethod
    def _db_url(cls, value: str) -> str:
        return normalize_database_url(str(value))

@lru_cache
def get_settings() -> Settings:
    return Settings()
